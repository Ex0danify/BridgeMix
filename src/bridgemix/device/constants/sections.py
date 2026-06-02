"""
Protocol framing constants: Roland SysEx header, section bytes, type bytes,
heartbeat/status addresses, sync read sizes, USB device IDs, channel labels.
"""

# ── Fixed header (bytes 1-15, without F0/F7) ─────────────────────────────────
ROLAND_HEADER: tuple[int, ...] = (0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11, 0x12, 0x7F)

CMD_WRITE: int = 0x12  # DT1 - Data Set 1
CMD_READ:  int = 0x11  # RQ1 - Request Data

# ── Section bytes ─────────────────────────────────────────────────────────────
SECTION_STATUS:   int = 0x01   # Heartbeat / keep-alive (host → device, 50 ms)
SECTION_GLOBAL:   int = 0x02
SECTION_CHANNEL:  int = 0x03
SECTION_VOICE_FX: int = 0x7F   # Voice FX preset block (confirmed 2026-05-13)

# SECTION_SYNC_10 — Voice FX preset bank (5 slots, type byte = slot index×0x10)
# SECTION_SYNC_11 — Game EQ preset bank  (5 slots, type byte = slot index×0x10)
# SECTION_SYNC_12 — purpose confirmed unknown — all-zero in all captures
# SECTION_SYNC_30 — unknown (2026-05-22); 27-byte all-zero payload
SECTION_SYNC_10: int = 0x10
SECTION_SYNC_11: int = 0x11
SECTION_SYNC_12: int = 0x12
SECTION_SYNC_30: int = 0x30

# ── Heartbeat addresses (SECTION_STATUS) ──────────────────────────────────────
SUBTYPE_STATUS_10: int = 0x10
SUBTYPE_STATUS_11: int = 0x11

ADDR_STATUS_00: int = 0x00
ADDR_STATUS_10: int = 0x10   # RX enable / keep-alive latch (val=01 enable, val=00 disable)
ADDR_STATUS_40: int = 0x40
ADDR_STATUS_60: int = 0x60
ADDR_STATUS_70: int = 0x70
ADDR_STATUS_7A: int = 0x7A

RX_ENABLE_ON:  int = 0x01
RX_ENABLE_OFF: int = 0x00

# Seconds to wait after sending RX-disable, before closing the MIDI port, so the
# device stops streaming and the input buffer drains.  Prevents the native
# rtmidi close_port() deadlock when disconnecting mid-stream (see transport.py).
RX_DRAIN_BEFORE_CLOSE_S: float = 0.2

# ── Type bytes ────────────────────────────────────────────────────────────────
TYPE_SWITCH:        int = 0x00   # on/off parameters
TYPE_MIC_FX:        int = 0x01   # mic "Clean Up" effect parameters
TYPE_VOICE:         int = 0x02   # voice effect parameters
TYPE_CHAT_FX:       int = 0x04   # chat channel effect parameters
TYPE_GAME_FX:       int = 0x05   # game channel FX parameters (EQ, Limiter, Virtual Surround)
TYPE_DELAY:         int = 0x06   # output delay parameters
TYPE_FADER:         int = 0x07   # volume/fader parameters
TYPE_HOTKEY:        int = 0x09   # Hot Key function (confirmed 2026-05-23)
TYPE_VOICE_FX:      int = 0x7F   # Voice FX preset selection

# type=0x0A — unknown; multi-addr, all zero in idle captures
TYPE_UNKNOWN_0A: int = 0x0A
# type=0x0B — unknown; addr 0x20/0x50, all zero
TYPE_UNKNOWN_0B: int = 0x0B
# type=0x0C — unknown; same read pattern as 0x0B
TYPE_UNKNOWN_0C: int = 0x0C
# type=0x0D — La2a tube compressor + NS Expander (confirmed 2026-05-27)
TYPE_MIC_LA2A: int = 0x0D
# type=0x0E — NS Expander + Compressor Modern (confirmed 2026-05-27)
TYPE_MIC_FX_EXT: int = 0x0E

# SECTION_GLOBAL additional type blocks
TYPE_GLOBAL_SFX_A: int = 0x01   # SFX A Volume / Filename block
TYPE_GLOBAL_SFX_B: int = 0x02   # SFX B Volume / Global voice/SFX preset block

# ── USB product IDs for device model detection ────────────────────────────────
USB_VENDOR_ID:             str = "0582"
USB_PRODUCT_BRIDGECAST:    str = "0231"   # Bridge Cast (original)
USB_PRODUCT_BRIDGECAST_V2: str = "031e"   # Bridge Cast V2 / X

# ── Channel labels ────────────────────────────────────────────────────────────
CHANNEL_LABELS: tuple[str, str, str, str] = ("Mic", "Aux", "Chat", "Game")
CAPTURE_LABELS: tuple[str, str, str] = ("StreamMix", "Mic", "SFX")

# ── Sync RQ1 bulk read sizes (confirmed 2026-05-19/26/27) ────────────────────
SYNC_RQ1_GLOBAL_SIZE:         int = 0x12   # Global settings
SYNC_RQ1_FADER_SIZE:          int = 0x6A   # Fader + mute
SYNC_RQ1_SWITCH_SIZE:         int = 0x4A   # Switch block
SYNC_RQ1_DELAY_SIZE:          int = 0x04   # Output delay
SYNC_RQ1_LED_SIZE:            int = 0x40   # LED colours
SYNC_RQ1_MIC_FX_SIZE:         int = 0x7C   # Mic Clean Up + 10-band EQ (type=0x01)
SYNC_RQ1_VOICE_SIZE:          int = 0x46   # Voice FX + Reverb (type=0x02)
SYNC_RQ1_CHAT_FX_SIZE:        int = 0x1C   # Chat FX effects (type=0x04)
SYNC_RQ1_GAME_FX_SIZE:        int = 0x6E   # Game EQ + Limiter + VSurround (type=0x05)
SYNC_RQ1_HOTKEY_SIZE:         int = 0x38   # Hot Key assignments (type=0x09)
SYNC_RQ1_MIC_EXT_SIZE:        int = 0x2A   # NS Expander + Compressor Modern (type=0x0E)
SYNC_RQ1_VOICE_FX_PRESET_SIZE: int = 0x46  # Voice FX preset slot (same as SYNC_RQ1_VOICE_SIZE)
SYNC_RQ1_GAME_EQ_PRESET_SIZE: int = 0x46   # Game EQ preset slot (SECTION_SYNC_11, name + curve)
SYNC_RQ1_PROFILE_NAME_SIZE:   int = 0x12   # Profile name (18 bytes = PROFILE_NAME_MAX)
