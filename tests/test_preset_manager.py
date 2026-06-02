"""Tests for JSON preset save/load (``bridgemix.preset.manager``)."""
from __future__ import annotations

import json

import pytest

from bridgemix.device.parameters import REGISTRY
from bridgemix.preset import manager


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "p.json"
    state = {"st_mic_vol": 100, "ps_aux_vol": 50, "mix_link": 1}
    manager.save_preset(path, state)
    loaded = manager.load_preset(path)
    assert loaded["st_mic_vol"] == 100
    assert loaded["ps_aux_vol"] == 50
    assert loaded["mix_link"] == 1


def test_save_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "deep" / "p.json"
    manager.save_preset(path, {"st_mic_vol": 10})
    assert path.exists()


def test_save_excludes_read_only_params(tmp_path):
    path = tmp_path / "p.json"
    # stream_vol is read-only and must never be persisted.
    manager.save_preset(path, {"stream_vol": 64, "st_mic_vol": 10})
    data = json.loads(path.read_text())
    assert "stream_vol" not in data
    assert "st_mic_vol" in data


def test_save_ignores_unknown_state_keys(tmp_path):
    path = tmp_path / "p.json"
    manager.save_preset(path, {"not_a_param": 5, "st_mic_vol": 10})
    data = json.loads(path.read_text())
    assert "not_a_param" not in data


def test_load_skips_out_of_range_values(tmp_path):
    path = tmp_path / "p.json"
    p = REGISTRY["st_mic_vol"]
    path.write_text(json.dumps({"st_mic_vol": p.max_value + 1}))
    loaded = manager.load_preset(path)
    assert "st_mic_vol" not in loaded


def test_load_accepts_range_boundaries(tmp_path):
    path = tmp_path / "p.json"
    p = REGISTRY["st_mic_vol"]
    path.write_text(json.dumps({"st_mic_vol": p.min_value}))
    assert manager.load_preset(path)["st_mic_vol"] == p.min_value


def test_load_skips_read_only_and_unknown(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"stream_vol": 10, "bogus": 1, "st_mic_vol": 20}))
    loaded = manager.load_preset(path)
    assert loaded == {"st_mic_vol": 20}


def test_load_skips_non_int_values(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"st_mic_vol": "loud", "ps_mic_vol": 30}))
    loaded = manager.load_preset(path)
    assert loaded == {"ps_mic_vol": 30}


def test_load_invalid_json_raises_value_error(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not valid json")
    with pytest.raises(ValueError):
        manager.load_preset(path)


def test_load_non_object_json_raises_value_error(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(ValueError):
        manager.load_preset(path)


def test_load_missing_file_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        manager.load_preset(tmp_path / "does_not_exist.json")
