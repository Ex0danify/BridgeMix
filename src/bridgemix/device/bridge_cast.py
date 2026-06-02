"""
BridgeCast — QObject facade for the Roland Bridge Cast.

Responsibilities:
  - Heartbeat (50 ms QTimer, 3 RQ1 frames/tick; 3 extra every 20th tick)
  - Universal MIDI Identity Request on connect
  - Thread-safe RX dispatch (mido callback → queued Qt signal → main thread)
  - Generic set_parameter() / state management
  - Level-meter decoding from heartbeat state vector (FW 1.06: 137-byte; FW 3.00: 127-byte + continuation)
"""
from __future__ import annotations

import logging
import time

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal

from bridgemix.device import constants as C
from bridgemix.device.parameters import REGISTRY, lookup_by_address
from bridgemix.midi.sysex import (
    build_heartbeat_rq1,
    build_identity_request,
    build_read,
    build_write,
    parse,
    parse_identity_reply,
)
from bridgemix.midi.transport import MidiTransport

log = logging.getLogger(__name__)

# Heartbeat RQ1 frames sent every tick (50 ms)
_HB_TICK_FRAMES = [
    build_heartbeat_rq1(0x10, 0x00, 0x7C),   # 124-byte state vector (level meters)
    build_heartbeat_rq1(0x11, 0x40, 0x08),   # dynamic status A (8 bytes)
    build_heartbeat_rq1(0x11, 0x60, 0x10),   # dynamic status B (16 bytes)
]

# Additional RQ1 frames sent every 20th tick (~1 s)
_HB_LONG_FRAMES = [
    build_heartbeat_rq1(0x00, 0x00, 0x08),   # keep-alive ping (firmware echo)
    build_heartbeat_rq1(0x10, 0x00, 0x7C),   # state vector (also in normal batch)
    build_heartbeat_rq1(0x11, 0x00, 0x70),   # full status snapshot (112 bytes)
]

# Bulk sync RQ1 frames sent on connect — (section, type, addr_hi, addr_lo, size)
# Staggered 5 ms apart to avoid wedging the device.
_SYNC_FRAMES = [
    (C.SECTION_GLOBAL,  C.TYPE_SWITCH,       0x00, 0x00, C.SYNC_RQ1_GLOBAL_SIZE),
    (C.SECTION_CHANNEL, C.TYPE_FADER,        0x00, 0x00, C.SYNC_RQ1_FADER_SIZE),
    (C.SECTION_CHANNEL, C.TYPE_SWITCH,       0x00, 0x00, C.SYNC_RQ1_SWITCH_SIZE),
    (C.SECTION_CHANNEL, C.TYPE_DELAY,        0x00, 0x00, C.SYNC_RQ1_DELAY_SIZE),
    (C.SECTION_CHANNEL, C.TYPE_STRIP_CONFIG, 0x00, 0x00, C.SYNC_RQ1_LED_SIZE),
    # Mic Clean Up + 10-band EQ — all mic_* parameters under TYPE_MIC_FX (0x01)
    (C.SECTION_CHANNEL, C.TYPE_MIC_FX,       0x00, 0x00, C.SYNC_RQ1_MIC_FX_SIZE),
    # NS Expander + Compressor Modern/mode (TYPE_MIC_FX_EXT = 0x0E)
    (C.SECTION_CHANNEL, C.TYPE_MIC_FX_EXT,  0x00, 0x00, C.SYNC_RQ1_MIC_EXT_SIZE),
    # Voice FX + Reverb
    (C.SECTION_CHANNEL, C.TYPE_VOICE,        0x00, 0x00, C.SYNC_RQ1_VOICE_SIZE),
    # Chat channel effects
    (C.SECTION_CHANNEL, C.TYPE_CHAT_FX,      0x00, 0x00, C.SYNC_RQ1_CHAT_FX_SIZE),
    # Game EQ + Limiter + Virtual Surround
    (C.SECTION_CHANNEL, C.TYPE_GAME_FX,      0x00, 0x00, C.SYNC_RQ1_GAME_FX_SIZE),
    # Hot Key button assignments
    (C.SECTION_CHANNEL, C.TYPE_HOTKEY,       0x00, 0x00, C.SYNC_RQ1_HOTKEY_SIZE),
]


class BridgeCast(QObject):
    # Public signals
    connected = pyqtSignal(bool)                  # device connected / disconnected
    parameter_changed = pyqtSignal(str, int)      # name, value
    meter_updated = pyqtSignal(dict)              # {channel_key: (L, R)} 0–16383
    status_message = pyqtSignal(str)              # human-readable status
    sysex_tx = pyqtSignal(tuple)                  # raw mido tuple (for MIDI monitor)
    sysex_rx = pyqtSignal(tuple)                  # raw mido tuple (for MIDI monitor)
    hw_strip_assignment_changed = pyqtSignal(int, str)  # strip_index (0–3), ch_key
    device_info_updated = pyqtSignal(str, str)    # model_name, firmware_version
    voice_preset_names_updated = pyqtSignal(list) # list[str] — 5 Voice FX preset names
    profile_names_updated      = pyqtSignal(list) # list[str] — 5 device profile names
    game_eq_preset_names_updated = pyqtSignal(list) # list[str] — 5 Game EQ preset slot names

    # Internal signal for thread-bouncing mido callback → Qt main thread
    _sysex_received_internal = pyqtSignal(tuple)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._transport = MidiTransport()
        self._state: dict[str, int] = {
            name: p.default_value for name, p in REGISTRY.items()
        }
        self._tick = 0
        self._is_connected = False
        self._last_rx: float = 0.0
        self._device_info: tuple[str, str] | None = None  # (model, firmware) dedup
        self._voice_preset_names: list[str] = [f"Preset {i+1}"  for i in range(5)]
        self._profile_names:      list[str] = [f"Profile {i+1}" for i in range(5)]
        self._game_eq_preset_names: list[str] = [f"Game EQ {i+1}" for i in range(5)]
        # Cache for OUT_PHONES R and OUT_LINE from the FW 3.00 continuation frame
        # (sec=0x01, type=0x10, addr_hi=0x70).  Updated by _decode_status10_continuation()
        # each tick; consumed by _decode_state_vector().  At most one tick (50 ms) stale.
        self._cached_phones_R: int = 0
        self._cached_line:     tuple[int, int] = (0, 0)

        # Guard against device pushing stale bulk state after a host write.
        # Maps param name → expiry timestamp (monotonic). While guarded, incoming
        # device state for that param is ignored so fresh host writes are not undone.
        self._write_guard: dict[str, float] = {}

        # Heartbeat timer — sends RQ1 frames to device every 50 ms
        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(50)
        self._heartbeat.timeout.connect(self._send_heartbeat)

        # Watchdog — declares device lost if no DT1 reply arrives within 2 s
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(500)
        self._watchdog.timeout.connect(self._check_heartbeat)

        # Bounce mido background thread → Qt main thread
        self._sysex_received_internal.connect(
            self._on_sysex_received, Qt.ConnectionType.QueuedConnection
        )

        # Re-emit hw_strip_assignment_changed whenever a strip assignment param changes
        self.parameter_changed.connect(self._on_strip_param_changed)

    # ── Connection management ─────────────────────────────────────────────────

    def connect_device(self, tx_port: str, rx_port: str) -> bool:
        """Open MIDI ports, send identity request, start heartbeat."""
        if self._is_connected:
            self.disconnect_device()
        try:
            self._transport.open(tx_port, rx_port, self._sysex_callback_threaded)
        except Exception as exc:
            log.error("Failed to open MIDI ports: %s", exc)
            self.status_message.emit(f"Connection failed: {exc}")
            return False

        self._is_connected = True
        self._last_rx = time.monotonic()
        self._send_identity_request()
        self._send_rx_enable()
        self._heartbeat.start()
        self._watchdog.start()
        self.connected.emit(True)
        self.status_message.emit(f"Connected — TX: {tx_port}")
        # Give the device 400 ms to process the identity request, then pull all values
        QTimer.singleShot(400, self._sync_all_parameters)
        return True

    def disconnect_device(self) -> None:
        if not self._is_connected:
            return
        self._is_connected = False
        self._heartbeat.stop()
        self._watchdog.stop()
        # Tell the device to stop streaming, then give it a brief moment to act
        # and let the RX buffer drain BEFORE closing the port.  Closing while the
        # device is still streaming deadlocks rtmidi's native close_port()
        # (midiInReset flushes buffered input through the GIL-bound callback).
        # This mirrors the official app, which also disables RX before closing.
        self._send_rx_disable()
        time.sleep(C.RX_DRAIN_BEFORE_CLOSE_S)
        self._transport.close()
        self.connected.emit(False)
        self.status_message.emit("Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def state(self) -> dict[str, int]:
        return dict(self._state)

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _send_heartbeat(self) -> None:
        for frame in _HB_TICK_FRAMES:
            self._send_raw(frame)
        if self._tick % 20 == 0:
            for frame in _HB_LONG_FRAMES:
                self._send_raw(frame)
        self._tick = (self._tick + 1) % 20

    def _check_heartbeat(self) -> None:
        """Watchdog: disconnect if no DT1 reply has arrived within 2 seconds."""
        if time.monotonic() - self._last_rx > 2.0:
            log.warning("Heartbeat timeout — device not responding")
            self.status_message.emit("Device lost — no response from Bridge Cast")
            self.disconnect_device()

    def _send_identity_request(self) -> None:
        self._send_raw(build_identity_request())

    def _send_rx_enable(self) -> None:
        self._send_raw(build_write(
            C.SECTION_STATUS, C.SUBTYPE_STATUS_10, C.ADDR_STATUS_10, 0x00, C.RX_ENABLE_ON
        ))

    def _send_rx_disable(self) -> None:
        self._send_raw(build_write(
            C.SECTION_STATUS, C.SUBTYPE_STATUS_10, C.ADDR_STATUS_10, 0x00, C.RX_ENABLE_OFF
        ))

    def _sync_all_parameters(self) -> None:
        """Send bulk RQ1 reads to pull the full device state into the UI."""
        if not self._is_connected:
            return
        self.status_message.emit("Connected — syncing device state…")
        for i, (sec, type_, hi, lo, size) in enumerate(_SYNC_FRAMES):
            frame = build_read(sec, type_, hi, lo, size)
            QTimer.singleShot(i * 5, lambda f=frame: self._send_raw(f))
        log.debug("Sync: queued %d bulk RQ1 reads", len(_SYNC_FRAMES))
        # Stagger name reads after the main sync burst finishes
        burst_ms = len(_SYNC_FRAMES) * 5 + 100
        QTimer.singleShot(burst_ms,       self._sync_voice_preset_names)
        QTimer.singleShot(burst_ms + 50,  self._sync_profile_names)
        QTimer.singleShot(burst_ms + 100, self._sync_game_eq_preset_names)

    def _sync_voice_preset_names(self) -> None:
        """Request the name string of each Voice FX preset slot (SECTION_SYNC_10)."""
        if not self._is_connected:
            return
        # Each slot uses type = slot_index × 0x10.
        # Full 70-byte slot payload: name (ASCII) at addr 0x00–0x11,
        # voice params at canonical addresses from 0x20 onwards.
        for slot in range(5):
            frame = build_read(C.SECTION_SYNC_10, slot * 0x10, 0x00, 0x00,
                               C.SYNC_RQ1_VOICE_FX_PRESET_SIZE)
            QTimer.singleShot(slot * 5, lambda f=frame: self._send_raw(f))
        log.debug("Sync: queued 5 Voice FX preset name reads (SECTION_SYNC_10)")

    def _sync_profile_names(self) -> None:
        """Explicitly request the first 18 bytes of TYPE_SWITCH for each profile slot.

        Profile names occupy addr 0x00–0x11 of TYPE_SWITCH in SECTION_PROFILE_*
        (sec=0x20–0x24).  The per-profile TYPE_SWITCH dump normally arrives
        automatically in response to the main sync burst; these explicit reads
        provide a reliable fallback (e.g. after loading factory defaults).
        Pattern confirmed from official app load-defaults capture (2026-05-27).
        """
        if not self._is_connected:
            return
        for slot in range(5):
            sec = C.SECTION_PROFILE_FIRST + slot
            frame = build_read(sec, C.TYPE_SWITCH, 0x00, 0x00,
                               C.SYNC_RQ1_PROFILE_NAME_SIZE)
            QTimer.singleShot(slot * 5, lambda f=frame: self._send_raw(f))
        log.debug("Sync: queued 5 profile name reads (SECTION_PROFILE_* TYPE_SWITCH addr=0x00)")

    def _sync_game_eq_preset_names(self) -> None:
        """Request the name string of each Game EQ preset slot (SECTION_SYNC_11).

        Each slot uses type = slot_index × 0x10, mirroring the Voice FX preset
        bank (SECTION_SYNC_10).  Confirmed 2026-06-01.
        """
        if not self._is_connected:
            return
        for slot in range(5):
            frame = build_read(C.SECTION_SYNC_11, slot * 0x10, 0x00, 0x00,
                               C.SYNC_RQ1_GAME_EQ_PRESET_SIZE)
            QTimer.singleShot(slot * 5, lambda f=frame: self._send_raw(f))
        log.debug("Sync: queued 5 Game EQ preset name reads (SECTION_SYNC_11)")

    def sync_game_eq_preset_names(self) -> None:
        """Public wrapper — re-fetch all 5 Game EQ preset slot names."""
        self._sync_game_eq_preset_names()

    def refresh_game_fx(self) -> None:
        """Re-read the live Game FX block (EQ curve, enable, limiter, surround).

        Used after selecting a Game EQ preset slot so the UI reflects the newly
        loaded curve (the official app issues the same read after a slot select).
        """
        if not self._is_connected:
            return
        self._send_raw(build_read(C.SECTION_CHANNEL, C.TYPE_GAME_FX, 0x00, 0x00,
                                  C.SYNC_RQ1_GAME_FX_SIZE))

    # ── Parameter control ────────────────────────────────────────────────────

    def get_parameter(self, name: str) -> int:
        """Return current cached value; raises KeyError for unknown names."""
        return self._state[name]

    def set_parameter(self, name: str, value: int) -> None:
        """Validate, send SysEx write, update state, emit signal."""
        p = REGISTRY.get(name)
        if p is None:
            log.warning("Unknown parameter: %s", name)
            return
        if p.read_only:
            return
        if not (p.min_value <= value <= p.max_value):
            log.warning("Value %d out of range [%d, %d] for %s", value, p.min_value, p.max_value, name)
            return
        frame = build_write(p.section, p.param_type, p.addr_hi, p.addr_lo, value)
        self._send_raw(frame)
        self._state[name] = value
        self._write_guard[name] = time.monotonic() + 0.5  # protect for 500 ms
        self.parameter_changed.emit(name, value)

    def set_vsurround_angle(self, name: str, degrees: int) -> None:
        """Write a surround/back angle (91°–179°) whose addr_lo encodes the high bit.

        Wire: addr_lo = degrees >> 7,  val = degrees & 0x7F.
        Registered as read_only in REGISTRY so set_parameter() won't be called.
        """
        p = REGISTRY.get(name)
        if p is None:
            return
        if not (p.min_value <= degrees <= p.max_value):
            log.warning("Angle %d out of range for %s", degrees, name)
            return
        addr_lo = degrees >> 7
        val     = degrees & 0x7F
        frame = build_write(p.section, p.param_type, p.addr_hi, addr_lo, val)
        self._send_raw(frame)
        self._state[name] = degrees
        self._write_guard[name] = time.monotonic() + 0.5
        self.parameter_changed.emit(name, degrees)

    def send_raw_sysex(self, data: tuple[int, ...]) -> None:
        """Send a raw SysEx mido tuple (for MIDI monitor raw sender)."""
        self._send_raw(data)

    def set_hw_strip_channel(self, strip_index: int, ch_key: str) -> None:
        """Write hardware strip channel assignment to device (strip_index 0–3)."""
        names = ["hw_strip_1_ch", "hw_strip_2_ch", "hw_strip_3_ch", "hw_strip_4_ch"]
        if 0 <= strip_index < len(names):
            value = C.HW_STRIP_CH_VALUE.get(ch_key)
            if value is not None:
                self.set_parameter(names[strip_index], value)

    # ── Profile management ────────────────────────────────────────────────────

    def _write_name_pairs(self, type_byte: int, name: str) -> None:
        """Send 9 DT1 frames that write a name into the live SECTION_CHANNEL name region.

        Shared by write_profile_name (TYPE_SWITCH) and write_voice_fx_preset_name
        (TYPE_VOICE).  Encoding confirmed 2026-05-28 — identical for both name types:

          sec=SECTION_CHANNEL, type=type_byte
          addr_hi = 2 × pair_index      (0x00, 0x02, …, 0x10)
          addr_lo = name[2i+1]          (odd  char = second of pair, 7-bit ASCII)
          value   = name[2i]            (even char = first of pair;  0x00 if absent)

        The decoders prepend addr_lo as payload[0] and then read (payload[i], payload[i+1])
        as (hi=second_char, lo=first_char), emitting lo then hi.  Both name decoders
        (_handle_voice_preset_name_frame and _handle_profile_name_frame) use this same
        convention.

        Wire example for "Mary" pair 0:
          build_write(SECTION_CHANNEL, type, 0x00, addr_lo=0x61='a', value=0x4D='M')
        """
        padded = name[: C.VOICE_FX_PRESET_NAME_MAX].ljust(C.VOICE_FX_PRESET_NAME_MAX, "\x00")
        for i in range(9):
            addr_lo = ord(padded[2 * i + 1]) & 0x7F   # second/odd char
            value   = ord(padded[2 * i]) & 0x7F         # first/even char
            QTimer.singleShot(
                i * 5,
                lambda _hi=2 * i, _lo=addr_lo, _v=value: self._send_raw(
                    build_write(C.SECTION_CHANNEL, type_byte, _hi, _lo, _v)
                ),
            )

    def write_profile_name(self, slot: int, name: str) -> None:
        """Write a profile name into the live SECTION_CHANNEL TYPE_SWITCH name region.

        Must be called BEFORE save_profile_to_slot() — the save copies the full
        CHANNEL TYPE_SWITCH block (including these name bytes) into the profile slot.
        Allow at least 50 ms before sending the save.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._write_name_pairs(C.TYPE_SWITCH, name[: C.VOICE_FX_PRESET_NAME_MAX])
        log.info("Profile %d: writing name %r to SECTION_CHANNEL (9 standard writes)",
                 slot, name)

    def sync_profile_names(self) -> None:
        """Public wrapper — re-fetch all 5 profile names from the device."""
        self._sync_profile_names()

    def sync_voice_preset_names(self) -> None:
        """Public wrapper — re-fetch all 5 Voice FX preset names from the device."""
        self._sync_voice_preset_names()

    def save_profile_to_slot(self, slot: int) -> None:
        """Save current device state to profile slot (0–4).

        Sends ADDR_PROFILE_SAVE (addr_hi=0x06) then ADDR_PROFILE_SELECT_7F
        (addr_hi=0x00), both with sec=0x7F type=0x7F addr_lo=0x00 val=slot.
        Pattern confirmed from 2026-05-27 save capture.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_PROFILE_SAVE, 0x00, slot))
        QTimer.singleShot(
            50, lambda s=slot: self._send_raw(
                build_write(0x7F, 0x7F, C.ADDR_PROFILE_SELECT_7F, 0x00, s)
            )
        )
        log.info("Profile: saved current state to slot %d", slot)

    # ── Voice FX preset management ────────────────────────────────────────────

    def write_voice_fx_preset_name(self, slot: int, name: str) -> None:
        """Write a Voice FX preset name to the live voice state and save to slot.

        Sends 9 DT1 frames (via _write_name_pairs with TYPE_VOICE) to write the
        name into the live SECTION_CHANNEL TYPE_VOICE name region, then one commit
        frame to persist the full live voice state to the target slot in SECTION_SYNC_10.

        After the 9 name frames a commit (save) frame is sent:
          sec=SECTION_VOICE_FX (0x7F), type=TYPE_VOICE_FX (0x7F)
          addr_hi=ADDR_VOICE_FX_SAVE (0x08), addr_lo=0x00, value=slot (0-indexed)
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._write_name_pairs(C.TYPE_VOICE, name[: C.VOICE_FX_PRESET_NAME_MAX])
        QTimer.singleShot(
            9 * 5 + 10,
            lambda s=slot: self._send_raw(
                build_write(C.SECTION_VOICE_FX, C.TYPE_VOICE_FX, C.ADDR_VOICE_FX_SAVE, 0x00, s)
            ),
        )
        log.info(
            "Voice FX preset %d: writing name %r (9 frames + commit)",
            slot, name[:C.VOICE_FX_PRESET_NAME_MAX],
        )

    def save_voice_fx_preset_to_slot(self, slot: int) -> None:
        """Save the current live voice state to a Voice FX preset slot (0–4).

        Sends the ADDR_VOICE_FX_SAVE commit frame without writing a new name.
        Use write_voice_fx_preset_name() when you also want to rename the slot.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(
            build_write(C.SECTION_VOICE_FX, C.TYPE_VOICE_FX, C.ADDR_VOICE_FX_SAVE, 0x00, slot)
        )
        log.info("Voice FX preset: saved live state to slot %d", slot)

    def reset_profile_to_defaults(self, slot: int) -> None:
        """Reset profile slot (0–4) to factory defaults.

        Sends ADDR_PROFILE_RESET_DEFAULT (addr_hi=0x12) with sec=0x7F
        type=0x7F addr_lo=0x00 val=slot.  Schedules a profile-name re-fetch
        500 ms later so the list updates with the restored factory name.
        Confirmed from 2026-05-27 load-defaults capture.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_PROFILE_RESET_DEFAULT, 0x00, slot))
        log.info("Profile: reset slot %d to factory defaults", slot)
        QTimer.singleShot(500, self._sync_profile_names)

    def reset_voice_fx_preset_to_defaults(self, slot: int) -> None:
        """Reset a Voice FX preset slot (0–4) to factory defaults.

        Sends ADDR_VOICE_FX_RESET_DEFAULT (addr_hi=0x14) with sec=0x7F
        type=0x7F addr_lo=0x00 val=slot.  Schedules a preset-name re-fetch
        500 ms later so the list reflects the restored factory name.
        Confirmed from 2026-05-28 capture (addr=0x14, same frame structure
        as ADDR_PROFILE_RESET_DEFAULT=0x12).
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_VOICE_FX_RESET_DEFAULT, 0x00, slot))
        log.info("Voice FX preset: reset slot %d to factory defaults", slot)
        QTimer.singleShot(500, self._sync_voice_preset_names)

    # ── Game EQ preset slot management ─────────────────────────────────────────

    def select_game_eq_preset(self, slot: int) -> None:
        """Load Game EQ preset slot (0–4) into the live EQ.

        Uses the 0x7F/0x7F command (addr=ADDR_GAME_EQ_PRESET_SELECT, val=slot),
        which is what the official app sends — writing ADDR_GAME_EQ_PRESET (0x34)
        only reports the active slot back and does NOT load the curve.
        Confirmed 2026-06-01.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_GAME_EQ_PRESET_SELECT, 0x00, slot))
        log.info("Game EQ: selected preset slot %d", slot)

    def save_game_eq_preset_to_slot(self, slot: int) -> None:
        """Persist the current live Game EQ into preset slot (0–4).

        Sends the ADDR_GAME_EQ_PRESET_SAVE command without renaming the slot.
        Use write_game_eq_preset_name() to also set a name.  Confirmed 2026-06-01.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_GAME_EQ_PRESET_SAVE, 0x00, slot))
        log.info("Game EQ preset: saved live EQ to slot %d", slot)

    def write_game_eq_preset_name(self, slot: int, name: str) -> None:
        """Write a name into the live Game EQ block, then save it to a slot.

        Sends 9 DT1 name-pair frames (via _write_name_pairs with TYPE_GAME_FX),
        then the ADDR_GAME_EQ_PRESET_SAVE command to persist the named EQ to the
        target slot.  Same name encoding as profiles / Voice FX.  Confirmed
        2026-06-01 (renamed slot 1 to "TEST").
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._write_name_pairs(C.TYPE_GAME_FX, name[: C.GAME_EQ_PRESET_NAME_MAX])
        QTimer.singleShot(
            9 * 5 + 10,
            lambda s=slot: self._send_raw(
                build_write(0x7F, 0x7F, C.ADDR_GAME_EQ_PRESET_SAVE, 0x00, s)
            ),
        )
        QTimer.singleShot(9 * 5 + 110, self._sync_game_eq_preset_names)
        log.info("Game EQ preset %d: writing name %r (9 frames + save)",
                 slot, name[: C.GAME_EQ_PRESET_NAME_MAX])

    def reset_game_eq_preset_to_defaults(self, slot: int) -> None:
        """Reset a Game EQ preset slot (0–4) to its factory default.

        Sends ADDR_GAME_EQ_PRESET_RESET (0x16) with sec=0x7F type=0x7F val=slot,
        then re-fetches the slot names.  Confirmed 2026-06-01.
        """
        if not self._is_connected or not (0 <= slot <= 4):
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_GAME_EQ_PRESET_RESET, 0x00, slot))
        log.info("Game EQ preset: reset slot %d to factory default", slot)
        QTimer.singleShot(500, self._sync_game_eq_preset_names)

    def factory_reset(self) -> None:
        """Reset the ENTIRE device to factory defaults.

        Replicates the official app's factory-reset sequence (captured 2026-06-01):
        two DT1 command frames to sec=0x7F type=0x7F addr_hi=ADDR_FACTORY_RESET,
        with the magic args 0x55/0x55 then 0x7F/0x7F.  The device performs the
        reset internally — we only trigger it, then re-pull the full state so the
        UI reflects the restored defaults (the app does the same bulk read-back).
        """
        if not self._is_connected:
            return
        self._send_raw(build_write(0x7F, 0x7F, C.ADDR_FACTORY_RESET, 0x55, 0x55))
        QTimer.singleShot(
            50, lambda: self._send_raw(
                build_write(0x7F, 0x7F, C.ADDR_FACTORY_RESET, 0x7F, 0x7F)
            )
        )
        log.info("Device: factory reset triggered")
        # Give the device time to finish resetting internally, then resync.
        QTimer.singleShot(600, self._sync_all_parameters)

    def export_profile(self, slot: int) -> dict:
        """Return the current device state as a JSON-serializable dict.

        Captures all REGISTRY parameters (SECTION_CHANNEL scope — the live
        values for whichever profile is currently active).  Uses the BridgeMix
        profile format; not directly compatible with the official app's
        .brdgcProfile format.
        """
        return {
            "ExportModelName": "BRIDGECAST",
            "ExportApp": "BridgeMix",
            "ExportVersion": 1,
            "profile_slot": slot,
            "profile_name": (
                self._profile_names[slot] if 0 <= slot <= 4 else ""
            ),
            "parameters": dict(self._state),
        }

    def import_profile(self, data: dict) -> int:
        """Apply a BridgeMix-format profile dict back to the device.

        Iterates the ``parameters`` key and calls set_parameter() for each
        recognised name.  Returns the number of parameters applied.
        """
        if not self._is_connected:
            return 0
        params = data.get("parameters", {})
        applied = 0
        for name, value in params.items():
            if name in REGISTRY:
                self.set_parameter(name, int(value))
                applied += 1
        log.info("Profile import: applied %d parameters", applied)
        return applied

    # ── RX dispatch ──────────────────────────────────────────────────────────

    def _sysex_callback_threaded(self, data: tuple[int, ...]) -> None:
        """Called from mido background thread — bounce to Qt main thread."""
        self._sysex_received_internal.emit(data)

    def _on_sysex_received(self, data: tuple[int, ...]) -> None:
        """Process an incoming SysEx frame (runs on Qt main thread)."""
        self._last_rx = time.monotonic()
        self.sysex_rx.emit(data)

        # Universal MIDI Identity Reply (7E … 06 02 …) — not a Roland DT1 frame
        if data and data[0] == 0x7E:
            info = parse_identity_reply(data)
            if info is not None:
                self._decode_identity_reply(info)
            return

        frame = parse(data)
        if frame is None:
            return

        cmd = frame["cmd"]
        sec = frame["section"]
        type_ = frame["type"]
        addr_hi = frame["addr_hi"]
        addr_lo = frame["addr_lo"]

        if cmd == 0x12:  # DT1 (device → host)
            if sec == C.SECTION_STATUS:
                # Heartbeat reply
                if type_ == C.SUBTYPE_STATUS_10 and addr_hi == 0x00:
                    # State vector — decode level meters (127 bytes FW 3.00, 137 bytes FW 1.06)
                    self._decode_state_vector(data)
                elif type_ == C.SUBTYPE_STATUS_10 and addr_hi == C.METER_ADDR_CONTINUATION:
                    # FW 3.00 continuation frame — carries OUT_PHONES R and OUT_LINE
                    self._decode_status10_continuation(frame)
                elif type_ == 0x00 and addr_hi == 0x00 and "payload" in frame:
                    # 8-byte "firmware echo" reply to keep-alive ping
                    self._decode_firmware_echo(frame)
                # Other status frames (0x7A beacon, 0x40/0x60 blocks) — log only
            elif "payload" in frame:
                # Bulk DT1 reply (sync response) — iterate each payload byte
                self._dispatch_bulk_frame(frame)
            elif "value" in frame:
                # Single-value DT1 (knob turn / unsolicited update)
                name = lookup_by_address(sec, type_, addr_hi, addr_lo)
                if name is not None and time.monotonic() > self._write_guard.get(name, 0):
                    self._state[name] = frame["value"]
                    self.parameter_changed.emit(name, frame["value"])

    # ── Device identification ─────────────────────────────────────────────────

    # Roland Bridge Cast MIDI identity codes (family, member).
    # Populated once a confirmed capture is available; unknown codes fall back to
    # displaying the raw family/member hex so they can be reported and added here.
    _ROLAND_DEVICE_NAMES: dict[tuple[int, int], str] = {
        # (family, member): "model name"   ← fill in after first confirmed capture
        # (0x????, 0x????): "Bridge Cast",
        # (0x????, 0x????): "Bridge Cast X",
    }

    def _decode_identity_reply(self, info: dict) -> None:
        """Emit device_info_updated from a parsed Universal MIDI Identity Reply."""
        family   = info["family"]
        member   = info["member"]
        firmware = info["firmware"]

        model = self._ROLAND_DEVICE_NAMES.get((family, member))
        if model is None:
            model = f"Roland (family=0x{family:04X} member=0x{member:04X})"

        # Roland firmware bytes: try BCD/decimal first, then ASCII, then raw hex.
        fw = firmware
        if all(b < 0x10 for b in fw):
            fw_str = f"{fw[0]}.{fw[1]:02d}"
            if fw[2] or fw[3]:
                fw_str += f".{fw[2]:02d}.{fw[3]:02d}"
        elif all(0x20 <= b < 0x7F for b in fw):
            fw_str = "".join(chr(b) for b in fw).rstrip()
        else:
            fw_str = ".".join(f"{b:02X}" for b in fw)

        log.info(
            "Device identity: %s  firmware: %s  (family=0x%04X member=0x%04X raw_fw=%s)",
            model, fw_str, family, member, fw,
        )
        self.device_info_updated.emit(model, fw_str)

    # Known model codes from STATUS type=0x00 firmware echo.
    # V1 layout (8-byte payload): model_code at payload[4].
    # V2 layout (7-byte payload): model_code at payload[3] — build MSB at payload[1]
    # pushes model_code one position earlier and removes the trailing padding byte.
    _ECHO_MODEL_CODES: dict[int, str] = {
        0x09: "Bridge Cast",
        0x03: "Bridge Cast V2",
    }

    def _decode_firmware_echo(self, frame: dict) -> None:
        """Decode the STATUS type=0x00 firmware echo and emit device_info_updated.

        Two payload layouts exist depending on firmware generation:
          V1 (8 bytes): [minor, 0x00, build, 0x00, model_code, ...]
          V2 (7 bytes): [minor, build_hi, build_lo, model_code, ...]
        V2 uses Roland's standard 7-bit MSB/LSB encoding for the build number
        and drops the inter-byte padding, shifting model_code from index 4 to 3.
        """
        payload = frame.get("payload", ())
        if len(payload) < 4:
            return

        major = frame["addr_lo"]
        minor = payload[0]

        if len(payload) >= 8:
            # V1 layout: build is a single byte, model_code at index 4
            build      = payload[2]
            model_code = payload[4]
        else:
            # V2 layout: build is MSB/LSB at [1][2], model_code at index 3
            build      = (payload[1] << 7) | payload[2]
            model_code = payload[3]

        firmware = f"{major}.{minor:02d} ({build})"
        model    = self._ECHO_MODEL_CODES.get(model_code, f"Unknown (code=0x{model_code:02X})")

        info = (model, firmware)
        if info == self._device_info:
            return
        self._device_info = info

        log.info("Device: %s  Firmware: %s  (model_code=0x%02X)", model, firmware, model_code)
        self.device_info_updated.emit(model, firmware)

    # ── Bulk DT1 dispatcher ───────────────────────────────────────────────────

    def _dispatch_bulk_frame(self, frame: dict) -> None:
        """Dispatch each byte in a bulk DT1 payload as an individual parameter update."""
        sec = frame["section"]
        type_ = frame["type"]
        base_hi = frame["addr_hi"]

        # SECTION_SYNC_10 carries Voice FX preset name strings — handle separately.
        if sec == C.SECTION_SYNC_10:
            self._handle_voice_preset_name_frame(frame)
            return

        # SECTION_SYNC_11 carries Game EQ preset slot names (same encoding).
        if sec == C.SECTION_SYNC_11:
            self._handle_game_eq_preset_name_frame(frame)
            return

        # Per-profile TYPE_SWITCH at addr=0x00 starts with the profile name in the
        # first 18 bytes (addr 0x00–0x11), using the same swapped-pair +
        # addr_lo-as-first-byte encoding as SECTION_SYNC_10.  The remaining bytes
        # (addr 0x12+) are switch params but have no REGISTRY entries for per-profile
        # sections, so we handle the frame here and return without dispatching further.
        if (C.SECTION_PROFILE_FIRST <= sec <= C.SECTION_PROFILE_LAST
                and type_ == C.TYPE_SWITCH
                and base_hi == 0x00):
            self._handle_profile_name_frame(frame)
            return

        # frame["addr_lo"] is unreliable in bulk responses — some types (e.g. SW)
        # carry a non-zero value there that has no addr meaning.  All registered
        # parameters use addr_lo=0x00, so we hard-code that here.
        now = time.monotonic()
        updated = 0
        payload = frame["payload"]
        _HIBIT_ADDRS = {
            C.ADDR_GAME_VSURROUND_SURROUND_ANGLE,
            C.ADDR_GAME_VSURROUND_BACK_ANGLE,
        }
        for offset, value in enumerate(payload):
            addr_hi = base_hi + offset
            # Surround/back angles (91°–179°) store the high bit in the byte at
            # addr-1 (the low 7 bits sit at the param address).  Reconstruct the
            # full degree: degrees = (prev_byte << 7) | value.  (Using addr+1 here
            # mis-reads the *next* angle's high bit, e.g. surround 115 → 243.)
            if addr_hi in _HIBIT_ADDRS:
                hi_bit = payload[offset - 1] if offset >= 1 else 0
                value = (hi_bit << 7) | value
            name = lookup_by_address(sec, type_, addr_hi, 0x00)
            if name is not None and now > self._write_guard.get(name, 0):
                self._state[name] = value
                self.parameter_changed.emit(name, value)
                updated += 1
        log.debug("Bulk DT1 sec=0x%02x type=0x%02x base=0x%02x payload=%d → %d params",
                  sec, type_, base_hi, len(frame["payload"]), updated)

    def _handle_voice_preset_name_frame(self, frame: dict) -> None:
        """Decode a preset name from a SECTION_SYNC_10 bulk reply.

        Encoding: swapped byte pairs — each 2-byte chunk [hi, lo] encodes two
        ASCII characters as chr(lo) then chr(hi).  Confirmed 2026-05-27.
        """
        type_ = frame["type"]
        slot = type_ // 0x10
        if not (0 <= slot <= 4):
            log.debug("SECTION_SYNC_10: unexpected type 0x%02x (slot=%d)", type_, slot)
            return
        # addr_lo carries the first encoded name byte on the wire; prepend it.
        first_byte = frame.get("addr_lo", 0)
        payload = (first_byte,) + frame.get("payload", ())
        # Name region: addr 0x00–0x11 (max VOICE_FX_PRESET_NAME_MAX = 18 bytes = 9 pairs)
        name_bytes = C.VOICE_FX_PRESET_NAME_MAX
        chars: list[str] = []
        for i in range(0, min(name_bytes, len(payload) - 1), 2):
            hi = payload[i]      # second char of pair
            lo = payload[i + 1]  # first char of pair
            if lo == 0 and hi == 0:
                break
            if 0x20 <= lo <= 0x7E:
                chars.append(chr(lo))
            if hi != 0 and 0x20 <= hi <= 0x7E:
                chars.append(chr(hi))
        name = "".join(chars).strip()
        if not name:
            name = f"Preset {slot + 1}"
        if self._voice_preset_names[slot] != name:
            self._voice_preset_names[slot] = name
            log.debug("Voice FX preset %d name: %r", slot, name)
        self.voice_preset_names_updated.emit(list(self._voice_preset_names))

    def _handle_game_eq_preset_name_frame(self, frame: dict) -> None:
        """Decode a Game EQ preset slot name from a SECTION_SYNC_11 bulk reply.

        Identical swapped-pair encoding to SECTION_SYNC_10 (Voice FX), with the
        first encoded byte in addr_lo.  Slot = type // 0x10.  Confirmed 2026-06-01.
        """
        type_ = frame["type"]
        slot = type_ // 0x10
        if not (0 <= slot <= 4):
            log.debug("SECTION_SYNC_11: unexpected type 0x%02x (slot=%d)", type_, slot)
            return
        first_byte = frame.get("addr_lo", 0)
        payload = (first_byte,) + frame.get("payload", ())
        chars: list[str] = []
        for i in range(0, min(C.GAME_EQ_PRESET_NAME_MAX, len(payload) - 1), 2):
            hi = payload[i]
            lo = payload[i + 1]
            if lo == 0 and hi == 0:
                break
            if 0x20 <= lo <= 0x7E:
                chars.append(chr(lo))
            if hi != 0 and 0x20 <= hi <= 0x7E:
                chars.append(chr(hi))
        name = "".join(chars).strip()
        if not name:
            name = f"Game EQ {slot + 1}"
        if self._game_eq_preset_names[slot] != name:
            self._game_eq_preset_names[slot] = name
            log.debug("Game EQ preset %d name: %r", slot, name)
        self.game_eq_preset_names_updated.emit(list(self._game_eq_preset_names))

    def _handle_profile_name_frame(self, frame: dict) -> None:
        """Decode a profile name from a per-profile TYPE_SWITCH bulk reply.

        Profile names live at addr 0x00–0x11 of the TYPE_SWITCH block in
        SECTION_PROFILE_* (sec=0x20–0x24).  Encoding is identical to
        SECTION_SYNC_10: swapped byte pairs with the first encoded byte in
        addr_lo (data[12]).  Slot = sec − SECTION_PROFILE_FIRST.
        Confirmed 2026-05-27 from ProfileMemory JSON + load-defaults capture.
        """
        sec  = frame["section"]
        slot = sec - C.SECTION_PROFILE_FIRST
        if not (0 <= slot <= 4):
            log.debug("SECTION_PROFILE: unexpected section 0x%02x (slot=%d)", sec, slot)
            return
        # addr_lo carries the first encoded name byte on the wire; prepend it.
        first_byte = frame.get("addr_lo", 0)
        payload = (first_byte,) + frame.get("payload", ())
        name_bytes = C.VOICE_FX_PRESET_NAME_MAX  # same 18-char cap
        chars: list[str] = []
        for i in range(0, min(name_bytes, len(payload) - 1), 2):
            hi = payload[i]      # second char of pair
            lo = payload[i + 1]  # first char of pair
            if lo == 0 and hi == 0:
                break
            if 0x20 <= lo <= 0x7E:
                chars.append(chr(lo))
            if hi != 0 and 0x20 <= hi <= 0x7E:
                chars.append(chr(hi))
        name = "".join(chars).strip()
        if not name:
            name = f"Profile {slot + 1}"
        if self._profile_names[slot] != name:
            self._profile_names[slot] = name
            log.debug("Profile %d name: %r", slot, name)
        self.profile_names_updated.emit(list(self._profile_names))

    # ── State vector decoder (heartbeat reply) ───────────────────────────────
    # FW 1.06: 137-byte wire frame (135 mido bytes, 121-byte payload).
    # FW 3.00: 127-byte wire frame (125 mido bytes, 111-byte payload).
    # Payload slot offsets are identical; the frame is simply shorter at the tail.
    # Slots beyond the frame end (e.g. OUT_LINE on FW 3.00) return (0, 0) via the
    # bounds check in slot() below.

    def _decode_state_vector(self, raw: tuple[int, ...]) -> None:
        """
        Decode the DT1 state vector into level meter values.

        raw is the mido data tuple (F0/F7 stripped).
        Wire indices are converted via: mido[i] = wire[i+1].
        Range per slot: 0–16383 (14-bit, (hi << 7) | lo).
        """
        if len(raw) < 125:
            return

        def slot(wire_idx: int) -> tuple[int, int]:
            m = wire_idx - 1  # mido index
            if m + 3 >= len(raw):
                return 0, 0
            L = (raw[m] << 7) | raw[m + 1]
            R = (raw[m + 2] << 7) | raw[m + 3]
            return L, R

        def slot2(wire_idx: int) -> int:
            m = wire_idx - 1  # mido index
            if m + 1 >= len(raw):
                return 0
            return (raw[m] << 7) | raw[m + 1]

        meters = {
            # Direct/raw mic (wire 109–110, 2-byte mono, pre-bus)
            "raw_mic":  slot2(C.METER_IDX_RAW_MIC),
            # Streaming inputs (wire 45–68)
            "st_mic":   slot(C.METER_IDX_ST_MIC),
            "st_aux":   slot(C.METER_IDX_ST_AUX),
            "st_chat":  slot(C.METER_IDX_ST_CHAT),
            "st_game":  slot(C.METER_IDX_ST_GAME),
            "st_music": slot(C.METER_IDX_ST_MUSIC),
            "st_sys":   slot(C.METER_IDX_ST_SYS),
            # Personal inputs (wire 69–108)
            "ps_sfx":   slot(C.METER_IDX_PS_SFX),
            "ps_mic":   slot(C.METER_IDX_PS_MIC),
            "ps_aux":   slot(C.METER_IDX_PS_AUX),
            "ps_chat":  slot(C.METER_IDX_PS_CHAT),
            "ps_game":  slot(C.METER_IDX_PS_GAME),
            "ps_music": slot(C.METER_IDX_PS_MUSIC),
            "ps_sys":   slot(C.METER_IDX_PS_SYS),
            # Output block (wire 111–130)
            "out_stream": slot(C.METER_IDX_OUT_STREAM),
            "out_submix": slot(C.METER_IDX_OUT_SUBMIX),
            # OUT_PHONES: FW 3.00 (125-byte frame) — L only present here; R from cache.
            # FW 1.06 (135-byte frame) — full 4-byte stereo slot present.
            "out_phones": (
                (slot2(C.METER_IDX_OUT_PHONES), self._cached_phones_R)
                if len(raw) < 135 else slot(C.METER_IDX_OUT_PHONES)
            ),
            # OUT_LINE: FW 3.00 — trimmed from main frame; use cached value from 0x10/0x70.
            # FW 1.06 — full 4-byte stereo slot at wire index 127.
            "out_line": (
                self._cached_line
                if len(raw) < 135 else slot(C.METER_IDX_OUT_LINE)
            ),
        }
        self.meter_updated.emit(meters)

        # Game EQ spectrum analyzer status: mido[35] (wire byte 36) reads 0x01
        # while the analyzer is active, 0x00 otherwise (confirmed 2026-06-01).
        # Echo it as the eq_analyzer parameter so a UI toggle stays in sync,
        # unless we just wrote it ourselves (write-guard window).
        analyzer = 1 if (len(raw) > 35 and raw[35]) else 0
        if (self._state.get("eq_analyzer") != analyzer
                and time.monotonic() > self._write_guard.get("eq_analyzer", 0.0)):
            self._state["eq_analyzer"] = analyzer
            self.parameter_changed.emit("eq_analyzer", analyzer)

    def _decode_status10_continuation(self, frame: dict) -> None:
        """Cache OUT_PHONES R and OUT_LINE from the FW 3.00 continuation frame.

        FW 3.00 splits the state vector across two DT1 frames per tick.  The
        second frame (sec=0x01, type=0x10, addr_hi=0x70) carries the data that
        was trimmed when Roland shortened the wire frame from 137→127 bytes:

          addr_lo        = OUT_PHONES R hi byte
          payload[0]     = OUT_PHONES R lo byte
          payload[1..2]  = OUT_LINE L  (hi, lo)
          payload[3..4]  = OUT_LINE R  (hi, lo)

        The cached values are consumed by _decode_state_vector() on the same tick.
        Confirmed 2026-05-29 from phones_output_midi.txt capture.
        """
        addr_lo = frame.get("addr_lo", 0)
        payload = frame.get("payload", ())
        if not payload:
            return
        self._cached_phones_R = (addr_lo << 7) | payload[0]
        if len(payload) >= 5:
            self._cached_line = (
                (payload[1] << 7) | payload[2],
                (payload[3] << 7) | payload[4],
            )

    # ── Strip assignment helpers ──────────────────────────────────────────────

    _HW_STRIP_PARAM_INDEX: dict[str, int] = {
        "hw_strip_1_ch": 0, "hw_strip_2_ch": 1,
        "hw_strip_3_ch": 2, "hw_strip_4_ch": 3,
    }

    def _on_strip_param_changed(self, name: str, value: int) -> None:
        idx = self._HW_STRIP_PARAM_INDEX.get(name)
        if idx is not None:
            ch = C.HW_STRIP_VALUE_CH.get(value)
            if ch is not None:
                self.hw_strip_assignment_changed.emit(idx, ch)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _send_raw(self, data: tuple[int, ...]) -> None:
        try:
            self._transport.send_sysex(data)
        except Exception as exc:
            if self._is_connected:
                log.warning("MIDI send failed: %s — device lost", exc)
                self.status_message.emit("Device lost — MIDI port closed unexpectedly")
                self.disconnect_device()
            return
        self.sysex_tx.emit(data)
