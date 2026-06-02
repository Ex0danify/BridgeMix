"""
Per-channel constants: stream/personal volumes and mutes, mix link, output
mutes and volumes, read-only monitors, LED strip config, meter indices.

All addresses use SECTION_CHANNEL (0x03) with TYPE_FADER (0x07) or
TYPE_STRIP_CONFIG (0x08) unless noted.
"""

# ── Volume/fader values ───────────────────────────────────────────────────────
# Factory-reset capture (2026-06-01) shows the device defaults every input fader
# to 0x64 (100), except the SFX channel which defaults to 0x47 (71).
VOLUME_MIN:         int = 0x00
VOLUME_MAX:         int = 0x7F
VOLUME_DEFAULT:     int = 0x64
VOLUME_DEFAULT_SFX: int = 0x47

# ── Mute values ───────────────────────────────────────────────────────────────
MUTE_ON:  int = 0x00   # channel muted
MUTE_OFF: int = 0x01   # channel active (unmuted)

# ── Stream-mix volume addresses  (SECTION_CHANNEL, TYPE_FADER) ───────────────
ADDR_ST_MIC_VOL:   int = 0x00
ADDR_ST_AUX_VOL:   int = 0x02
ADDR_ST_CHAT_VOL:  int = 0x04
ADDR_ST_GAME_VOL:  int = 0x06
ADDR_ST_MUSIC_VOL: int = 0x08
ADDR_ST_SYS_VOL:   int = 0x0A
ADDR_ST_SFX_VOL:   int = 0x0C

# ── Personal-mix volume addresses  (SECTION_CHANNEL, TYPE_FADER) ─────────────
ADDR_PS_MIC_VOL:   int = 0x10
ADDR_PS_AUX_VOL:   int = 0x12
ADDR_PS_CHAT_VOL:  int = 0x14
ADDR_PS_GAME_VOL:  int = 0x16
ADDR_PS_MUSIC_VOL: int = 0x18
ADDR_PS_SYS_VOL:   int = 0x1A
ADDR_PS_SFX_VOL:   int = 0x1C

# ── Mic "third channel" — un-bussed raw mic tap ───────────────────────────────
ADDR_MIC_DIRECT_VOL:  int = 0x54   # un-bussed mic feed (writability unverified)
ADDR_MIC_DIRECT_MUTE: int = 0x64
MIC_DIRECT_MUTE_OFF:  int = 0x00   # muted
MIC_DIRECT_MUTE_ON:   int = 0x01   # active (unmuted)

# Knob target: SECTION_CHANNEL, TYPE_SWITCH, addr=0x46
ADDR_MIC_KNOB_TARGET: int = 0x46
MIC_KNOB_TARGET_RAW:  int = 0x00   # hardware knob controls raw mic vol (addr=0x54)
MIC_KNOB_TARGET_PERS: int = 0x01   # hardware knob controls personal mix mic vol (addr=0x10)

# Device notifies host via addr=0x64 on ps_mic_mute changes
ADDR_PS_MIC_MUTE_MIRROR: int = 0x64

# ── Stream-bus mute addresses  (SECTION_CHANNEL, TYPE_FADER) ─────────────────
# value: 0x00=muted, 0x01=active
ADDR_ST_MIC_MUTE:  int = 0x20
ADDR_ST_AUX_MUTE:  int = 0x22
ADDR_ST_CHAT_MUTE: int = 0x24
ADDR_ST_GAME_MUTE: int = 0x26
ADDR_ST_MUSIC_MUTE: int = 0x28
ADDR_ST_SYS_MUTE:  int = 0x2A
ST_MUTE_ADDRESSES: tuple[int, int, int, int] = (
    ADDR_ST_MIC_MUTE, ADDR_ST_AUX_MUTE, ADDR_ST_CHAT_MUTE, ADDR_ST_GAME_MUTE,
)
ST_MUTE_ALL_SOURCES: tuple[int, ...] = (
    ADDR_ST_MIC_MUTE, ADDR_ST_AUX_MUTE, ADDR_ST_CHAT_MUTE, ADDR_ST_GAME_MUTE,
    ADDR_ST_MUSIC_MUTE, ADDR_ST_SYS_MUTE,
)

# ── Personal-bus mute addresses  (SECTION_CHANNEL, TYPE_FADER) ───────────────
ADDR_PS_MIC_MUTE:  int = 0x30
ADDR_PS_AUX_MUTE:  int = 0x32
ADDR_PS_CHAT_MUTE: int = 0x34
ADDR_PS_GAME_MUTE: int = 0x36
ADDR_PS_MUSIC_MUTE: int = 0x38
ADDR_PS_SYS_MUTE:  int = 0x3A
PS_MUTE_ADDRESSES: tuple[int, int, int, int] = (
    ADDR_PS_MIC_MUTE, ADDR_PS_AUX_MUTE, ADDR_PS_CHAT_MUTE, ADDR_PS_GAME_MUTE,
)
PS_MUTE_ALL_SOURCES: tuple[int, ...] = (
    ADDR_PS_MIC_MUTE, ADDR_PS_AUX_MUTE, ADDR_PS_CHAT_MUTE, ADDR_PS_GAME_MUTE,
    ADDR_PS_MUSIC_MUTE, ADDR_PS_SYS_MUTE,
)

# ── Mix link  (SECTION_CHANNEL, TYPE_SWITCH) ──────────────────────────────────
ADDR_MIX_LINK: int = 0x40
MIX_LINK_OFF:  int = 0x00
MIX_LINK_ON:   int = 0x01

# Mix-Link diff burst base/end addresses (TYPE_FADER frames emitted on link toggle)
ADDR_MIX_LINK_DIFF_BASE: int = 0x40
ADDR_MIX_LINK_DIFF_END:  int = 0x5A

# ── Output mutes  (SECTION_CHANNEL, TYPE_FADER) ───────────────────────────────
ADDR_MUTE_STREAM_OUT: int = 0x60   # confirmed (2026-05-14)
ADDR_MUTE_SUBMIX_OUT: int = 0x62   # confirmed (2026-05-14)
ADDR_MUTE_PHONES_OUT: int = 0x66   # confirmed (2026-05-14)
ADDR_MUTE_LINE_OUT:   int = 0x68   # confirmed (2026-05-14)
OUTPUT_MUTE_OFF: int = 0x00   # muted
OUTPUT_MUTE_ON:  int = 0x01   # active (unmuted)

# ── Sub-Mix (Personal) output volume  (SECTION_CHANNEL, TYPE_FADER) ──────────
ADDR_SUBMIX_VOL: int = 0x52   # confirmed 2026-05-25

# ── Read-only monitor addresses  (SECTION_CHANNEL, TYPE_FADER) ────────────────
ADDR_STREAM_VOL: int = 0x50
ADDR_PHONES_VOL: int = 0x56
ADDR_LINE_OUT:   int = 0x58

# ── Strip button action assignment  (SECTION_CHANNEL, TYPE_STRIP_CONFIG = 0x08) ──
TYPE_STRIP_CONFIG: int = 0x08   # confirmed 2026-05-14

ADDR_STRIP1_BUTTON_ACTION: int = 0x04
ADDR_STRIP2_BUTTON_ACTION: int = 0x14
ADDR_STRIP3_BUTTON_ACTION: int = 0x24
ADDR_STRIP4_BUTTON_ACTION: int = 0x34

STRIP_BUTTON_ACTION_CHANNEL_MUTE_ALL:    int = 0x00
STRIP_BUTTON_ACTION_CHANNEL_MUTE_STREAM: int = 0x01
STRIP_BUTTON_ACTION_CHANNEL_MUTE_PERS:   int = 0x02
STRIP_BUTTON_ACTION_SFX_A:               int = 0x03
STRIP_BUTTON_ACTION_SFX_B:               int = 0x04
STRIP_BUTTON_ACTION_SFX_BEEP:            int = 0x05
STRIP_BUTTON_ACTION_MUTE_OUT_ALL:        int = 0x06
STRIP_BUTTON_ACTION_MUTE_OUT_STREAM:     int = 0x07
STRIP_BUTTON_ACTION_MUTE_OUT_LINE:       int = 0x08
STRIP_BUTTON_ACTION_MUTE_OUT_PHONES:     int = 0x09
STRIP_BUTTON_ACTION_PROFILE_1:           int = 0x0A
STRIP_BUTTON_ACTION_PROFILE_2:           int = 0x0B
STRIP_BUTTON_ACTION_PROFILE_3:           int = 0x0C
STRIP_BUTTON_ACTION_PROFILE_4:           int = 0x0D
STRIP_BUTTON_ACTION_PROFILE_5:           int = 0x0E
STRIP_BUTTON_ACTION_GAME_EQ_1:           int = 0x0F
STRIP_BUTTON_ACTION_GAME_EQ_2:           int = 0x10
STRIP_BUTTON_ACTION_GAME_EQ_3:           int = 0x11
STRIP_BUTTON_ACTION_GAME_EQ_4:           int = 0x12
STRIP_BUTTON_ACTION_GAME_EQ_5:           int = 0x13
STRIP_BUTTON_ACTION_GAME_EQ_OFF:         int = 0x14
STRIP_BUTTON_ACTION_MIC_FX_1:            int = 0x15
STRIP_BUTTON_ACTION_MIC_FX_2:            int = 0x16
STRIP_BUTTON_ACTION_MIC_FX_3:            int = 0x17
STRIP_BUTTON_ACTION_MIC_FX_4:            int = 0x18
STRIP_BUTTON_ACTION_MIC_FX_5:            int = 0x19
STRIP_BUTTON_ACTION_MIDI_CC_1:           int = 0x1A
STRIP_BUTTON_ACTION_MIDI_CC_2:           int = 0x1B
STRIP_BUTTON_ACTION_MIDI_CC_3:           int = 0x1C
STRIP_BUTTON_ACTION_MIDI_CC_4:           int = 0x1D
STRIP_BUTTON_ACTION_BGM_SFX_A:           int = 0x1E
STRIP_BUTTON_ACTION_BGM_SFX_B:           int = 0x1F
STRIP_BUTTON_ACTION_BGM_SFX_C:           int = 0x20
STRIP_BUTTON_ACTION_BGM_SFX_D:           int = 0x21
STRIP_BUTTON_ACTION_HOT_KEY:             int = 0x22
STRIP_BUTTON_ACTION_REVERB:              int = 0x23
STRIP_BUTTON_ACTION_BGM_CAST_PLAY_STOP:  int = 0x24
STRIP_BUTTON_ACTION_BGM_CAST_NEXT:       int = 0x25

# ── Channel LED colours  (SECTION_CHANNEL, TYPE_STRIP_CONFIG = 0x08) ─────────
# Each component: range 0x00–0x20 (0–32). Channel stride = 0x10.
LED_COLOR_MIN: int = 0x00
LED_COLOR_MAX: int = 0x20   # confirmed from full sweep capture

ADDR_LED_MIC_R:  int = 0x08   # confirmed 2026-05-14
ADDR_LED_MIC_G:  int = 0x0A
ADDR_LED_MIC_B:  int = 0x0C

ADDR_LED_AUX_R:  int = 0x18   # confirmed 2026-05-14
ADDR_LED_AUX_G:  int = 0x1A
ADDR_LED_AUX_B:  int = 0x1C

ADDR_LED_CHAT_R: int = 0x28   # confirmed 2026-05-14
ADDR_LED_CHAT_G: int = 0x2A
ADDR_LED_CHAT_B: int = 0x2C

ADDR_LED_GAME_R: int = 0x38   # confirmed 2026-05-14
ADDR_LED_GAME_G: int = 0x3A
ADDR_LED_GAME_B: int = 0x3C

# ── Hardware strip channel assignment  (SECTION_CHANNEL, TYPE_STRIP_CONFIG) ───
# Strip stride = 0x10; value encodes the assigned channel index.
ADDR_HW_STRIP_1_CH: int = 0x00   # confirmed 2026-05-20
ADDR_HW_STRIP_2_CH: int = 0x10
ADDR_HW_STRIP_3_CH: int = 0x20
ADDR_HW_STRIP_4_CH: int = 0x30

HW_STRIP_CH_MIC:    int = 0x00   # confirmed 2026-05-20
HW_STRIP_CH_AUX:    int = 0x01   # inferred
HW_STRIP_CH_CHAT:   int = 0x02   # confirmed 2026-05-20
HW_STRIP_CH_GAME:   int = 0x03   # confirmed 2026-05-20
HW_STRIP_CH_MUSIC:  int = 0x04   # inferred
HW_STRIP_CH_SYSTEM: int = 0x05   # confirmed 2026-05-20
HW_STRIP_CH_SFX:    int = 0x06   # inferred

HW_STRIP_CH_VALUE: dict[str, int] = {
    "mic":   HW_STRIP_CH_MIC,
    "aux":   HW_STRIP_CH_AUX,
    "chat":  HW_STRIP_CH_CHAT,
    "game":  HW_STRIP_CH_GAME,
    "music": HW_STRIP_CH_MUSIC,
    "sys":   HW_STRIP_CH_SYSTEM,
    "sfx":   HW_STRIP_CH_SFX,
}
HW_STRIP_VALUE_CH: dict[int, str] = {v: k for k, v in HW_STRIP_CH_VALUE.items()}

# ── Live Level Meter — 127-byte State Vector ──────────────────────────────────
# SECTION_STATUS (0x01), type=0x10, addr=0x00. Sent every ~50 ms.
# Frame indices are ABSOLUTE (F0=0). All 4-byte slots: L=(hi<<7)|lo, R=(hi<<7)|lo.
METER_SECTION:            int = 0x01   # SECTION_STATUS
METER_TYPE:               int = 0x10
METER_ADDR:               int = 0x00
METER_ADDR_CONTINUATION:  int = 0x70   # FW 3.00 continuation frame
METER_FRAME_LEN:          int = 127    # smaller of FW 1.06 (137) / FW 3.00 (127)

# Meter full-scale reference.  Although slots are 14-bit ((hi<<7)|lo, 0–16383),
# the device reports ~12288 (0x60<<7) at 0 dBFS — confirmed from maxed-output
# captures where phones/sub-mix peak around 10900–11700, never near 0x3FFF.
# UI meters must top out here so a maxed signal fills the bar instead of ~66%.
METER_FULL_SCALE:         int = 12288

# Streaming input slots (abs idx 45–68)
METER_IDX_ST_MIC:   int = 45
METER_IDX_ST_AUX:   int = 49
METER_IDX_ST_CHAT:  int = 53
METER_IDX_ST_GAME:  int = 57
METER_IDX_ST_MUSIC: int = 61
METER_IDX_ST_SYS:   int = 65

# Personal input slots (abs idx 69–108)
METER_IDX_PS_SFX:   int = 69
METER_IDX_PS_MIC:   int = 77
METER_IDX_PS_AUX:   int = 81
METER_IDX_PS_CHAT:  int = 85
METER_IDX_PS_GAME:  int = 89
METER_IDX_PS_MUSIC: int = 93
METER_IDX_PS_SYS:   int = 97

# Output block (abs idx 109–136)
METER_IDX_RAW_MIC:    int = 109   # raw/direct mic, pre-bus (2 bytes, mono)
METER_IDX_OUT_STREAM: int = 111   # STREAM MIX output (4 bytes)
METER_IDX_OUT_SUBMIX: int = 115   # SUB MIX output (4 bytes)
METER_IDX_OUT_PHONES: int = 123   # PHONES output
METER_IDX_OUT_LINE:   int = 127   # LINE OUT
