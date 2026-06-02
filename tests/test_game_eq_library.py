"""Tests for the Game EQ preset library (``bridgemix.preset.game_eq_library``)."""
from __future__ import annotations

import json

import pytest

from bridgemix.device.parameters import REGISTRY
from bridgemix.preset import game_eq_library as lib


@pytest.fixture
def tmp_library(tmp_path, monkeypatch):
    """Redirect the library directory to a temp path for the duration of a test."""
    monkeypatch.setattr(lib, "_LIBRARY_DIR", tmp_path / "game_eq_library")
    return tmp_path


def test_curve_param_names_derived_from_registry():
    assert "game_eq_enable" in lib.CURVE_PARAM_NAMES
    assert any(n.startswith("game_eq_band") for n in lib.CURVE_PARAM_NAMES)
    assert all(n in REGISTRY for n in lib.CURVE_PARAM_NAMES)


def test_capture_live_keeps_only_curve_params():
    state = {"game_eq_enable": 1, "st_mic_vol": 99, "game_limiter": 1}
    snap = lib.capture_live(state)
    assert snap == {"game_eq_enable": 1, "game_limiter": 1}


def test_save_and_load_round_trip(tmp_library):
    params = {"game_eq_enable": 1, "game_eq_band1_gain": REGISTRY["game_eq_band1_gain"].max_value}
    lib.save_library_preset("My Curve", params)
    loaded = lib.load_library_preset("My Curve")
    assert loaded["game_eq_enable"] == 1
    assert loaded["game_eq_band1_gain"] == REGISTRY["game_eq_band1_gain"].max_value


def test_save_filters_out_of_range_and_noncurve(tmp_library):
    bad_gain = REGISTRY["game_eq_band1_gain"].max_value + 1
    path = lib.save_library_preset("X", {
        "game_eq_band1_gain": bad_gain,   # out of range → dropped
        "st_mic_vol": 50,                  # not a curve param → dropped
        "game_eq_enable": 1,               # valid
    })
    stored = json.loads(path.read_text())["parameters"]
    assert stored == {"game_eq_enable": 1}


def test_slugify_sanitizes_filename(tmp_library):
    path = lib.save_library_preset("Bass/Boost: V2", {"game_eq_enable": 1})
    assert "/" not in path.name
    assert ":" not in path.name
    assert path.suffix == ".json"


def test_list_includes_factory_presets(tmp_library):
    names = lib.list_library()
    assert len(names) > 0
    from bridgemix.preset.game_eq_factory import FACTORY_PRESETS
    for fname in FACTORY_PRESETS:
        assert fname in names


def test_user_preset_appears_in_list(tmp_library):
    lib.save_library_preset("Custom Curve", {"game_eq_enable": 1})
    assert "Custom Curve" in lib.list_library()


def test_delete_removes_user_preset(tmp_library):
    lib.save_library_preset("Temp", {"game_eq_enable": 1})
    assert lib.delete_library_preset("Temp") is True
    assert "Temp" not in lib.list_library()


def test_delete_missing_returns_false(tmp_library):
    assert lib.delete_library_preset("nope") is False


def test_load_factory_preset_by_name(tmp_library):
    from bridgemix.preset.game_eq_factory import FACTORY_PRESETS
    name = next(iter(FACTORY_PRESETS))
    loaded = lib.load_library_preset(name)
    assert isinstance(loaded, dict)
    assert loaded == FACTORY_PRESETS[name]


def test_load_missing_raises(tmp_library):
    with pytest.raises(ValueError):
        lib.load_library_preset("absolutely-not-here")


def test_user_file_overrides_factory(tmp_library):
    from bridgemix.preset.game_eq_factory import FACTORY_PRESETS
    name = next(iter(FACTORY_PRESETS))
    # Saving under a factory name should make load return the user's params.
    lib.save_library_preset(name, {"game_eq_enable": 0})
    assert lib.load_library_preset(name) == {"game_eq_enable": 0}
    # And the name should not be duplicated in the listing.
    assert lib.list_library().count(name) == 1
