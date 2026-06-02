"""
Mic-related constants: input source, phantom power, gain, mic Clean Up effects
(low-cut, noise suppressor, de-esser, compressor, modern compressor, manual EQ),
and chat channel effects.

All addresses use SECTION_CHANNEL (0x03) with:
  TYPE_SWITCH (0x00)    — source, phantom, gain, fx enable
  TYPE_MIC_FX (0x01)   — cleanup and EQ parameters
  TYPE_MIC_FX_EXT (0x0E) — NS Expander + Compressor Modern
  TYPE_CHAT_FX (0x04)  — chat channel de-esser and compressor
"""

# ── Microphone source selector  (SECTION_CHANNEL, TYPE_SWITCH) ──────────────
ADDR_MIC_SOURCE: int = 0x20
MIC_SOURCE_XLR:     int = 0x00   # XLR input (Dynamic or Condenser)
MIC_SOURCE_HEADSET: int = 0x01   # TRS Headset input

ADDR_MIC_PHANTOM: int = 0x26
MIC_PHANTOM_OFF:  int = 0x00
MIC_PHANTOM_ON:   int = 0x01   # +48V phantom power (Condenser XLR)

# ── Mic gain  (SECTION_CHANNEL, TYPE_SWITCH) ──────────────────────────────────
ADDR_MIC_GAIN_XLR:     int = 0x22
ADDR_MIC_GAIN_HEADSET: int = 0x24
MIC_GAIN_MIN:          int = 0x00
MIC_GAIN_MAX:          int = 0x19   # 25 steps

# ── Mic effects enable / preset  (SECTION_CHANNEL, TYPE_SWITCH) ───────────────
ADDR_MIC_FX_ENABLE: int = 0x30
MIC_FX_DISABLED:    int = 0x00
MIC_FX_ENABLED:     int = 0x01

ADDR_MIC_FX_PRESET: int = 0x32   # confirmed (2026-05-20)
MIC_FX_PRESET_MIN:  int = 0
MIC_FX_PRESET_MAX:  int = 4

# ── Low Cut Filter  (SECTION_CHANNEL, TYPE_MIC_FX = 0x01) ────────────────────
ADDR_MIC_LOW_CUT:      int = 0x00
MIC_LOW_CUT_OFF:       int = 0x00
MIC_LOW_CUT_ON:        int = 0x01

ADDR_MIC_LOW_CUT_FREQ: int = 0x02
MIC_LOW_CUT_FREQ_MIN:  int = 0x00   # Flat (confirmed 2026-05-13)
MIC_LOW_CUT_FREQ_MAX:  int = 0x0F   # 500Hz

# ── Noise Suppressor  (SECTION_CHANNEL, TYPE_MIC_FX = 0x01) ──────────────────
ADDR_MIC_NS:          int = 0x10
MIC_NS_OFF:           int = 0x00
MIC_NS_ON:            int = 0x01

ADDR_MIC_NS_LEVEL:    int = 0x12   # confirmed (2026-05-13)
MIC_NS_LEVEL_MIN:     int = 0x00   # -96dBm
MIC_NS_LEVEL_MAX:     int = 0x60   # 0dBm

ADDR_MIC_NS_TYPE:     int = 0x14
MIC_NS_TYPE_GATE:     int = 0x00
MIC_NS_TYPE_ADAPTIVE: int = 0x01
MIC_NS_TYPE_EXPANDER: int = 0x02

ADDR_MIC_NS_ADT_LEVEL: int = 0x16
MIC_NS_ADT_LEVEL_MIN:  int = 0x00
MIC_NS_ADT_LEVEL_MAX:  int = 0x09

ADDR_MIC_NS_ATTACK:   int = 0x18
MIC_NS_ATTACK_MIN:    int = 0x00   # 0ms
MIC_NS_ATTACK_MAX:    int = 0x0A   # 100ms

ADDR_MIC_NS_RELEASE:  int = 0x1A
MIC_NS_RELEASE_MIN:   int = 0x00   # 50ms
MIC_NS_RELEASE_MAX:   int = 0x14   # 5000ms

# NS Expander  (SECTION_CHANNEL, TYPE_MIC_FX_EXT = 0x0E)
ADDR_NS_EXP_LEVEL:    int = 0x20
NS_EXP_LEVEL_MIN:     int = 0x27   # -60dB
NS_EXP_LEVEL_MAX:     int = 0x63   # 0dB

ADDR_NS_EXP_RELEASE:  int = 0x24
NS_EXP_RELEASE_MIN:   int = 0x00   # 0ms
NS_EXP_RELEASE_MAX:   int = 0x64   # 4000ms

# ── De-esser  (SECTION_CHANNEL, TYPE_MIC_FX = 0x01) ──────────────────────────
ADDR_MIC_DE_ESSER:       int = 0x20
MIC_DE_ESSER_OFF:        int = 0x00
MIC_DE_ESSER_ON:         int = 0x01

ADDR_MIC_DE_ESSER_DEPTH: int = 0x22
MIC_DE_ESSER_DEPTH_MIN:  int = 0x00   # depth=1
MIC_DE_ESSER_DEPTH_MAX:  int = 0x09   # depth=10

# ── Compressor (Legacy)  (SECTION_CHANNEL, TYPE_MIC_FX = 0x01) ───────────────
ADDR_MIC_COMPRESSOR:         int = 0x70
MIC_COMPRESSOR_OFF:          int = 0x00
MIC_COMPRESSOR_ON:           int = 0x01

ADDR_MIC_COMPRESSOR_ATTACK:  int = 0x72
MIC_COMPRESSOR_ATTACK_MIN:   int = 0x00   # 0.0ms
MIC_COMPRESSOR_ATTACK_MAX:   int = 0x0A   # 100ms

ADDR_MIC_COMPRESSOR_RELEASE: int = 0x74
MIC_COMPRESSOR_RELEASE_MIN:  int = 0x00   # 50ms
MIC_COMPRESSOR_RELEASE_MAX:  int = 0x14   # 5000ms

ADDR_MIC_COMPRESSOR_THRESHOLD: int = 0x76
MIC_COMPRESSOR_THRESHOLD_MIN:  int = 0x00   # -48dBm
MIC_COMPRESSOR_THRESHOLD_MAX:  int = 0x10   # 0dBm

ADDR_MIC_COMPRESSOR_RATIO:   int = 0x78
MIC_COMPRESSOR_RATIO_MIN:    int = 0x00   # 1.00:1
MIC_COMPRESSOR_RATIO_MAX:    int = 0x0D   # inf:1

ADDR_MIC_COMPRESSOR_POST_GAIN: int = 0x7A
MIC_COMPRESSOR_POST_GAIN_MIN:  int = 0x00   # +0dB
MIC_COMPRESSOR_POST_GAIN_MAX:  int = 0x1E   # +30dB

# ── Compressor Modern  (SECTION_CHANNEL, TYPE_MIC_FX_EXT = 0x0E) ─────────────
ADDR_COMP_MODE:        int = 0x00
COMP_MODE_LEGACY:      int = 0x00
COMP_MODE_MODERN:      int = 0x01

ADDR_COMP_MOD_AMOUNT:  int = 0x04
COMP_MOD_AMOUNT_MIN:   int = 0x00
COMP_MOD_AMOUNT_MAX:   int = 0x7F

ADDR_COMP_MOD_PEAK:    int = 0x12
COMP_MOD_PEAK_MIN:     int = 0x00
COMP_MOD_PEAK_MAX:     int = 0x64

ADDR_COMP_MOD_GAIN:    int = 0x14
COMP_MOD_GAIN_MIN:     int = 0x00
COMP_MOD_GAIN_MAX:     int = 0x64

# ── Mic Manual EQ  (SECTION_CHANNEL, TYPE_MIC_FX = 0x01) ─────────────────────
ADDR_MIC_EQ_ENABLE:    int = 0x30
MIC_EQ_ENABLE_OFF:     int = 0x00
MIC_EQ_ENABLE_ON:      int = 0x01

# Gain range (all bands): 0x00=-12dB, 0x0C=0dB, 0x18=+12dB (1dB/step, confirmed
# 2026-06-01). The Game EQ freq sweep matched the Mic EQ band ranges below, so the
# two are treated as shared; exact per-step freq tables live in
# gui/widgets/eq_widget.py.
MIC_EQ_GAIN_MIN:       int = 0x00
MIC_EQ_GAIN_CENTER:    int = 0x0C
MIC_EQ_GAIN_MAX:       int = 0x18

MIC_EQ_Q_MIN:          int = 0x00   # Q=0.3
MIC_EQ_Q_MAX:          int = 0x1F   # Q=16 (32 steps, confirmed FW 3.00)

# Band 01 — Low shelf (20Hz–400Hz, 20 steps)
ADDR_MIC_EQ_BAND1_GAIN: int = 0x32
ADDR_MIC_EQ_BAND1_FREQ: int = 0x34
MIC_EQ_BAND1_FREQ_MIN:  int = 0x00   # 20Hz
MIC_EQ_BAND1_FREQ_MAX:  int = 0x14   # 400Hz

# Band 02 — Peak (20Hz–470Hz, 30 steps; matches Game EQ sweep 2026-06-01)
ADDR_MIC_EQ_BAND2_GAIN: int = 0x36
ADDR_MIC_EQ_BAND2_FREQ: int = 0x38
ADDR_MIC_EQ_BAND2_Q:    int = 0x3A
MIC_EQ_BAND2_FREQ_MIN:  int = 0x00   # 20Hz
MIC_EQ_BAND2_FREQ_MAX:  int = 0x1E   # 470Hz

# Band 03 — Peak (20Hz–470Hz, 30 steps; matches Game EQ sweep 2026-06-01)
ADDR_MIC_EQ_BAND3_GAIN: int = 0x3C
ADDR_MIC_EQ_BAND3_FREQ: int = 0x3E
ADDR_MIC_EQ_BAND3_Q:    int = 0x40   # inferred
MIC_EQ_BAND3_FREQ_MIN:  int = 0x00
MIC_EQ_BAND3_FREQ_MAX:  int = 0x1E

# Band 04 — Peak (20Hz–470Hz, 30 steps; matches Game EQ sweep 2026-06-01)
ADDR_MIC_EQ_BAND4_GAIN: int = 0x42
ADDR_MIC_EQ_BAND4_FREQ: int = 0x44
ADDR_MIC_EQ_BAND4_Q:    int = 0x46   # inferred
MIC_EQ_BAND4_FREQ_MIN:  int = 0x00
MIC_EQ_BAND4_FREQ_MAX:  int = 0x1E

# Band 05 — Peak (315Hz–3.3KHz, 30 steps)
ADDR_MIC_EQ_BAND5_GAIN: int = 0x48
ADDR_MIC_EQ_BAND5_FREQ: int = 0x4A
ADDR_MIC_EQ_BAND5_Q:    int = 0x4C   # inferred
MIC_EQ_BAND5_FREQ_MIN:  int = 0x00   # 315Hz
MIC_EQ_BAND5_FREQ_MAX:  int = 0x1E   # 3.3KHz

# Band 06 — Peak (315Hz–3.3KHz, 30 steps)
ADDR_MIC_EQ_BAND6_GAIN: int = 0x4E
ADDR_MIC_EQ_BAND6_FREQ: int = 0x50
ADDR_MIC_EQ_BAND6_Q:    int = 0x52   # inferred
MIC_EQ_BAND6_FREQ_MIN:  int = 0x00
MIC_EQ_BAND6_FREQ_MAX:  int = 0x1E

# Band 07 — Peak (315Hz–3.3KHz, 30 steps)
ADDR_MIC_EQ_BAND7_GAIN: int = 0x54
ADDR_MIC_EQ_BAND7_FREQ: int = 0x56
ADDR_MIC_EQ_BAND7_Q:    int = 0x58   # inferred
MIC_EQ_BAND7_FREQ_MIN:  int = 0x00
MIC_EQ_BAND7_FREQ_MAX:  int = 0x1E

# Band 08 — Peak (3.0KHz–20.0KHz, 30 steps)
ADDR_MIC_EQ_BAND8_GAIN: int = 0x5A
ADDR_MIC_EQ_BAND8_FREQ: int = 0x5C
ADDR_MIC_EQ_BAND8_Q:    int = 0x5E   # inferred
MIC_EQ_BAND8_FREQ_MIN:  int = 0x00   # 3.0KHz
MIC_EQ_BAND8_FREQ_MAX:  int = 0x1E   # 20.0KHz

# Band 09 — Peak (3.0KHz–20.0KHz, 30 steps)
ADDR_MIC_EQ_BAND9_GAIN: int = 0x60
ADDR_MIC_EQ_BAND9_FREQ: int = 0x62
ADDR_MIC_EQ_BAND9_Q:    int = 0x64   # inferred
MIC_EQ_BAND9_FREQ_MIN:  int = 0x00
MIC_EQ_BAND9_FREQ_MAX:  int = 0x1E

# Band 10 — High shelf (800Hz–20.0KHz, 20 steps)
ADDR_MIC_EQ_BAND10_GAIN: int = 0x66
ADDR_MIC_EQ_BAND10_FREQ: int = 0x68
MIC_EQ_BAND10_FREQ_MIN:  int = 0x00   # 800Hz
MIC_EQ_BAND10_FREQ_MAX:  int = 0x14   # 20.0KHz

# ── Chat channel effects  (SECTION_CHANNEL, TYPE_CHAT_FX = 0x04) ─────────────

# Chat De-esser
ADDR_CHAT_DE_ESSER:       int = 0x00
CHAT_DE_ESSER_OFF:        int = 0x00
CHAT_DE_ESSER_ON:         int = 0x01

ADDR_CHAT_DE_ESSER_DEPTH: int = 0x02
CHAT_DE_ESSER_DEPTH_MIN:  int = 0x00
CHAT_DE_ESSER_DEPTH_MAX:  int = 0x09

# Chat Compressor
ADDR_CHAT_COMPRESSOR:         int = 0x10
CHAT_COMPRESSOR_OFF:          int = 0x00
CHAT_COMPRESSOR_ON:           int = 0x01

ADDR_CHAT_COMPRESSOR_ATTACK:  int = 0x12
CHAT_COMPRESSOR_ATTACK_MIN:   int = 0x00   # 0.0ms
CHAT_COMPRESSOR_ATTACK_MAX:   int = 0x0A   # 100ms

ADDR_CHAT_COMPRESSOR_RELEASE: int = 0x14
CHAT_COMPRESSOR_RELEASE_MIN:  int = 0x00   # 50ms
CHAT_COMPRESSOR_RELEASE_MAX:  int = 0x14   # 5000ms

ADDR_CHAT_COMPRESSOR_THRESHOLD: int = 0x16
CHAT_COMPRESSOR_THRESHOLD_MIN:  int = 0x00   # -48dBm
CHAT_COMPRESSOR_THRESHOLD_MAX:  int = 0x10   # 0dBm

ADDR_CHAT_COMPRESSOR_RATIO:   int = 0x18
CHAT_COMPRESSOR_RATIO_MIN:    int = 0x00   # 1.00:1
CHAT_COMPRESSOR_RATIO_MAX:    int = 0x0D   # inf:1

ADDR_CHAT_COMPRESSOR_POST_GAIN: int = 0x1A
CHAT_COMPRESSOR_POST_GAIN_MIN:  int = 0x00   # +0dB
CHAT_COMPRESSOR_POST_GAIN_MAX:  int = 0x1E   # +30dB
