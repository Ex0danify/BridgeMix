"""Tests for the Roland export translation table (``bridgemix.preset.roland_map``)."""
from __future__ import annotations

import json

import pytest

from bridgemix.preset import roland_map


def _export(**extra) -> dict:
    base = {"ExportModelName": "BRIDGECAST"}
    base.update(extra)
    return base


def test_translate_live_state_bare_keys():
    raw = _export(MixLevelStMic=100, MixLevelPsAux=42)
    live = roland_map.translate_live_state(raw)
    assert live["st_mic_vol"] == 100
    assert live["ps_aux_vol"] == 42


def test_wrong_model_name_raises():
    with pytest.raises(ValueError):
        roland_map.parse_roland_file_dict({"ExportModelName": "SOMETHING_ELSE"})


def test_missing_model_name_raises():
    with pytest.raises(ValueError):
        roland_map.parse_roland_file_dict({})


def test_bank_prefix_groups_into_slots():
    raw = _export(
        MicEfxMemory1_ReverbSwitch=1,
        MicEfxMemory2_ReverbSwitch=0,
    )
    slots = roland_map.parse_roland_file_dict(raw)
    assert slots[1]["reverb_switch"] == 1
    assert slots[2]["reverb_switch"] == 0


def test_bare_keys_land_in_slot_zero():
    slots = roland_map.parse_roland_file_dict(_export(MixLevelStMic=77))
    assert slots[0]["st_mic_vol"] == 77


def test_non_int_values_are_skipped():
    raw = _export(MixLevelStMic=10, SomeSfxPath="C:/audio/clip.wav")
    live = roland_map.translate_live_state(raw)
    assert live == {"st_mic_vol": 10}


def test_unknown_stem_is_skipped():
    live = roland_map.translate_live_state(_export(TotallyUnknownKey=5, MixLevelStMic=1))
    assert "TotallyUnknownKey" not in live
    assert live["st_mic_vol"] == 1


def test_explicitly_unmapped_stem_is_skipped():
    # MixLevelStHdmi is mapped to None (documented, no REGISTRY equivalent).
    live = roland_map.translate_live_state(_export(MixLevelStHdmi=64))
    assert "MixLevelStHdmi" not in live
    assert live == {}


def test_game_efx_bank_short_form():
    # Inside a GameEfxMemory bank Roland drops the "Game" prefix on EQ band stems.
    slots = roland_map.parse_roland_file_dict(_export(GameEfxMemory3_EqBand1Gain=20))
    assert slots[3]["game_eq_band1_gain"] == 20


def test_parse_roland_file_reads_from_disk(tmp_path):
    path = tmp_path / "preset.brdgcEfx"
    path.write_text(json.dumps(_export(MixLevelStMic=55)), encoding="utf-8")
    slots = roland_map.parse_roland_file(path)
    assert slots[0]["st_mic_vol"] == 55
