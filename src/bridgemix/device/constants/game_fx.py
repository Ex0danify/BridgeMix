"""
Game channel effect constants: 10-band EQ, limiter, and virtual surround.

All addresses use SECTION_CHANNEL (0x03) with TYPE_GAME_FX (0x05),
except ADDR_GAME_EQ_PRESET which uses TYPE_SWITCH (0x00).

SECTION_SYNC_11 carries the 5 named Game EQ preset slots (type byte = slot index×0x10).
"""

# ── Game EQ preset selection  (SECTION_CHANNEL, TYPE_SWITCH = 0x00) ──────────
# Confirmed 2026-05-20 from sync_gameEq_1..5.midilog captures.
ADDR_GAME_EQ_PRESET: int = 0x34   # confirmed (2026-05-20)
GAME_EQ_PRESET_MIN:  int = 0
GAME_EQ_PRESET_MAX:  int = 4

# ── Game EQ preset name  (TYPE_GAME_FX = 0x05, addr 0x00) ────────────────────
# Same character packing as Voice Preset names. Confirmed 2026-05-20.
ADDR_GAME_EQ_NAME_START:        int = 0x00
ADDR_GAME_EQ_PRESET_NAME_BLOCK: int = 0x00
# Name region length in bytes (10 swapped-pairs); EQ data begins at 0x14.
GAME_EQ_PRESET_NAME_MAX:        int = 20

# ── Game EQ preset slot commands  (sec=0x7F type=0x7F command frames) ─────────
# Confirmed 2026-06-01: the official app SELECTS a slot with a 0x7F/0x7F command
# (val=slot), NOT by writing ADDR_GAME_EQ_PRESET (0x34) — that address only
# reports the active slot back.  SAVE persists the live EQ into a slot.
ADDR_GAME_EQ_PRESET_SELECT: int = 0x04   # confirmed (2026-06-01)
ADDR_GAME_EQ_PRESET_SAVE:   int = 0x0A   # confirmed (2026-06-01)
ADDR_GAME_EQ_PRESET_RESET:  int = 0x16   # reset slot to factory default (2026-06-01)

# ── Game EQ enable  (SECTION_CHANNEL, TYPE_GAME_FX = 0x05) ───────────────────
ADDR_GAME_EQ_ENABLE: int = 0x20   # confirmed (2026-05-13)
GAME_EQ_ENABLE_OFF:  int = 0x00
GAME_EQ_ENABLE_ON:   int = 0x01

# ── Game EQ Spectrum Analyzer  (SECTION_STATUS = 0x01, type SUBTYPE_STATUS_10 = 0x10) ──
# Toggles a real-time FFT overlay in the GAME EQ view. Confirmed 2026-06-01. Enabling
# it routes the Game channel into the SUB MIX (temporarily commandeering it — relevant
# when streaming). The Mic EQ has an always-on spectrum (no toggle) from its own ADC.
# NOTE: the FFT data is NOT sent over MIDI — the official app captures the SubMix USB
# audio and computes the FFT host-side. The only MIDI feedback is state-vector byte 36
# (in the 127-byte sec=0x01/type=0x10/addr=0x00 frame): 0x01=on, 0x00=off.
#   enable:  F0 41 10 00 00 00 00 11 12 7F 01 10 16 00 01 59 F7
#   disable: F0 41 10 00 00 00 00 11 12 7F 01 10 16 00 00 5A F7
ADDR_EQ_ANALYZER: int = 0x16   # confirmed (2026-06-01); section=STATUS, type=0x10
EQ_ANALYZER_OFF:  int = 0x00
EQ_ANALYZER_ON:   int = 0x01

# Gain range (all bands): 0x00=-12dB, 0x0C=0dB, 0x18=+12dB (1dB/step, confirmed
# 2026-06-01: our app's ±12 matched the official app's ±6 only after halving, i.e.
# raw-12 is correct). Exact per-step freq tables live in gui/widgets/eq_widget.py.
GAME_EQ_GAIN_MIN:    int = 0x00
GAME_EQ_GAIN_CENTER: int = 0x0C
GAME_EQ_GAIN_MAX:    int = 0x18

GAME_EQ_Q_MIN:       int = 0x00   # Q=0.3
GAME_EQ_Q_MAX:       int = 0x1F   # Q=16 (32 steps, confirmed FW 3.00)

# Band 01 — Low shelf (20Hz–400Hz, 20 steps)
ADDR_GAME_EQ_BAND1_GAIN: int = 0x22   # confirmed (2026-05-13)
ADDR_GAME_EQ_BAND1_FREQ: int = 0x24   # confirmed (2026-05-13)
GAME_EQ_BAND1_FREQ_MIN:  int = 0x00   # 20Hz
GAME_EQ_BAND1_FREQ_MAX:  int = 0x14   # 400Hz

# Band 02 — Peak (20Hz–470Hz, 30 steps; range confirmed 2026-06-01 sweep)
ADDR_GAME_EQ_BAND2_GAIN: int = 0x26   # inferred
ADDR_GAME_EQ_BAND2_FREQ: int = 0x28   # inferred
ADDR_GAME_EQ_BAND2_Q:    int = 0x2A   # inferred
GAME_EQ_BAND2_FREQ_MIN:  int = 0x00   # 20Hz
GAME_EQ_BAND2_FREQ_MAX:  int = 0x1E   # 470Hz

# Band 03 — Peak (20Hz–470Hz, 30 steps; range confirmed 2026-06-01 sweep)
ADDR_GAME_EQ_BAND3_GAIN: int = 0x2C   # inferred
ADDR_GAME_EQ_BAND3_FREQ: int = 0x2E   # inferred
ADDR_GAME_EQ_BAND3_Q:    int = 0x30   # inferred
GAME_EQ_BAND3_FREQ_MIN:  int = 0x00
GAME_EQ_BAND3_FREQ_MAX:  int = 0x1E

# Band 04 — Peak (20Hz–470Hz, 30 steps; range confirmed 2026-06-01 sweep)
ADDR_GAME_EQ_BAND4_GAIN: int = 0x32   # inferred
ADDR_GAME_EQ_BAND4_FREQ: int = 0x34   # inferred
ADDR_GAME_EQ_BAND4_Q:    int = 0x36   # inferred
GAME_EQ_BAND4_FREQ_MIN:  int = 0x00
GAME_EQ_BAND4_FREQ_MAX:  int = 0x1E

# Band 05 — Peak (315Hz–3.3KHz, 30 steps)
ADDR_GAME_EQ_BAND5_GAIN: int = 0x38   # inferred
ADDR_GAME_EQ_BAND5_FREQ: int = 0x3A   # inferred
ADDR_GAME_EQ_BAND5_Q:    int = 0x3C   # inferred
GAME_EQ_BAND5_FREQ_MIN:  int = 0x00   # 315Hz
GAME_EQ_BAND5_FREQ_MAX:  int = 0x1E   # 3.3KHz

# Band 06 — Peak (315Hz–3.3KHz, 30 steps)
ADDR_GAME_EQ_BAND6_GAIN: int = 0x3E   # inferred
ADDR_GAME_EQ_BAND6_FREQ: int = 0x40   # inferred
ADDR_GAME_EQ_BAND6_Q:    int = 0x42   # inferred
GAME_EQ_BAND6_FREQ_MIN:  int = 0x00
GAME_EQ_BAND6_FREQ_MAX:  int = 0x1E

# Band 07 — Peak (315Hz–3.3KHz, 30 steps)
ADDR_GAME_EQ_BAND7_GAIN: int = 0x44   # inferred
ADDR_GAME_EQ_BAND7_FREQ: int = 0x46   # inferred
ADDR_GAME_EQ_BAND7_Q:    int = 0x48   # inferred
GAME_EQ_BAND7_FREQ_MIN:  int = 0x00
GAME_EQ_BAND7_FREQ_MAX:  int = 0x1E

# Band 08 — Peak (3.0KHz–20.0KHz, 30 steps)
ADDR_GAME_EQ_BAND8_GAIN: int = 0x4A   # inferred
ADDR_GAME_EQ_BAND8_FREQ: int = 0x4C   # inferred
ADDR_GAME_EQ_BAND8_Q:    int = 0x4E   # inferred
GAME_EQ_BAND8_FREQ_MIN:  int = 0x00   # 3.0KHz
GAME_EQ_BAND8_FREQ_MAX:  int = 0x1E   # 20.0KHz

# Band 09 — Peak (3.0KHz–20.0KHz, 30 steps)
ADDR_GAME_EQ_BAND9_GAIN: int = 0x50   # inferred
ADDR_GAME_EQ_BAND9_FREQ: int = 0x52   # inferred
ADDR_GAME_EQ_BAND9_Q:    int = 0x54   # inferred
GAME_EQ_BAND9_FREQ_MIN:  int = 0x00
GAME_EQ_BAND9_FREQ_MAX:  int = 0x1E

# Band 10 — High shelf (800Hz–20.0KHz, 20 steps)
ADDR_GAME_EQ_BAND10_GAIN: int = 0x56   # inferred
ADDR_GAME_EQ_BAND10_FREQ: int = 0x58   # inferred
GAME_EQ_BAND10_FREQ_MIN:  int = 0x00   # 800Hz
GAME_EQ_BAND10_FREQ_MAX:  int = 0x14   # 20.0KHz

# ── Game channel Limiter  (SECTION_CHANNEL, TYPE_GAME_FX = 0x05) ─────────────
ADDR_GAME_LIMITER:         int = 0x60   # confirmed (2026-05-13)
GAME_LIMITER_OFF:          int = 0x00
GAME_LIMITER_ON:           int = 0x01

ADDR_GAME_LIMITER_LEVEL:   int = 0x62   # confirmed (2026-05-13)
GAME_LIMITER_LEVEL_MIN:    int = 0x00
GAME_LIMITER_LEVEL_MAX:    int = 0x19   # 25 steps

ADDR_GAME_LIMITER_RELEASE: int = 0x64   # confirmed (2026-05-13)
GAME_LIMITER_RELEASE_MIN:  int = 0x00   # 10ms
GAME_LIMITER_RELEASE_MAX:  int = 0x18   # 5000ms (24 steps)

# ── Virtual Surround  (SECTION_CHANNEL, TYPE_GAME_FX = 0x05) ─────────────────
ADDR_GAME_VSURROUND:        int = 0x12   # confirmed (2026-05-13)
GAME_VSURROUND_OFF:         int = 0x00
GAME_VSURROUND_ON:          int = 0x02

ADDR_GAME_VSURROUND_OUTPUT: int = 0x6A  # confirmed (2026-05-13)
GAME_VSURROUND_OUTPUT_PHONES:   int = 0x00
GAME_VSURROUND_OUTPUT_SPEAKERS: int = 0x01

# Front Angle (1°–89°, 88 steps; wire value = degrees)
ADDR_GAME_VSURROUND_FRONT_ANGLE: int = 0x14   # confirmed (2026-05-13)
GAME_VSURROUND_FRONT_ANGLE_MIN:  int = 0x01   # 1°
GAME_VSURROUND_FRONT_ANGLE_MAX:  int = 0x59   # 89°

# Surround Angle (91°–179°, 88 steps; ADDR_LO=0x01 at upper end)
ADDR_GAME_VSURROUND_SURROUND_ANGLE: int = 0x16   # confirmed (2026-05-13)
GAME_VSURROUND_SURROUND_ANGLE_MIN:  int = 0x5B   # 91°
GAME_VSURROUND_SURROUND_ANGLE_MAX:  int = 0x33   # 179° (wire wraps; ADDR_LO=0x01 at max)

# Surround Back Angle (91°–179°, 88 steps)
ADDR_GAME_VSURROUND_BACK_ANGLE: int = 0x18   # confirmed (2026-05-13)
GAME_VSURROUND_BACK_ANGLE_MIN:  int = 0x5B   # 91°
GAME_VSURROUND_BACK_ANGLE_MAX:  int = 0x33   # 179°

# Listening Angle (12°–78°, 66 steps; only when Output Type = Speakers)
ADDR_GAME_VSURROUND_LISTEN_ANGLE: int = 0x6C   # confirmed (2026-05-13)
GAME_VSURROUND_LISTEN_ANGLE_MIN:  int = 0x0C   # 12°
GAME_VSURROUND_LISTEN_ANGLE_MAX:  int = 0x4E   # 78°
