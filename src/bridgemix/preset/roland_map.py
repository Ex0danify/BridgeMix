"""
Roland BridgeCast → BridgeMix REGISTRY translation table.

Roland's JSON export files (.brdgcBackup, .brdgcProfile, .brdgcEfx) use
CamelCase "stem" names.  Prefixed bank keys strip the slot prefix first:
  MicEfxMemory2_ReverbSwitch  →  stem = "ReverbSwitch"
  ProfMemMicCleanup3_MicEqBand1Gain  →  stem = "MicEqBand1Gain"

The table maps each stem to either:
  • a BridgeMix REGISTRY parameter name  (str)
  • None – key is documented but has no current REGISTRY equivalent;
            kept here for future expansion and logging transparency.

parse_roland_file() is the public entry point.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# ── Stems that appear ONLY inside GameEfxMemory* banks ───────────────────────
# Roland omits the "Game" prefix for EQ bands when stored inside a game-EFX
# bank slot — e.g. GameEfxMemory1_EqBand1Gain (not GameEqBand1Gain).
# These extra entries handle the short form; the full "GameEq*" forms are also
# present in the main table for live-state and ProfMemGameEffects* usage.
_GAME_EFX_BANK_EXTRAS: dict[str, str | None] = {
    **{f"EqBand{n}Gain":      f"game_eq_band{n}_gain" for n in range(1, 11)},
    **{f"EqBand{n}Frequency": f"game_eq_band{n}_freq" for n in range(1, 11)},
    **{f"EqBand{n}Q":         f"game_eq_band{n}_q"    for n in range(2, 10)},
    "EqSwitch":    "game_eq_enable",
    "HdmiEqSwitch": None,   # HDMI EQ inside game bank — no REGISTRY param
}

# ── Main translation table ────────────────────────────────────────────────────
ROLAND_TO_REGISTRY: dict[str, str | None] = {

    # ── Stream mix volumes ────────────────────────────────────────────────────
    "MixLevelStMic":   "st_mic_vol",
    "MixLevelStAux":   "st_aux_vol",
    "MixLevelStChat":  "st_chat_vol",
    "MixLevelStGame":  "st_game_vol",
    "MixLevelStMusic": "st_music_vol",
    "MixLevelStSys":   "st_sys_vol",
    "MixLevelStSfx":   "st_sfx_vol",
    "MixLevelStHdmi":  None,   # HDMI path — no BridgeMix param

    # ── Personal mix volumes ──────────────────────────────────────────────────
    "MixLevelPsMic":   "ps_mic_vol",
    "MixLevelPsAux":   "ps_aux_vol",
    "MixLevelPsChat":  "ps_chat_vol",
    "MixLevelPsGame":  "ps_game_vol",
    "MixLevelPsMusic": "ps_music_vol",
    "MixLevelPsSys":   "ps_sys_vol",
    "MixLevelPsSfx":   "ps_sfx_vol",
    "MixLevelPsHdmi":  None,   # HDMI path — no BridgeMix param

    # ── Mix-link differentials (stored by Roland; not MIDI addressable) ───────
    "MixLevelDiffMic":   None,
    "MixLevelDiffAux":   None,
    "MixLevelDiffChat":  None,
    "MixLevelDiffGame":  None,
    "MixLevelDiffMusic": None,
    "MixLevelDiffSys":   None,
    "MixLevelDiffSfx":   None,
    "MixLevelDiffHdmi":  None,
    "VolDiffMic":        None,  # same class

    # ── Stream mutes (0=muted 1=active) ──────────────────────────────────────
    "MuteStMic":   "st_mic_mute",
    "MuteStAux":   "st_aux_mute",
    "MuteStChat":  "st_chat_mute",
    "MuteStGame":  "st_game_mute",
    "MuteStMusic": "st_music_mute",
    "MuteStSys":   "st_sys_mute",
    "MuteStHdmi":  None,

    # ── Personal mutes ────────────────────────────────────────────────────────
    "MutePsMic":   "ps_mic_mute",
    "MutePsAux":   "ps_aux_mute",
    "MutePsChat":  "ps_chat_mute",
    "MutePsGame":  "ps_game_mute",
    "MutePsMusic": "ps_music_mute",
    "MutePsSys":   "ps_sys_mute",
    "MutePsHdmi":  None,

    # ── Output mutes ──────────────────────────────────────────────────────────
    "MuteUsbStOut":  "mute_stream_out",
    "MuteUsbPsOut":  "mute_submix_out",
    "MutePhonesOut": "mute_phones_out",
    "MuteLineOut":   "mute_line_out",
    "MuteMicOut":    None,  # mic direct out — device address unconfirmed

    # ── Hardware output volumes (read-only in BridgeMix; stored by Roland) ───
    "VolLine":     None,   # line_out is read-only
    "VolPhones":   None,   # phones_vol is read-only
    "VolStreaming": None,   # stream_vol is read-only
    # VolMic / VolPersonal overlap with MixLevel* fields — omit to avoid
    # double-write; the MixLevel* keys above handle the same values.
    "VolMic":      None,
    "VolPersonal": None,

    # ── Global system ─────────────────────────────────────────────────────────
    "MainLedBrightness": "led_brightness",
    "MainIndicatorType": "indicator_type",
    "MainPhoneBoost":    "phones_gain",
    "MainMuteDispType":  "mute_display",

    # ── SFX pad volumes ───────────────────────────────────────────────────────
    "MainSfxAVol": "sfx_a_vol",
    "MainSfxBVol": "sfx_b_vol",
    # MainSfxAName01..32 / MainSfxBName01..32 — file path bytes, not MIDI params

    # ── Mic input / gain ──────────────────────────────────────────────────────
    "SelMicIn":     "mic_source",
    "48vSw":        "mic_phantom",
    "MicXlrGain":   "mic_gain_xlr",
    "MicHsGain":    "mic_gain_headset",
    "MicKnobPsSrc": "mic_knob_target",
    "MicFxNo":      "mic_fx_preset",
    "MicFxSw":      "mic_fx_enable",
    "MicFxSwLock":  None,   # FX lock toggle — no REGISTRY param
    "GameFxNo":     "game_eq_preset",
    "GameFxSw":     None,   # game FX global enable — separate from game_eq_enable

    # ── Mic Noise Suppressor ──────────────────────────────────────────────────
    "MicNsSwitch":    "mic_ns",
    "MicNsThreshold": "mic_ns_level",
    "MicNsType":      "mic_ns_type",
    # Adaptive NS (TYPE 1):
    "MicFftNsLevel":        "mic_ns_adp_level",
    "MicFftNsNormAttack":   None,   # adaptive NS attack — no REGISTRY param
    "MicFftNsNormRelease":  None,   # adaptive NS release — no REGISTRY param
    # Expander NS (TYPE 2, via TYPE_MIC_FX_EXT):
    "MicNsExpRange":      "mic_ns_exp_level",   # range ≈ level/threshold
    "MicNsExpRelease":    "mic_ns_exp_release",
    "MicNsExpThreshold":  None,   # separate expander threshold — not confirmed
    "MicNsExpFastAttack": None,   # fast-attack flag — not in REGISTRY
    # Gate / legacy NS:
    "MicNsAttack":  "mic_ns_attack",
    "MicNsRelease": "mic_ns_release",

    # ── Mic Low-Cut (HPF) ─────────────────────────────────────────────────────
    "MicHpfSwitch":    "mic_low_cut",
    "MicHpfFrequency": "mic_low_cut_freq",

    # ── Mic De-esser ─────────────────────────────────────────────────────────
    "MicDeEsserSwitch": "mic_de_esser",
    "MicDeEsserDepth":  "mic_de_esser_depth",

    # ── Mic Compressor (Legacy / Modern) ──────────────────────────────────────
    "MicCompSwitch":    "mic_compressor",
    "MicCompAttack":    "mic_compressor_attack",
    "MicCompRelease":   "mic_compressor_release",
    "MicCompThreshold": "mic_compressor_threshold",
    "MicCompRatio":     "mic_compressor_ratio",
    "MicCompPostGain":  "mic_compressor_post_gain",
    # Modern / LA-2A compressor (TYPE_MIC_FX_EXT):
    "MicCompType":          "mic_comp_mode",
    "MicLa2aOneKnobVal":    "mic_comp_mod_amount",
    "MicLa2aPeakReduction": "mic_comp_mod_peak",
    "MicLa2aGain":          "mic_comp_mod_gain",
    "MicLa2aHf":            None,   # LA-2A HF shelf — no REGISTRY param
    "MicLa2aLimitMode":     None,   # LA-2A limit mode — no REGISTRY param
    "MicLa2aOneKnobType":   None,   # LA-2A one-knob type — no REGISTRY param

    # ── Mic EQ (10 bands) ─────────────────────────────────────────────────────
    "MicEqSwitch": "mic_eq_enable",
    **{f"MicEqBand{n}Gain":      f"mic_eq_band{n}_gain" for n in range(1, 11)},
    **{f"MicEqBand{n}Frequency": f"mic_eq_band{n}_freq" for n in range(1, 11)},
    **{f"MicEqBand{n}Q":         f"mic_eq_band{n}_q"    for n in range(2, 10)},

    # ── Voice / Voice-Changer ─────────────────────────────────────────────────
    "VtSwitch":            None,   # voice changer on/off (per-slot state, not direct param)
    "VtPitch":             "voice_pitch",
    "VtFormant":           "voice_format",
    "VtConsonantMode":     "voice_mode",
    "VtRobotSwitch":       None,   # robot effect — no REGISTRY param
    "VtRobotVariation":    None,
    "VtMegaphoneSwitch":   None,   # megaphone effect — no REGISTRY param
    "VtMegaphoneVariation":None,

    # ── Reverb ───────────────────────────────────────────────────────────────
    "MicReverbSwitch":   "reverb_switch",
    "MicReverbSize":     "reverb_size",
    "MicReverbWetLevel": "reverb_level",
    # ReverbSwitch / ReverbSize / ReverbWetLevel appear as plain stems inside
    # MicEfxMemory* banks (without the "Mic" prefix):
    "ReverbSwitch":   "reverb_switch",
    "ReverbSize":     "reverb_size",
    "ReverbWetLevel": "reverb_level",

    # ── Mic-FX slot LED colors (different from channel-strip LEDs) ────────────
    "MicFxLedColorR": None,   # no REGISTRY param — FX slot indicator
    "MicFxLedColorG": None,
    "MicFxLedColorB": None,

    # ── Game EQ (10 bands) ────────────────────────────────────────────────────
    "GameEqSwitch":  "game_eq_enable",
    **{f"GameEqBand{n}Gain":      f"game_eq_band{n}_gain" for n in range(1, 11)},
    **{f"GameEqBand{n}Frequency": f"game_eq_band{n}_freq" for n in range(1, 11)},
    **{f"GameEqBand{n}Q":         f"game_eq_band{n}_q"    for n in range(2, 10)},

    # ── Game FX compressor / limiter ──────────────────────────────────────────
    "GameCompSwitch":  "game_limiter",
    "GameCompLevel":   "game_limiter_level",
    "GameCompRelease": "game_limiter_release",

    # ── Game virtual surround ─────────────────────────────────────────────────
    # Live-state key forms (with "GameFx" / "GameSurr" prefix):
    "GameFxSurrSwitch":      "game_vsurround",
    "GameFxSurrFrongAngle":  "game_vsurround_front_angle",   # Roland typo: "Frong"
    "GameFxSurrBackAngle":   None,   # back angle — no REGISTRY param
    "GameFxSurrSideAngle":   None,   # side angle — no REGISTRY param
    "GameSurrOutMode":       "game_vsurround_output",
    "GameSurrOutSpAngle":    "game_vsurround_listen_angle",
    "GameSurrReverbSwitch":  None,   # surround reverb — no REGISTRY param
    # Short-stem forms inside GameEfxMemory* / ProfMemGameEffects* banks:
    "SurrSwitch":      "game_vsurround",
    "SurrFrongAngle":  "game_vsurround_front_angle",
    "SurrBackAngle":   None,
    "SurrSideAngle":   None,
    # Game-FX slot LED colors:
    "GameFxFxLedColorR": None,
    "GameFxFxLedColorG": None,
    "GameFxFxLedColorB": None,
    # HDMI-related game parameters:
    "GameFxHdmiEqSwitch": None,   # HDMI EQ for game — no REGISTRY param
    "HdmiCompSwitch":     None,   # HDMI compressor — no REGISTRY param
    "HdmiEqSwitch":       None,   # HDMI EQ — no REGISTRY param

    # ── Chat FX ──────────────────────────────────────────────────────────────
    "ChatDeEsserSwitch":     "chat_de_esser",
    "ChatDeEsserDepth":      "chat_de_esser_depth",
    "ChatCompSwitch":        "chat_compressor",
    "ChatCompAttack":        "chat_compressor_attack",
    "ChatCompRelease":       "chat_compressor_release",
    "ChatCompThreshold":     "chat_compressor_threshold",
    "ChatCompRatio":         "chat_compressor_ratio",
    "ChatCompPostGain":      "chat_compressor_post_gain",

    # ── Output delay ─────────────────────────────────────────────────────────
    "UsbStDlySwitch": "output_delay_sw",
    "UsbStDlyTime":   "output_delay_amount",

    # ── Output routing ────────────────────────────────────────────────────────
    "SelLineOut":    "line_out_mode",
    "SelUsbGenToPc": "usb_out_mode",
    "SelUsbPsOut":   None,   # sub-mix USB routing — no REGISTRY param
    "StatusLink":    None,   # link-state flag — semantics unclear

    # ── Channel strip LED colours ─────────────────────────────────────────────
    "LedColorMicR":  "led_mic_r",
    "LedColorMicG":  "led_mic_g",
    "LedColorMicB":  "led_mic_b",
    "LedColorAuxR":  "led_aux_r",
    "LedColorAuxG":  "led_aux_g",
    "LedColorAuxB":  "led_aux_b",
    "LedColorChatR": "led_chat_r",
    "LedColorChatG": "led_chat_g",
    "LedColorChatB": "led_chat_b",
    "LedColorGameR": "led_game_r",
    "LedColorGameG": "led_game_g",
    "LedColorGameB": "led_game_b",
    "LedSwMic":      None,   # per-strip LED enable — no REGISTRY param
    "LedSwAux":      None,
    "LedSwChat":     None,
    "LedSwGame":     None,

    # ── Hardware strip channel assignment ─────────────────────────────────────
    "AssignGenAudioMic":  "hw_strip_1_ch",
    "AssignGenAudioAux":  "hw_strip_2_ch",
    "AssignGenAudioChat": "hw_strip_3_ch",
    "AssignGenAudioGame": "hw_strip_4_ch",

    # ── Strip button actions ──────────────────────────────────────────────────
    "AssignFuncMic":  "strip1_button_action",
    "AssignFuncAux":  "strip2_button_action",
    "AssignFuncChat": "strip3_button_action",
    "AssignFuncGame": "strip4_button_action",

    # ── Advanced multi-source strip routing (vendor-specific, no REGISTRY) ────
    "AssignVenAudioMic":   None, "AssignVenAudioAux":   None,
    "AssignVenAudioChat":  None, "AssignVenAudioGame":  None,
    "AssignVenAudioCh5":   None, "AssignVenAudioCh5X":  None,
    "AssignVenAudioCh6":   None, "AssignVenAudioCh6X":  None,
    "AssignVenAudioCh7":   None, "AssignVenAudioCh7X":  None,
    "AssignVenAudioCh8X":  None,
    "AssignVenGenAudioCh5": None, "AssignVenGenAudioCh6": None,
    "AssignVenGenAudioCh7": None, "AssignVenGenAudioCh8": None,
    "AssignVenGenAudioCh9": None, "AssignVenGenAudioGame": None,
    "AssignVenGenXAudioChat": None, "AssignVenGenXAudioHdmi": None,
    "AssignVenGenXAudioMic":  None,
    "AssignVenXAudioChat": None, "AssignVenXAudioGame": None,
    "AssignVenXAudioHdmi": None, "AssignVenXAudioMic":  None,
    "AssignGenAudioCh5X":  None,
    "AssignGenXAudioChat": None, "AssignGenXAudioGame": None,
    "AssignGenXAudioHdmi": None, "AssignGenXAudioMic":  None,

    # ── BGM / SFX pad settings ────────────────────────────────────────────────
    "BgmHistories":     None, "BgmVolume": None,
    "BgmSfxSettings_A":None, "BgmSfxSettings_B":None,
    "BgmSfxSettings_C":None, "BgmSfxSettings_D":None,
    "PadSetNo":         None,

    # ── Profile metadata ──────────────────────────────────────────────────────
    "MainProfileNo": None,

    # ── Preset / profile name encoding (packed byte-pairs) ───────────────────
    "Name0102": None, "Name0304": None, "Name0506": None, "Name0708": None,
    "Name0910": None, "Name1112": None, "Name1314": None, "Name1516": None,
    "Name1718": None,
    "ProfileName0102": None, "ProfileName0304": None, "ProfileName0506": None,
    "ProfileName0708": None, "ProfileName0910": None, "ProfileName1112": None,
    "ProfileName1314": None, "ProfileName1516": None, "ProfileName1718": None,

    # ── Profile-slot SFX file paths ───────────────────────────────────────────
    **{f"ProfileSfx_{s}_{c}": None for s in range(5) for c in "ABCD"},

    # ── Video / HDMI input settings ───────────────────────────────────────────
    "HdmiInput":             None, "MainVideoEditMode":     None,
    "MainVideoHdcpSwitch":   None, "MainVideoHdmiAudioChAllocation": None,
    "MainVideoHdmiAudioChCount": None, "MainVideoHdmiIn1Connect": None,
    "MainVideoHdmiIn1Hdcp":  None, "MainVideoHdmiIn2Connect": None,
    "MainVideoHdmiIn2Hdcp":  None, "MainVideoHdmiInput":     None,
    "MainVideoIntEditType":  None, "MainVideoUvcAutoOnSw":   None,
    "MainVideoUvcFormat":    None, "MainVideoUvcOutputSwStatus": None,

    # ── Streaming / firmware ──────────────────────────────────────────────────
    "MainStatusStreaming": None,
    "BootMode":            None, "ExportModelName":    None,
    "TargetName":          None, "ParameterVersion":   None,
    "ProgramBuildNumber":  None, "ProgramVersionNumber": None,
}

# Merge in the short-form game-EFX bank extras
ROLAND_TO_REGISTRY.update(_GAME_EFX_BANK_EXTRAS)


# ── Bank prefix extraction ────────────────────────────────────────────────────

# Matches "BankNameN_Stem" where N is one or more digits.
# Groups: (bank_prefix, slot_str, stem)
_BANK_RE = re.compile(r'^([A-Za-z]+)(\d+)_(.+)$')

# All known top-level bank names (used for slot grouping).
# The set is deliberately open: unknown prefixes fall through to slot 0.
_KNOWN_BANKS: frozenset[str] = frozenset({
    "MicEfxMemory",
    "GameEfxMemory",
    "ProfMemMicCleanup",
    "ProfMemMicEffects",
    "ProfMemMicLa2aComp",
    "ProfMemGameEffects",
    "ProfMemChatEffects",
    "ProfMemMixer",
    "ProfMemPanelAssign",
    "ProfMemStreamingEffects",
    "ProfileMemory",
})

# Distinguishes "key absent from table" from "key present but mapped to None"
_SENTINEL = object()


def _translate_stem(stem: str) -> str | None | object:
    return ROLAND_TO_REGISTRY.get(stem, _SENTINEL)


def parse_roland_file(path: Path) -> dict[int, dict[str, int]]:
    """Parse a Roland native export file and return per-slot REGISTRY params.

    Supports .brdgcBackup, .brdgcProfile, and .brdgcEfx files.

    Returns
    -------
    dict[int, dict[str, int]]
        Slot-indexed mapping where keys are 1-based slot numbers.
        Slot 0 is reserved for bare live-state keys (found in .brdgcBackup
        with no bank prefix).

    Raises
    ------
    ValueError
        If the file is not a recognised Roland BridgeCast export.
    """
    raw: dict = json.loads(path.read_text(encoding="utf-8"))
    return parse_roland_file_dict(raw, source=path.name)


def translate_live_state(raw: dict) -> dict[str, int]:
    """Convenience wrapper: extract only the slot-0 (live state) params."""
    slots = parse_roland_file_dict(raw)
    return slots.get(0, {})


def parse_roland_file_dict(raw: dict, source: str = "<dict>") -> dict[int, dict[str, int]]:
    """Parse an already-loaded Roland BridgeCast export dict into per-slot params.

    ``source`` is only used for log messages (e.g. the originating file name).
    Raises ValueError if the dict is not a recognised Roland BridgeCast export.
    """
    if raw.get("ExportModelName") != "BRIDGECAST":
        raise ValueError(
            f"{source!r} does not appear to be a Roland BridgeCast export "
            f"(ExportModelName={raw.get('ExportModelName')!r})."
        )

    slots: dict[int, dict[str, int]] = {}
    unmapped: list[str] = []

    for key, value in raw.items():
        if not isinstance(value, int):
            continue   # skip strings and nested objects (e.g. SFX paths)

        m = _BANK_RE.match(key)
        if m:
            slot = int(m.group(2))
            stem = m.group(3)
        else:
            slot = 0
            stem = key

        result = _translate_stem(stem)
        if result is _SENTINEL:
            # Completely unknown — collect for a single debug log line
            unmapped.append(stem)
            continue
        if result is None:
            # Known but intentionally unmapped
            continue

        registry_name: str = result  # type: ignore[assignment]
        slots.setdefault(slot, {})[registry_name] = value

    if unmapped:
        unique = sorted(set(unmapped))
        log.debug(
            "roland_map: %d stems had no translation entry in %s: %s",
            len(unique), source, unique,
        )

    mapped = sum(len(v) for v in slots.values())
    log.info(
        "roland_map: parsed %s → %d slots, %d parameters mapped",
        source, len(slots), mapped,
    )
    return slots
