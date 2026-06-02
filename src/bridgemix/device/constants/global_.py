"""
System and global settings: mix mode, system settings (brightness, phones gain,
indicator type, mute display), SFX volumes, profile management, active profile,
output routing, output delay, hot keys, and CC (MIDI Control Change) numbers.

Sections: SECTION_GLOBAL (0x02) with TYPE_SWITCH (0x00),
          SECTION_CHANNEL (0x03) with TYPE_SWITCH, TYPE_DELAY, TYPE_HOTKEY,
          SECTION_VOICE_FX (0x7F) with TYPE_VOICE_FX for profile save/reset.
"""

# ── Mix mode  (SECTION_GLOBAL, TYPE_SWITCH) ───────────────────────────────────
ADDR_MIX_MODE:     int = 0x02
MIX_MODE_PERSONAL: int = 0x00
MIX_MODE_STREAM:   int = 0x01

# ── Active profile  (SECTION_GLOBAL, TYPE_SWITCH) ────────────────────────────
ADDR_ACTIVE_PROFILE: int = 0x00   # confirmed (2026-05-19); val=0x00–0x04
ACTIVE_PROFILE_MIN:  int = 0x00
ACTIVE_PROFILE_MAX:  int = 0x04   # 5 profiles (0-indexed)

# ── Per-profile section bytes ─────────────────────────────────────────────────
# Sections 0x20–0x24 are per-profile copies of the SECTION_CHANNEL block.
SECTION_PROFILE_0: int = 0x20   # confirmed (2026-05-19)
SECTION_PROFILE_1: int = 0x21
SECTION_PROFILE_2: int = 0x22
SECTION_PROFILE_3: int = 0x23
SECTION_PROFILE_4: int = 0x24
SECTION_PROFILE_FIRST: int = SECTION_PROFILE_0
SECTION_PROFILE_LAST:  int = SECTION_PROFILE_4
SECTION_PROFILE_COUNT: int = 5
SECTION_PROFILES: tuple[int, ...] = (
    SECTION_PROFILE_0, SECTION_PROFILE_1, SECTION_PROFILE_2,
    SECTION_PROFILE_3, SECTION_PROFILE_4,
)

# ── Profile name  (SECTION_PROFILE_*, TYPE_SWITCH = 0x00, addr 0x00–0x11) ────
# 18-byte max, 7-bit ASCII, two chars per DT1 frame (same scheme as voice names).
PROFILE_NAME_MAX: int = 18   # confirmed (2026-05-28)

# ── Profile management  (SECTION_VOICE_FX = 0x7F, TYPE_VOICE_FX = 0x7F) ──────
# SAVE current live state to a slot (val = slot index 0–4)
ADDR_PROFILE_SAVE:          int = 0x06   # confirmed (2026-05-27)
# SELECT a profile slot (sent immediately after save)
ADDR_PROFILE_SELECT_7F:     int = 0x00   # confirmed (2026-05-27)
# RESET a slot to factory defaults
ADDR_PROFILE_RESET_DEFAULT: int = 0x12   # confirmed (2026-05-27)
# FULL-DEVICE factory reset opcode.  Unlike the per-slot resets, the captured
# sequence (2026-06-01) sends two frames with addr_lo/value = 0x55/0x55 then
# 0x7F/0x7F (not addr_lo=0x00/val=slot), so the magic args live in the caller.
ADDR_FACTORY_RESET:         int = 0x10   # confirmed (2026-06-01)

# Unknown TYPE_SWITCH address; sits just after ADDR_GAME_EQ_PRESET (0x34)
ADDR_SWITCH_0x36: int = 0x36   # unverified (2026-05-19); sec=03 type=00; val=0x00 at idle

# ── System settings  (SECTION_GLOBAL, TYPE_SWITCH) ───────────────────────────
ADDR_LED_BRIGHTNESS:    int = 0x04
LED_BRIGHTNESS_MIN:     int = 0x00
LED_BRIGHTNESS_MAX:     int = 0x07
LED_BRIGHTNESS_DEFAULT: int = 0x04

ADDR_PHONES_GAIN:       int = 0x08
PHONES_GAIN_NORMAL:     int = 0x00
PHONES_GAIN_BOOST1:     int = 0x01
PHONES_GAIN_BOOST2:     int = 0x02

ADDR_INDICATOR_TYPE:    int = 0x06
INDICATOR_TYPE_LEVEL:   int = 0x00
INDICATOR_TYPE_METER:   int = 0x01

ADDR_MUTE_DISPLAY:      int = 0x0C
MUTE_DISPLAY_BLINK:     int = 0x00
MUTE_DISPLAY_OFF:       int = 0x01

# ── SFX volumes  (SECTION_GLOBAL) ────────────────────────────────────────────
# A and B share the SAME address (0x00/0x00); they are disambiguated by the
# TYPE byte, not the address — A=TYPE_GLOBAL_SFX_A (0x01), B=TYPE_GLOBAL_SFX_B
# (0x02).  Confirmed from official-app capture (2026-06-01):
#   F0 41 10 .. 12 7F 02 01 00 00 <val> ..   (SFX A: sec=02 type=01 addr=00 00)
#   F0 41 10 .. 12 7F 02 02 00 00 <val> ..   (SFX B: sec=02 type=02 addr=00 00)
# Both constants are 0x00 by design — do not "fix" them to differ.
ADDR_SFX_A_VOL: int = 0x00
ADDR_SFX_B_VOL: int = 0x00
SFX_VOL_MIN:     int = 0x00
# Factory-reset capture (2026-06-01) reports SFX A/B volume = 0x64, so the usable
# range tops out at 0x64 (100), not 0x63, and the factory default is 0x64.
SFX_VOL_MAX:     int = 0x64
SFX_VOL_DEFAULT: int = 0x64

ADDR_SFX_A_FILENAME_START: int = 0x10
ADDR_SFX_A_FILENAME_STEP:  int = 0x02

# ── Output routing  (SECTION_CHANNEL, TYPE_SWITCH = 0x00) ────────────────────
ADDR_LINE_OUT_MODE:        int = 0x42   # confirmed (2026-05-13)
LINE_OUT_MODE_MIC:         int = 0x00
LINE_OUT_MODE_STREAM_MIX:  int = 0x01
LINE_OUT_MODE_PHONES_SYNC: int = 0x02

ADDR_USB_OUT_MODE:         int = 0x44   # confirmed (2026-05-13)
USB_OUT_MODE_MIC:          int = 0x00
USB_OUT_MODE_STREAM_MIX:   int = 0x01

ADDR_SUB_MIX_MODE:         int = 0x48   # confirmed (2026-05-13)
SUB_MIX_MODE_PERSONAL:     int = 0x00
SUB_MIX_MODE_MIC_DRY:      int = 0x01
SUB_MIX_MODE_AUX:          int = 0x02

# ── Output delay  (SECTION_CHANNEL, TYPE_DELAY = 0x06) ───────────────────────
ADDR_OUTPUT_DELAY_SW:     int = 0x00   # confirmed (2026-05-13)
ADDR_OUTPUT_DELAY_AMOUNT: int = 0x02   # confirmed (2026-05-13)
OUTPUT_DELAY_SW_OFF:      int = 0x00
OUTPUT_DELAY_SW_ON:       int = 0x01
OUTPUT_DELAY_AMOUNT_MIN:  int = 0x00
OUTPUT_DELAY_AMOUNT_MAX:  int = 0x3C   # 60 steps

# ── Hot Key  (SECTION_CHANNEL, TYPE_HOTKEY = 0x09) ───────────────────────────
ADDR_HOTKEY_BTN1: int = 0x16

HOTKEY_MOD_NONE:           int = 0x00
HOTKEY_MOD_CTRL:           int = 0x02
HOTKEY_MOD_SHIFT:          int = 0x04
HOTKEY_MOD_ALT:            int = 0x08
HOTKEY_MOD_CTRL_SHIFT:     int = 0x06
HOTKEY_MOD_CTRL_ALT:       int = 0x0A
HOTKEY_MOD_SHIFT_ALT:      int = 0x0C
HOTKEY_MOD_CTRL_SHIFT_ALT: int = 0x0E

HID_KEY_A:   int = 0x04
HID_KEY_Z:   int = 0x1D
HID_KEY_F1:  int = 0x3A
HID_KEY_F12: int = 0x45
HID_KEY_DEL: int = 0x4C

# ── MIDI Control Change numbers ───────────────────────────────────────────────
CC_MIC_FX_SW:          int = 0
CC_MIC_FX_CHANGE:      int = 1
CC_REVERB_SW:          int = 2
CC_GAME_EQ_SW:         int = 5
CC_GAME_EQ_CHANGE:     int = 6
CC_CHAT_DEESSER_SW:    int = 7
CC_CHAT_COMP_SW:       int = 8
CC_OUTPUT_DELAY_SW:    int = 9
CC_PROFILE_CHANGE:     int = 10
CC_SFX_A:              int = 11
CC_SFX_B:              int = 12
CC_BEEP:               int = 13
CC_MUTE_STREAM_OUT:    int = 14
CC_MUTE_LINE_OUT:      int = 15
CC_MUTE_PHONES:        int = 16
CC_MUTE_ALL_OUTPUTS:   int = 17
CC_CH_MUTE_STREAM:     int = 18
CC_CH_MUTE_PERSONAL:   int = 19
CC_CH_MUTE_MIC:        int = 20
CC_CH_MUTE_ALL:        int = 21
CC_STREAM_MIX_LEVEL:   int = 22
CC_PERSONAL_MIX_LEVEL: int = 23
CC_MIC_LEVEL:          int = 24

# CC channel assignments (1-based; subtract 1 for MIDI wire channel nibble)
CC_CHANNEL_MIC:    int = 1
CC_CHANNEL_AUX:    int = 2
CC_CHANNEL_CHAT:   int = 3
CC_CHANNEL_GAME:   int = 4
CC_CHANNEL_MUSIC:  int = 5
CC_CHANNEL_SYSTEM: int = 6
CC_CHANNEL_SFX:    int = 7

CC_CHANNELS_PER_CHANNEL_MUTE:  tuple[int, ...] = (1, 2, 3, 4, 5, 6)    # Mic..Sys (no Sfx)
CC_CHANNELS_PER_CHANNEL_LEVEL: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7) # Mic..Sfx
