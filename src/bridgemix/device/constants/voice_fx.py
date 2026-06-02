"""
Voice effect and reverb constants.

All addresses use SECTION_CHANNEL (0x03) with TYPE_VOICE (0x02),
or SECTION_VOICE_FX (0x7F) with TYPE_VOICE_FX (0x7F) for preset management.
"""

# ── Voice effects  (SECTION_CHANNEL, TYPE_VOICE = 0x02) ──────────────────────
ADDR_VOICE_PITCH:  int = 0x20   # range 0x00–0x7F
ADDR_VOICE_FORMAT: int = 0x22   # range 0x00–0x7F
ADDR_VOICE_MODE:   int = 0x2C
VOICE_MODE_AVATAR: int = 0x00
VOICE_MODE_SING:   int = 0x01

VOICE_MIN:     int = 0x00
VOICE_MAX:     int = 0x7F
VOICE_DEFAULT: int = 0x40

# ── Reverb  (SECTION_CHANNEL, TYPE_VOICE = 0x02) ─────────────────────────────
ADDR_REVERB_SWITCH: int = 0x40
REVERB_SWITCH_OFF:  int = 0x00
REVERB_SWITCH_ON:   int = 0x01

ADDR_REVERB_SIZE:   int = 0x42
REVERB_SIZE_MIN:    int = 0x00
REVERB_SIZE_MAX:    int = 0x09

ADDR_REVERB_LEVEL:  int = 0x44   # confirmed (2026-05-13)
REVERB_LEVEL_MIN:   int = 0x00
REVERB_LEVEL_MAX:   int = 0x09

# ── Voice FX preset management  (SECTION_VOICE_FX = 0x7F, TYPE_VOICE_FX = 0x7F) ──
# SELECT a preset slot (val 0–4)
ADDR_VOICE_FX_PRESET:   int = 0x02

# SAVE current live voice state to a slot
ADDR_VOICE_FX_SAVE:     int = 0x08   # confirmed (2026-05-27)

# RESET a slot to factory defaults
ADDR_VOICE_FX_RESET_DEFAULT: int = 0x14  # confirmed (2026-05-28)

# ── Voice FX preset name encoding ─────────────────────────────────────────────
# Names occupy addr 0x00–0x11 (max 18 chars), packed two chars per SysEx frame.
# sec=CHANNEL (0x03), type=VOICE (0x02)
# ADDR_HI = 2 × pair_index; ADDR_LO = char[even]; VALUE = char[odd]
ADDR_VOICE_NAME_START:        int = 0x00
VOICE_FX_PRESET_NAME_MAX:     int = 18   # confirmed (2026-05-27)
ADDR_VOICE_PRESET_NAME_BLOCK: int = 0x00  # confirmed (2026-05-27)
