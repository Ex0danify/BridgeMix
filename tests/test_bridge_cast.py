"""Tests for the protocol-encoding paths of ``BridgeCast``.

These exercise the synchronous write methods (``set_parameter`` and
``set_vsurround_angle``) without any MIDI hardware: the real transport is
replaced with a recorder that captures the mido tuples that would be sent.
The frames are decoded with ``sysex.parse`` so assertions read in protocol
terms (section / type / address / value) rather than raw byte offsets.
"""
from __future__ import annotations

import pytest

import bridgemix.device.constants as C
from bridgemix.device.bridge_cast import BridgeCast
from bridgemix.device.parameters import REGISTRY
from bridgemix.midi import sysex


class _RecordingTransport:
    """Stand-in for MidiTransport that just records sent frames."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, ...]] = []

    def send_sysex(self, data: tuple[int, ...]) -> None:
        self.sent.append(data)


@pytest.fixture
def device(qapp):
    """A BridgeCast wired to a recording transport (no real MIDI ports)."""
    dev = BridgeCast()
    dev._transport = _RecordingTransport()
    return dev


# ── Frame-building helpers (device → host) ────────────────────────────────────

_ROLAND_HEADER = (0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11)


def _bulk_dt1(section, type_, addr_hi, addr_lo, payload):
    """A DT1 frame with a multi-byte payload (len > 15 ⇒ parse() sets 'payload').

    The trailing checksum byte is not validated by parse(), so 0x00 is fine.
    """
    return (*_ROLAND_HEADER, 0x12, 0x7F, section, type_, addr_hi, addr_lo,
            *payload, 0x00)


def _encode_name(text):
    """Encode a name the way the device sends it back: swapped byte pairs with
    the first encoded byte carried in addr_lo.

    The decoder reads each [hi, lo] pair as chr(lo) then chr(hi), and prepends
    addr_lo as payload[0]. So for the flat byte stream b0,b1,b2,b3,… the decoder
    emits chr(b1),chr(b0),chr(b3),chr(b2),… Returns (addr_lo, payload_tuple).
    """
    raw = text.encode("ascii")
    stream = []
    for i in range(0, len(raw), 2):
        first = raw[i]
        second = raw[i + 1] if i + 1 < len(raw) else 0
        stream += [second, first]   # swapped within the pair
    stream += [0, 0]                 # null pair terminates decoding
    return stream[0], tuple(stream[1:])


# ── set_parameter ───────────────────────────────────────────────────────────

def test_set_parameter_sends_correct_frame_and_updates_state(device):
    p = REGISTRY["st_mic_vol"]
    received = []
    device.parameter_changed.connect(lambda n, v: received.append((n, v)))

    device.set_parameter("st_mic_vol", 0x40)

    assert len(device._transport.sent) == 1
    frame = sysex.parse(device._transport.sent[0])
    assert frame["section"] == p.section
    assert frame["type"] == p.param_type
    assert frame["addr_hi"] == p.addr_hi
    assert frame["addr_lo"] == p.addr_lo
    assert frame["value"] == 0x40
    # State cache and the change signal both reflect the write.
    assert device.get_parameter("st_mic_vol") == 0x40
    assert received == [("st_mic_vol", 0x40)]


def test_set_parameter_rejects_out_of_range(device):
    before = device.get_parameter("st_mic_vol")
    device.set_parameter("st_mic_vol", 999)  # max is 127
    assert device._transport.sent == []
    assert device.get_parameter("st_mic_vol") == before


def test_set_parameter_rejects_read_only(device):
    # stream_vol is a hardware-knob mirror, registered read_only.
    assert REGISTRY["stream_vol"].read_only
    device.set_parameter("stream_vol", 10)
    assert device._transport.sent == []


def test_set_parameter_ignores_unknown_name(device):
    device.set_parameter("not_a_real_param", 1)
    assert device._transport.sent == []


# ── set_vsurround_angle ───────────────────────────────────────────────────────

def test_vsurround_angle_max_wraps_high_bit_into_addr_lo(device):
    # PROTOCOL.md: at 179° the wire is addr_lo=0x01, value=0x33 (the high bit of
    # the angle spills into addr_lo because MIDI data bytes are 7-bit).
    device.set_vsurround_angle("game_vsurround_surround_angle", 179)

    frame = sysex.parse(device._transport.sent[-1])
    assert frame["addr_lo"] == 0x01
    assert frame["value"] == 0x33
    assert device.get_parameter("game_vsurround_surround_angle") == 179


def test_vsurround_angle_below_128_keeps_addr_lo_zero(device):
    device.set_vsurround_angle("game_vsurround_surround_angle", 100)
    frame = sysex.parse(device._transport.sent[-1])
    assert frame["addr_lo"] == 0x00
    assert frame["value"] == 100


def test_vsurround_angle_rejects_out_of_range(device):
    device.set_vsurround_angle("game_vsurround_surround_angle", 200)  # max 179
    assert device._transport.sent == []


# ── Incoming single-value DT1 (knob turn / unsolicited update) ────────────────

def test_incoming_single_value_updates_state_and_emits(device):
    received = []
    device.parameter_changed.connect(lambda n, v: received.append((n, v)))

    p = REGISTRY["st_mic_vol"]
    frame = sysex.build_write(p.section, p.param_type, p.addr_hi, p.addr_lo, 0x55)
    device._on_sysex_received(frame)

    assert device.get_parameter("st_mic_vol") == 0x55
    assert received == [("st_mic_vol", 0x55)]


def test_incoming_update_suppressed_during_write_guard(device):
    # A host write arms a 500 ms guard; a device frame arriving inside that
    # window must not clobber the value we just set.
    device.set_parameter("st_mic_vol", 0x10)
    received = []
    device.parameter_changed.connect(lambda n, v: received.append((n, v)))

    p = REGISTRY["st_mic_vol"]
    stale = sysex.build_write(p.section, p.param_type, p.addr_hi, p.addr_lo, 0x7F)
    device._on_sysex_received(stale)

    assert device.get_parameter("st_mic_vol") == 0x10   # unchanged
    assert received == []


def test_incoming_unknown_address_is_ignored(device):
    # No REGISTRY entry for this address ⇒ no crash, no state change.
    received = []
    device.parameter_changed.connect(lambda n, v: received.append((n, v)))
    frame = sysex.build_write(C.SECTION_CHANNEL, C.TYPE_FADER, 0x7E, 0x00, 0x01)
    device._on_sysex_received(frame)
    assert received == []


def test_garbage_frame_does_not_raise(device):
    device._on_sysex_received((0x00, 0x01, 0x02))   # too short / non-Roland
    device._on_sysex_received(())                    # empty


# ── Bulk DT1 dispatch ─────────────────────────────────────────────────────────

def test_bulk_frame_dispatches_consecutive_addresses(device):
    # TYPE_FADER stream volumes sit at addr 0x00 (st_mic_vol) and 0x02
    # (st_aux_vol); a bulk payload indexes by offset from the base address.
    updates = {}
    device.parameter_changed.connect(lambda n, v: updates.__setitem__(n, v))

    payload = (0x11, 0x00, 0x22)   # offset 0 → st_mic_vol, offset 2 → st_aux_vol
    frame = _bulk_dt1(C.SECTION_CHANNEL, C.TYPE_FADER, 0x00, 0x00, payload)
    device._on_sysex_received(frame)

    assert updates["st_mic_vol"] == 0x11
    assert updates["st_aux_vol"] == 0x22


def test_bulk_frame_reconstructs_vsurround_high_bit(device):
    # In a bulk dump the surround angle's high bit lives in the *preceding* byte.
    # base 0x14 + offset 2 == 0x16 (ADDR_GAME_VSURROUND_SURROUND_ANGLE); the byte
    # at offset 1 holds the high bit, so degrees = (1 << 7) | value.
    updates = {}
    device.parameter_changed.connect(lambda n, v: updates.__setitem__(n, v))

    payload = (0x00, 0x01, 0x33)   # offset1=high bit, offset2=0x33 ⇒ 179°
    frame = _bulk_dt1(C.SECTION_CHANNEL, C.TYPE_GAME_FX, 0x14, 0x00, payload)
    device._on_sysex_received(frame)

    assert updates["game_vsurround_surround_angle"] == 179


# ── Name decoders ─────────────────────────────────────────────────────────────

def test_voice_preset_name_decoded_from_sync10(device):
    captured = []
    device.voice_preset_names_updated.connect(captured.append)

    addr_lo, payload = _encode_name("Robot")
    # slot 2 ⇒ type byte = 2 * 0x10
    frame = _bulk_dt1(C.SECTION_SYNC_10, 0x20, 0x00, addr_lo, payload)
    device._on_sysex_received(frame)

    assert captured[-1][2] == "Robot"


def test_game_eq_preset_name_decoded_from_sync11(device):
    captured = []
    device.game_eq_preset_names_updated.connect(captured.append)

    addr_lo, payload = _encode_name("FPS")
    frame = _bulk_dt1(C.SECTION_SYNC_11, 0x00, 0x00, addr_lo, payload)  # slot 0
    device._on_sysex_received(frame)

    assert captured[-1][0] == "FPS"


def test_profile_name_decoded_from_profile_section(device):
    captured = []
    device.profile_names_updated.connect(captured.append)

    addr_lo, payload = _encode_name("Stream")
    # SECTION_PROFILE_FIRST + 3 ⇒ slot 3, TYPE_SWITCH name block at addr 0x00
    frame = _bulk_dt1(C.SECTION_PROFILE_FIRST + 3, C.TYPE_SWITCH, 0x00, addr_lo, payload)
    device._on_sysex_received(frame)

    assert captured[-1][3] == "Stream"


# ── State vector (heartbeat reply) ────────────────────────────────────────────

def _state_vector(mido_bytes=None, length=125):
    """Build a STATUS type=0x10 addr=0x00 state-vector frame of `length` bytes.

    `mido_bytes` maps mido index → value for the meter slots under test.
    """
    raw = [0] * length
    raw[0], raw[1] = 0x41, 0x10
    raw[7], raw[8] = 0x12, 0x7F
    raw[9], raw[10], raw[11], raw[12] = C.SECTION_STATUS, C.SUBTYPE_STATUS_10, 0x00, 0x00
    for idx, val in (mido_bytes or {}).items():
        raw[idx] = val
    return tuple(raw)


def test_state_vector_decodes_meter_pair(device):
    meters = []
    device.meter_updated.connect(meters.append)

    # st_mic occupies mido indices m..m+3 where m = METER_IDX_ST_MIC - 1.
    m = C.METER_IDX_ST_MIC - 1
    frame = _state_vector({m: 0x01, m + 1: 0x02, m + 2: 0x00, m + 3: 0x05})
    device._on_sysex_received(frame)

    assert meters[-1]["st_mic"] == ((0x01 << 7) | 0x02, 0x05)


def test_state_vector_echoes_eq_analyzer_flag(device):
    received = []
    device.parameter_changed.connect(lambda n, v: received.append((n, v)))
    # Byte 35 (mido) mirrors the analyzer on/off flag.
    device._on_sysex_received(_state_vector({35: 0x01}))
    assert ("eq_analyzer", 1) in received


def test_state_vector_too_short_is_ignored(device):
    meters = []
    device.meter_updated.connect(meters.append)
    device._on_sysex_received(_state_vector(length=100))  # < 125 ⇒ bail out
    assert meters == []


def test_status10_continuation_caches_phones_and_line(device):
    # sec=0x01 type=0x10 addr_hi=0x70: addr_lo + payload carry the trimmed tail.
    frame = _bulk_dt1(C.SECTION_STATUS, C.SUBTYPE_STATUS_10,
                      C.METER_ADDR_CONTINUATION, 0x01, (0x02, 0x03, 0x04, 0x05, 0x06))
    device._on_sysex_received(frame)

    assert device._cached_phones_R == (0x01 << 7) | 0x02
    assert device._cached_line == ((0x03 << 7) | 0x04, (0x05 << 7) | 0x06)


# ── Device identification ─────────────────────────────────────────────────────

def test_identity_reply_emits_device_info(device):
    captured = []
    device.device_info_updated.connect(lambda m, f: captured.append((m, f)))

    # 7E dev 06 02 mfr fam_lsb fam_msb mem_lsb mem_msb fw0..fw3
    reply = (0x7E, 0x10, 0x06, 0x02, 0x41, 0x02, 0x01, 0x04, 0x03, 0x03, 0x00, 0x00, 0x00)
    device._on_sysex_received(reply)

    assert len(captured) == 1
    model, fw = captured[0]
    assert "0x" in model          # unknown family/member ⇒ raw hex fallback
    assert fw == "3.00"           # BCD-style firmware (3, 0)


def test_firmware_echo_modern_fw3_emits_once_then_dedupes(device):
    # Modern firmware (FW 3.00) uses the V2 echo layout: a 7-byte payload where
    # the build number is Roland 7-bit MSB/LSB at payload[1:3] and model_code is
    # at payload[3] (no inter-byte padding, unlike the legacy V1 8-byte layout).
    #   major = addr_lo = 3, minor = payload[0] = 0  ⇒ "3.00"
    #   build = (payload[1] << 7) | payload[2] = 115
    #   model_code 0x03 ⇒ "Bridge Cast V2"
    captured = []
    device.device_info_updated.connect(lambda m, f: captured.append((m, f)))

    payload = (0x00, 0x00, 0x73, 0x03, 0x00, 0x00)   # 6 bytes (< 8 ⇒ V2 branch)
    echo = _bulk_dt1(C.SECTION_STATUS, 0x00, 0x00, 0x03, payload)  # major=3

    device._on_sysex_received(echo)
    device._on_sysex_received(echo)   # identical ⇒ no second emit

    assert captured == [("Bridge Cast V2", "3.00 (115)")]


def test_firmware_echo_legacy_v1_layout_branch(device):
    # Branch coverage for the older V1 8-byte layout (build as a single byte at
    # payload[2], model_code at payload[4]). Not a target device, but the decode
    # path still exists, so keep it exercised.
    captured = []
    device.device_info_updated.connect(lambda m, f: captured.append((m, f)))

    payload = (0x06, 0x00, 0x73, 0x00, 0x09, 0x00, 0x00, 0x00)  # 8 bytes ⇒ V1 branch
    echo = _bulk_dt1(C.SECTION_STATUS, 0x00, 0x00, 0x01, payload)  # major=1

    device._on_sysex_received(echo)

    assert captured == [("Bridge Cast", "1.06 (115)")]
