"""
Parameter dataclass and REGISTRY.

Each Parameter encodes everything needed to build a SysEx frame:
  section, param_type, addr_hi, addr_lo, value range, default.

The REGISTRY maps parameter names (str) → Parameter.
bridge_cast.py uses REGISTRY for generic set_parameter() dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bridgemix.device import constants as C


@dataclass(frozen=True)
class Parameter:
    name: str
    section: int
    param_type: int
    addr_hi: int
    addr_lo: int
    min_value: int
    max_value: int
    default_value: int
    read_only: bool = False


def _p(
    name: str,
    section: int,
    param_type: int,
    addr_hi: int,
    min_val: int,
    max_val: int,
    default: int,
    addr_lo: int = 0x00,
    read_only: bool = False,
) -> Parameter:
    return Parameter(name, section, param_type, addr_hi, addr_lo, min_val, max_val, default, read_only)


SC = C.SECTION_CHANNEL
SG = C.SECTION_GLOBAL
VFX = C.SECTION_VOICE_FX

SW = C.TYPE_SWITCH
MFX = C.TYPE_MIC_FX      # 0x01 (Mic Clean Up / EQ)
EXT = C.TYPE_MIC_FX_EXT  # 0x0E (NS Expander + Compressor Modern)
VOI = C.TYPE_VOICE        # 0x02
CFX = C.TYPE_CHAT_FX      # 0x04
GFX = C.TYPE_GAME_FX      # 0x05
DLY = C.TYPE_DELAY        # 0x06
FAD = C.TYPE_FADER        # 0x07
LED = C.TYPE_STRIP_CONFIG  # 0x08
HKY = C.TYPE_HOTKEY       # 0x09
VFX_T = C.TYPE_VOICE_FX   # 0x7F


def _build_registry() -> dict[str, Parameter]:
    r: dict[str, Parameter] = {}

    def add(p: Parameter) -> None:
        r[p.name] = p

    # ── Stream Mix Volumes ────────────────────────────────────────────────────
    add(_p("st_mic_vol",   SC, FAD, C.ADDR_ST_MIC_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("st_aux_vol",   SC, FAD, C.ADDR_ST_AUX_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("st_chat_vol",  SC, FAD, C.ADDR_ST_CHAT_VOL,  C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("st_game_vol",  SC, FAD, C.ADDR_ST_GAME_VOL,  C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("st_music_vol", SC, FAD, C.ADDR_ST_MUSIC_VOL, C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("st_sys_vol",   SC, FAD, C.ADDR_ST_SYS_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("st_sfx_vol",   SC, FAD, C.ADDR_ST_SFX_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT_SFX))

    # ── Personal Mix Volumes ──────────────────────────────────────────────────
    add(_p("ps_mic_vol",   SC, FAD, C.ADDR_PS_MIC_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("ps_aux_vol",   SC, FAD, C.ADDR_PS_AUX_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("ps_chat_vol",  SC, FAD, C.ADDR_PS_CHAT_VOL,  C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("ps_game_vol",  SC, FAD, C.ADDR_PS_GAME_VOL,  C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("ps_music_vol", SC, FAD, C.ADDR_PS_MUSIC_VOL, C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("ps_sys_vol",   SC, FAD, C.ADDR_PS_SYS_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))
    add(_p("ps_sfx_vol",   SC, FAD, C.ADDR_PS_SFX_VOL,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT_SFX))

    # ── Stream Mutes (0=muted, 1=active) ─────────────────────────────────────
    add(_p("st_mic_mute",   SC, FAD, C.ADDR_ST_MIC_MUTE,   C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("st_aux_mute",   SC, FAD, C.ADDR_ST_AUX_MUTE,   C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("st_chat_mute",  SC, FAD, C.ADDR_ST_CHAT_MUTE,  C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("st_game_mute",  SC, FAD, C.ADDR_ST_GAME_MUTE,  C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("st_music_mute", SC, FAD, C.ADDR_ST_MUSIC_MUTE, C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("st_sys_mute",   SC, FAD, C.ADDR_ST_SYS_MUTE,   C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))

    # ── Personal Mutes ────────────────────────────────────────────────────────
    add(_p("ps_mic_mute",   SC, FAD, C.ADDR_PS_MIC_MUTE,   C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("ps_aux_mute",   SC, FAD, C.ADDR_PS_AUX_MUTE,   C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("ps_chat_mute",  SC, FAD, C.ADDR_PS_CHAT_MUTE,  C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("ps_game_mute",  SC, FAD, C.ADDR_PS_GAME_MUTE,  C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("ps_music_mute", SC, FAD, C.ADDR_PS_MUSIC_MUTE, C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))
    add(_p("ps_sys_mute",   SC, FAD, C.ADDR_PS_SYS_MUTE,   C.MUTE_ON, C.MUTE_OFF, C.MUTE_OFF))

    # ── Sub-Mix output volume (writable) ─────────────────────────────────────
    add(_p("submix_vol", SC, FAD, C.ADDR_SUBMIX_VOL, C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT))

    # ── Mic direct (un-bussed raw mic tap, addr 0x54) ─────────────────────────
    # Writability unverified; registered writable so the UI fader can be tested.
    add(_p("mic_direct_vol",  SC, FAD, C.ADDR_MIC_DIRECT_VOL,  C.VOLUME_MIN,         C.VOLUME_MAX,          C.VOLUME_DEFAULT))
    add(_p("mic_direct_mute", SC, FAD, C.ADDR_MIC_DIRECT_MUTE, C.MIC_DIRECT_MUTE_OFF, C.MIC_DIRECT_MUTE_ON,  C.MIC_DIRECT_MUTE_ON))
    # Knob target: 0=raw mic, 1=personal mix. Default=1 (personal).
    add(_p("mic_knob_target", SC, SW,  C.ADDR_MIC_KNOB_TARGET, C.MIC_KNOB_TARGET_RAW, C.MIC_KNOB_TARGET_PERS, C.MIC_KNOB_TARGET_PERS))

    # ── Read-only monitor (hardware knobs) ────────────────────────────────────
    add(_p("stream_vol", SC, FAD, C.ADDR_STREAM_VOL, C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT, read_only=True))
    add(_p("phones_vol", SC, FAD, C.ADDR_PHONES_VOL, C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT, read_only=True))
    add(_p("line_out",   SC, FAD, C.ADDR_LINE_OUT,   C.VOLUME_MIN, C.VOLUME_MAX, C.VOLUME_DEFAULT, read_only=True))

    # ── Output mutes ─────────────────────────────────────────────────────────
    add(_p("mute_stream_out", SC, FAD, C.ADDR_MUTE_STREAM_OUT, C.OUTPUT_MUTE_OFF, C.OUTPUT_MUTE_ON, C.OUTPUT_MUTE_ON))
    add(_p("mute_submix_out", SC, FAD, C.ADDR_MUTE_SUBMIX_OUT, C.OUTPUT_MUTE_OFF, C.OUTPUT_MUTE_ON, C.OUTPUT_MUTE_ON))
    add(_p("mute_phones_out", SC, FAD, C.ADDR_MUTE_PHONES_OUT, C.OUTPUT_MUTE_OFF, C.OUTPUT_MUTE_ON, C.OUTPUT_MUTE_ON))
    add(_p("mute_line_out",   SC, FAD, C.ADDR_MUTE_LINE_OUT,   C.OUTPUT_MUTE_OFF, C.OUTPUT_MUTE_ON, C.OUTPUT_MUTE_ON))

    # ── Mic controls (TYPE_SWITCH) ────────────────────────────────────────────
    add(_p("mic_source",       SC, SW, C.ADDR_MIC_SOURCE,       0, 1, 0))
    add(_p("mic_phantom",      SC, SW, C.ADDR_MIC_PHANTOM,      0, 1, 0))
    add(_p("mic_gain_xlr",     SC, SW, C.ADDR_MIC_GAIN_XLR,     C.MIC_GAIN_MIN, C.MIC_GAIN_MAX, 0))
    add(_p("mic_gain_headset", SC, SW, C.ADDR_MIC_GAIN_HEADSET, C.MIC_GAIN_MIN, C.MIC_GAIN_MAX, 0))
    add(_p("mic_fx_enable",    SC, SW, C.ADDR_MIC_FX_ENABLE,    0, 1, 0))
    add(_p("mic_fx_preset",    SC, SW, C.ADDR_MIC_FX_PRESET,    C.MIC_FX_PRESET_MIN, C.MIC_FX_PRESET_MAX, 0))
    add(_p("game_eq_preset",   SC, SW, C.ADDR_GAME_EQ_PRESET,   C.GAME_EQ_PRESET_MIN, C.GAME_EQ_PRESET_MAX, 0))

    # ── Mix mode / link ───────────────────────────────────────────────────────
    add(_p("mix_mode",       SG, SW, C.ADDR_MIX_MODE,     0, 1, 0))
    add(_p("mix_link",       SC, SW, C.ADDR_MIX_LINK,     0, 1, 0))
    add(_p("active_profile", SG, SW, C.ADDR_ACTIVE_PROFILE, C.ACTIVE_PROFILE_MIN, C.ACTIVE_PROFILE_MAX, 0))

    # ── Global system settings ─────────────────────────────────────────────
    add(_p("led_brightness",  SG, SW, C.ADDR_LED_BRIGHTNESS,  C.LED_BRIGHTNESS_MIN, C.LED_BRIGHTNESS_MAX, C.LED_BRIGHTNESS_DEFAULT))
    add(_p("indicator_type",  SG, SW, C.ADDR_INDICATOR_TYPE,  0, 1, 0))
    add(_p("phones_gain",     SG, SW, C.ADDR_PHONES_GAIN,     0, 2, 0))
    add(_p("mute_display",    SG, SW, C.ADDR_MUTE_DISPLAY,    0, 1, 0))

    # ── SFX volumes (SECTION_GLOBAL, type=0x01/0x02) ──────────────────────────
    add(_p("sfx_a_vol", SG, C.TYPE_GLOBAL_SFX_A, C.ADDR_SFX_A_VOL, C.SFX_VOL_MIN, C.SFX_VOL_MAX, C.SFX_VOL_DEFAULT))
    add(_p("sfx_b_vol", SG, C.TYPE_GLOBAL_SFX_B, C.ADDR_SFX_B_VOL, C.SFX_VOL_MIN, C.SFX_VOL_MAX, C.SFX_VOL_DEFAULT))

    # ── Mic Cleanup (TYPE_MIC_FX = 0x01) ─────────────────────────────────────
    add(_p("mic_low_cut",           SC, MFX, C.ADDR_MIC_LOW_CUT,           0, 1, 0))
    add(_p("mic_low_cut_freq",      SC, MFX, C.ADDR_MIC_LOW_CUT_FREQ,      C.MIC_LOW_CUT_FREQ_MIN, C.MIC_LOW_CUT_FREQ_MAX, 0))
    add(_p("mic_ns",                SC, MFX, C.ADDR_MIC_NS,                0, 1, 0))
    add(_p("mic_ns_level",          SC, MFX, C.ADDR_MIC_NS_LEVEL,          C.MIC_NS_LEVEL_MIN, C.MIC_NS_LEVEL_MAX, 0))
    add(_p("mic_ns_type",           SC, MFX, C.ADDR_MIC_NS_TYPE,           0, 2, 0))
    add(_p("mic_ns_adp_level",     SC, MFX, C.ADDR_MIC_NS_ADT_LEVEL,      C.MIC_NS_ADT_LEVEL_MIN, C.MIC_NS_ADT_LEVEL_MAX, 0))
    add(_p("mic_ns_attack",        SC, MFX, C.ADDR_MIC_NS_ATTACK,         C.MIC_NS_ATTACK_MIN, C.MIC_NS_ATTACK_MAX, 0))
    add(_p("mic_ns_release",       SC, MFX, C.ADDR_MIC_NS_RELEASE,        C.MIC_NS_RELEASE_MIN, C.MIC_NS_RELEASE_MAX, 0))
    add(_p("mic_ns_exp_level",     SC, EXT, C.ADDR_NS_EXP_LEVEL,   C.NS_EXP_LEVEL_MIN,   C.NS_EXP_LEVEL_MAX,   C.NS_EXP_LEVEL_MAX))
    add(_p("mic_ns_exp_release",   SC, EXT, C.ADDR_NS_EXP_RELEASE, C.NS_EXP_RELEASE_MIN, C.NS_EXP_RELEASE_MAX, 0))
    add(_p("mic_de_esser",          SC, MFX, C.ADDR_MIC_DE_ESSER,          0, 1, 0))
    add(_p("mic_de_esser_depth",    SC, MFX, C.ADDR_MIC_DE_ESSER_DEPTH,    C.MIC_DE_ESSER_DEPTH_MIN, C.MIC_DE_ESSER_DEPTH_MAX, 0))
    add(_p("mic_compressor",        SC, MFX, C.ADDR_MIC_COMPRESSOR,        0, 1, 0))
    add(_p("mic_compressor_attack", SC, MFX, C.ADDR_MIC_COMPRESSOR_ATTACK, C.MIC_COMPRESSOR_ATTACK_MIN, C.MIC_COMPRESSOR_ATTACK_MAX, 0))
    add(_p("mic_compressor_release",   SC, MFX, C.ADDR_MIC_COMPRESSOR_RELEASE,   C.MIC_COMPRESSOR_RELEASE_MIN, C.MIC_COMPRESSOR_RELEASE_MAX, 0))
    add(_p("mic_compressor_threshold", SC, MFX, C.ADDR_MIC_COMPRESSOR_THRESHOLD, C.MIC_COMPRESSOR_THRESHOLD_MIN, C.MIC_COMPRESSOR_THRESHOLD_MAX, 0))
    add(_p("mic_compressor_ratio",     SC, MFX, C.ADDR_MIC_COMPRESSOR_RATIO,     C.MIC_COMPRESSOR_RATIO_MIN, C.MIC_COMPRESSOR_RATIO_MAX, 0))
    add(_p("mic_compressor_post_gain", SC, MFX, C.ADDR_MIC_COMPRESSOR_POST_GAIN, C.MIC_COMPRESSOR_POST_GAIN_MIN, C.MIC_COMPRESSOR_POST_GAIN_MAX, 0))
    add(_p("mic_comp_mode",       SC, EXT, C.ADDR_COMP_MODE,       C.COMP_MODE_LEGACY,    C.COMP_MODE_MODERN,    C.COMP_MODE_LEGACY))
    add(_p("mic_comp_mod_amount", SC, EXT, C.ADDR_COMP_MOD_AMOUNT, C.COMP_MOD_AMOUNT_MIN, C.COMP_MOD_AMOUNT_MAX, 0))
    add(_p("mic_comp_mod_peak",   SC, EXT, C.ADDR_COMP_MOD_PEAK,   C.COMP_MOD_PEAK_MIN,   C.COMP_MOD_PEAK_MAX,   0))
    add(_p("mic_comp_mod_gain",   SC, EXT, C.ADDR_COMP_MOD_GAIN,   C.COMP_MOD_GAIN_MIN,   C.COMP_MOD_GAIN_MAX,   0))
    add(_p("mic_eq_enable", SC, MFX, C.ADDR_MIC_EQ_ENABLE, 0, 1, 0))

    # Mic Manual EQ — 10 bands
    _MIC_EQ = [
        (1,  C.ADDR_MIC_EQ_BAND1_GAIN,  C.ADDR_MIC_EQ_BAND1_FREQ,  None,                  C.MIC_EQ_BAND1_FREQ_MIN,  C.MIC_EQ_BAND1_FREQ_MAX),
        (2,  C.ADDR_MIC_EQ_BAND2_GAIN,  C.ADDR_MIC_EQ_BAND2_FREQ,  C.ADDR_MIC_EQ_BAND2_Q, C.MIC_EQ_BAND2_FREQ_MIN,  C.MIC_EQ_BAND2_FREQ_MAX),
        (3,  C.ADDR_MIC_EQ_BAND3_GAIN,  C.ADDR_MIC_EQ_BAND3_FREQ,  C.ADDR_MIC_EQ_BAND3_Q, C.MIC_EQ_BAND2_FREQ_MIN,  C.MIC_EQ_BAND2_FREQ_MAX),
        (4,  C.ADDR_MIC_EQ_BAND4_GAIN,  C.ADDR_MIC_EQ_BAND4_FREQ,  C.ADDR_MIC_EQ_BAND4_Q, C.MIC_EQ_BAND2_FREQ_MIN,  C.MIC_EQ_BAND2_FREQ_MAX),
        (5,  C.ADDR_MIC_EQ_BAND5_GAIN,  C.ADDR_MIC_EQ_BAND5_FREQ,  C.ADDR_MIC_EQ_BAND5_Q, C.MIC_EQ_BAND5_FREQ_MIN,  C.MIC_EQ_BAND5_FREQ_MAX),
        (6,  C.ADDR_MIC_EQ_BAND6_GAIN,  C.ADDR_MIC_EQ_BAND6_FREQ,  C.ADDR_MIC_EQ_BAND6_Q, C.MIC_EQ_BAND5_FREQ_MIN,  C.MIC_EQ_BAND5_FREQ_MAX),
        (7,  C.ADDR_MIC_EQ_BAND7_GAIN,  C.ADDR_MIC_EQ_BAND7_FREQ,  C.ADDR_MIC_EQ_BAND7_Q, C.MIC_EQ_BAND5_FREQ_MIN,  C.MIC_EQ_BAND5_FREQ_MAX),
        (8,  C.ADDR_MIC_EQ_BAND8_GAIN,  C.ADDR_MIC_EQ_BAND8_FREQ,  C.ADDR_MIC_EQ_BAND8_Q, C.MIC_EQ_BAND8_FREQ_MIN,  C.MIC_EQ_BAND8_FREQ_MAX),
        (9,  C.ADDR_MIC_EQ_BAND9_GAIN,  C.ADDR_MIC_EQ_BAND9_FREQ,  C.ADDR_MIC_EQ_BAND9_Q, C.MIC_EQ_BAND8_FREQ_MIN,  C.MIC_EQ_BAND8_FREQ_MAX),
        (10, C.ADDR_MIC_EQ_BAND10_GAIN, C.ADDR_MIC_EQ_BAND10_FREQ, None,                  C.MIC_EQ_BAND10_FREQ_MIN, C.MIC_EQ_BAND10_FREQ_MAX),
    ]
    for n, gain_a, freq_a, q_a, freq_min, freq_max in _MIC_EQ:
        add(_p(f"mic_eq_band{n}_gain", SC, MFX, gain_a, C.MIC_EQ_GAIN_MIN, C.MIC_EQ_GAIN_MAX, C.MIC_EQ_GAIN_CENTER))
        add(_p(f"mic_eq_band{n}_freq", SC, MFX, freq_a, freq_min, freq_max, 0))
        if q_a is not None:
            add(_p(f"mic_eq_band{n}_q", SC, MFX, q_a, C.MIC_EQ_Q_MIN, C.MIC_EQ_Q_MAX, 0))

    # ── Voice Effects (TYPE_VOICE = 0x02) ─────────────────────────────────────
    add(_p("voice_pitch",   SC, VOI, C.ADDR_VOICE_PITCH,  C.VOICE_MIN, C.VOICE_MAX, C.VOICE_DEFAULT))
    add(_p("voice_format",  SC, VOI, C.ADDR_VOICE_FORMAT, C.VOICE_MIN, C.VOICE_MAX, C.VOICE_DEFAULT))
    add(_p("voice_mode",    SC, VOI, C.ADDR_VOICE_MODE,   0, 1, 0))
    add(_p("reverb_switch", SC, VOI, C.ADDR_REVERB_SWITCH, 0, 1, 0))
    add(_p("reverb_size",   SC, VOI, C.ADDR_REVERB_SIZE,   C.REVERB_SIZE_MIN, C.REVERB_SIZE_MAX, 0))
    add(_p("reverb_level",  SC, VOI, C.ADDR_REVERB_LEVEL,  C.REVERB_LEVEL_MIN, C.REVERB_LEVEL_MAX, 0))

    # Voice FX preset (SECTION_VOICE_FX / TYPE_VOICE_FX) — non-standard section
    add(_p("voice_fx_preset", VFX, VFX_T, C.ADDR_VOICE_FX_PRESET, 0, 4, 0))

    # ── Chat Effects (TYPE_CHAT_FX = 0x04) ───────────────────────────────────
    add(_p("chat_de_esser",             SC, CFX, C.ADDR_CHAT_DE_ESSER,             0, 1, 0))
    add(_p("chat_de_esser_depth",       SC, CFX, C.ADDR_CHAT_DE_ESSER_DEPTH,       C.CHAT_DE_ESSER_DEPTH_MIN, C.CHAT_DE_ESSER_DEPTH_MAX, 0))
    add(_p("chat_compressor",           SC, CFX, C.ADDR_CHAT_COMPRESSOR,           0, 1, 0))
    add(_p("chat_compressor_attack",    SC, CFX, C.ADDR_CHAT_COMPRESSOR_ATTACK,    C.CHAT_COMPRESSOR_ATTACK_MIN, C.CHAT_COMPRESSOR_ATTACK_MAX, 0))
    add(_p("chat_compressor_release",   SC, CFX, C.ADDR_CHAT_COMPRESSOR_RELEASE,   C.CHAT_COMPRESSOR_RELEASE_MIN, C.CHAT_COMPRESSOR_RELEASE_MAX, 0))
    add(_p("chat_compressor_threshold", SC, CFX, C.ADDR_CHAT_COMPRESSOR_THRESHOLD, C.CHAT_COMPRESSOR_THRESHOLD_MIN, C.CHAT_COMPRESSOR_THRESHOLD_MAX, 0))
    add(_p("chat_compressor_ratio",     SC, CFX, C.ADDR_CHAT_COMPRESSOR_RATIO,     C.CHAT_COMPRESSOR_RATIO_MIN, C.CHAT_COMPRESSOR_RATIO_MAX, 0))
    add(_p("chat_compressor_post_gain", SC, CFX, C.ADDR_CHAT_COMPRESSOR_POST_GAIN, C.CHAT_COMPRESSOR_POST_GAIN_MIN, C.CHAT_COMPRESSOR_POST_GAIN_MAX, 0))

    # ── Game Effects (TYPE_GAME_FX = 0x05) ───────────────────────────────────
    add(_p("game_eq_enable",    SC, GFX, C.ADDR_GAME_EQ_ENABLE,    0, 1, 0))
    add(_p("game_limiter",      SC, GFX, C.ADDR_GAME_LIMITER,      0, 1, 0))
    add(_p("game_limiter_level",   SC, GFX, C.ADDR_GAME_LIMITER_LEVEL,   C.GAME_LIMITER_LEVEL_MIN, C.GAME_LIMITER_LEVEL_MAX, 0))
    add(_p("game_limiter_release", SC, GFX, C.ADDR_GAME_LIMITER_RELEASE, C.GAME_LIMITER_RELEASE_MIN, C.GAME_LIMITER_RELEASE_MAX, 0))
    add(_p("game_vsurround",        SC, GFX, C.ADDR_GAME_VSURROUND,        0, 2, 0))
    add(_p("game_vsurround_output", SC, GFX, C.ADDR_GAME_VSURROUND_OUTPUT, 0, 1, 0))
    add(_p("game_vsurround_front_angle", SC, GFX, C.ADDR_GAME_VSURROUND_FRONT_ANGLE,
           C.GAME_VSURROUND_FRONT_ANGLE_MIN, C.GAME_VSURROUND_FRONT_ANGLE_MAX, 45))
    # Surround/back angles span 91°–179°.  Values >127 require addr_lo=0x01 (high bit),
    # so standard set_parameter cannot write them.  Register read_only here; use
    # BridgeCast.set_vsurround_angle() for writes.
    add(_p("game_vsurround_surround_angle", SC, GFX,
           C.ADDR_GAME_VSURROUND_SURROUND_ANGLE,
           C.GAME_VSURROUND_SURROUND_ANGLE_MIN, 179, 111,
           read_only=True))
    add(_p("game_vsurround_back_angle", SC, GFX,
           C.ADDR_GAME_VSURROUND_BACK_ANGLE,
           C.GAME_VSURROUND_BACK_ANGLE_MIN, 179, 149,
           read_only=True))
    add(_p("game_vsurround_listen_angle", SC, GFX, C.ADDR_GAME_VSURROUND_LISTEN_ANGLE,
           C.GAME_VSURROUND_LISTEN_ANGLE_MIN, C.GAME_VSURROUND_LISTEN_ANGLE_MAX, 45))

    # Game Manual EQ — 10 bands
    _GAME_EQ = [
        (1,  C.ADDR_GAME_EQ_BAND1_GAIN,  C.ADDR_GAME_EQ_BAND1_FREQ,  None,                   C.GAME_EQ_BAND1_FREQ_MIN, C.GAME_EQ_BAND1_FREQ_MAX),
        (2,  C.ADDR_GAME_EQ_BAND2_GAIN,  C.ADDR_GAME_EQ_BAND2_FREQ,  C.ADDR_GAME_EQ_BAND2_Q, C.GAME_EQ_BAND2_FREQ_MIN, C.GAME_EQ_BAND2_FREQ_MAX),
        (3,  C.ADDR_GAME_EQ_BAND3_GAIN,  C.ADDR_GAME_EQ_BAND3_FREQ,  C.ADDR_GAME_EQ_BAND3_Q, C.GAME_EQ_BAND2_FREQ_MIN, C.GAME_EQ_BAND2_FREQ_MAX),
        (4,  C.ADDR_GAME_EQ_BAND4_GAIN,  C.ADDR_GAME_EQ_BAND4_FREQ,  C.ADDR_GAME_EQ_BAND4_Q, C.GAME_EQ_BAND2_FREQ_MIN, C.GAME_EQ_BAND2_FREQ_MAX),
        (5,  C.ADDR_GAME_EQ_BAND5_GAIN,  C.ADDR_GAME_EQ_BAND5_FREQ,  C.ADDR_GAME_EQ_BAND5_Q, C.GAME_EQ_BAND5_FREQ_MIN, C.GAME_EQ_BAND5_FREQ_MAX),
        (6,  C.ADDR_GAME_EQ_BAND6_GAIN,  C.ADDR_GAME_EQ_BAND6_FREQ,  C.ADDR_GAME_EQ_BAND6_Q, C.GAME_EQ_BAND5_FREQ_MIN, C.GAME_EQ_BAND5_FREQ_MAX),
        (7,  C.ADDR_GAME_EQ_BAND7_GAIN,  C.ADDR_GAME_EQ_BAND7_FREQ,  C.ADDR_GAME_EQ_BAND7_Q, C.GAME_EQ_BAND5_FREQ_MIN, C.GAME_EQ_BAND5_FREQ_MAX),
        (8,  C.ADDR_GAME_EQ_BAND8_GAIN,  C.ADDR_GAME_EQ_BAND8_FREQ,  C.ADDR_GAME_EQ_BAND8_Q, C.GAME_EQ_BAND8_FREQ_MIN, C.GAME_EQ_BAND8_FREQ_MAX),
        (9,  C.ADDR_GAME_EQ_BAND9_GAIN,  C.ADDR_GAME_EQ_BAND9_FREQ,  C.ADDR_GAME_EQ_BAND9_Q, C.GAME_EQ_BAND8_FREQ_MIN, C.GAME_EQ_BAND8_FREQ_MAX),
        (10, C.ADDR_GAME_EQ_BAND10_GAIN, C.ADDR_GAME_EQ_BAND10_FREQ, None,                   C.GAME_EQ_BAND10_FREQ_MIN, C.GAME_EQ_BAND10_FREQ_MAX),
    ]
    for n, gain_a, freq_a, q_a, freq_min, freq_max in _GAME_EQ:
        add(_p(f"game_eq_band{n}_gain", SC, GFX, gain_a, C.GAME_EQ_GAIN_MIN, C.GAME_EQ_GAIN_MAX, C.GAME_EQ_GAIN_CENTER))
        add(_p(f"game_eq_band{n}_freq", SC, GFX, freq_a, freq_min, freq_max, 0))
        if q_a is not None:
            add(_p(f"game_eq_band{n}_q", SC, GFX, q_a, C.GAME_EQ_Q_MIN, C.GAME_EQ_Q_MAX, 0))

    # EQ spectrum analyzer toggle — SECTION_STATUS / type 0x10; reroutes SUB MIX
    # ADC to the FFT overlay (confirmed 2026-06-01).
    add(_p("eq_analyzer", C.SECTION_STATUS, C.SUBTYPE_STATUS_10, C.ADDR_EQ_ANALYZER,
           C.EQ_ANALYZER_OFF, C.EQ_ANALYZER_ON, C.EQ_ANALYZER_OFF))

    # ── Output controls ───────────────────────────────────────────────────────
    add(_p("output_delay_sw",     SC, DLY, C.ADDR_OUTPUT_DELAY_SW,     0, 1, 0))
    add(_p("output_delay_amount", SC, DLY, C.ADDR_OUTPUT_DELAY_AMOUNT, C.OUTPUT_DELAY_AMOUNT_MIN, C.OUTPUT_DELAY_AMOUNT_MAX, 0))
    add(_p("line_out_mode",       SC, SW,  C.ADDR_LINE_OUT_MODE, 0, 2, 0))
    add(_p("usb_out_mode",        SC, SW,  C.ADDR_USB_OUT_MODE,  0, 1, 0))
    add(_p("sub_mix_mode",        SC, SW,  C.ADDR_SUB_MIX_MODE,  0, 2, 0))

    # ── Hardware strip channel assignment (TYPE_STRIP_CONFIG = 0x08) ────────────
    # Addresses 0x00/0x10/0x20/0x30 confirmed 2026-05-20; value range 0–6 (7 channels).
    add(_p("hw_strip_1_ch", SC, LED, C.ADDR_HW_STRIP_1_CH, 0, 6, C.HW_STRIP_CH_MIC))
    add(_p("hw_strip_2_ch", SC, LED, C.ADDR_HW_STRIP_2_CH, 0, 6, C.HW_STRIP_CH_AUX))
    add(_p("hw_strip_3_ch", SC, LED, C.ADDR_HW_STRIP_3_CH, 0, 6, C.HW_STRIP_CH_CHAT))
    add(_p("hw_strip_4_ch", SC, LED, C.ADDR_HW_STRIP_4_CH, 0, 6, C.HW_STRIP_CH_GAME))

    # ── Strip button action assignment (TYPE_STRIP_CONFIG = 0x08) ────────────
    # Addresses 0x04/0x14/0x24/0x34 confirmed 2026-05-22.
    _BTN_MAX = C.STRIP_BUTTON_ACTION_BGM_CAST_NEXT
    add(_p("strip1_button_action", SC, LED, C.ADDR_STRIP1_BUTTON_ACTION, 0, _BTN_MAX, C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_ALL))
    add(_p("strip2_button_action", SC, LED, C.ADDR_STRIP2_BUTTON_ACTION, 0, _BTN_MAX, C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_ALL))
    add(_p("strip3_button_action", SC, LED, C.ADDR_STRIP3_BUTTON_ACTION, 0, _BTN_MAX, C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_ALL))
    add(_p("strip4_button_action", SC, LED, C.ADDR_STRIP4_BUTTON_ACTION, 0, _BTN_MAX, C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_ALL))

    # ── Channel LED colours (TYPE_STRIP_CONFIG = 0x08) ────────────────────────
    for ch, r_a, g_a, b_a in [
        ("mic",  C.ADDR_LED_MIC_R,  C.ADDR_LED_MIC_G,  C.ADDR_LED_MIC_B),
        ("aux",  C.ADDR_LED_AUX_R,  C.ADDR_LED_AUX_G,  C.ADDR_LED_AUX_B),
        ("chat", C.ADDR_LED_CHAT_R, C.ADDR_LED_CHAT_G, C.ADDR_LED_CHAT_B),
        ("game", C.ADDR_LED_GAME_R, C.ADDR_LED_GAME_G, C.ADDR_LED_GAME_B),
    ]:
        add(_p(f"led_{ch}_r", SC, LED, r_a, C.LED_COLOR_MIN, C.LED_COLOR_MAX, 0))
        add(_p(f"led_{ch}_g", SC, LED, g_a, C.LED_COLOR_MIN, C.LED_COLOR_MAX, 0))
        add(_p(f"led_{ch}_b", SC, LED, b_a, C.LED_COLOR_MIN, C.LED_COLOR_MAX, 0))

    return r


REGISTRY: dict[str, Parameter] = _build_registry()

# Reverse lookup: (section, type, addr_hi, addr_lo) → parameter name
# Used by the RX dispatcher to identify incoming frames.
_ADDR_TO_NAME: dict[tuple[int, int, int, int], str] = {
    (p.section, p.param_type, p.addr_hi, p.addr_lo): name
    for name, p in REGISTRY.items()
}


def lookup_by_address(section: int, type_: int, addr_hi: int, addr_lo: int) -> str | None:
    return _ADDR_TO_NAME.get((section, type_, addr_hi, addr_lo))
