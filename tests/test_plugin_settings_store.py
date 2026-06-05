"""Tests for the SDK per-plugin settings store (``bridgemix.plugins.settings_store``)."""
from __future__ import annotations

import pytest

from bridgemix.plugins.settings_store import SettingsStore


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def test_get_returns_default_when_absent(isolated_config):
    assert SettingsStore("p").get("missing", 5) == 5


def test_set_persists_across_instances(isolated_config):
    SettingsStore("p").set("k", 7)
    assert SettingsStore("p").get("k") == 7


def test_update_merges_and_persists(isolated_config):
    s = SettingsStore("p")
    s.update({"a": 1, "b": 2})
    assert s.as_dict() == {"a": 1, "b": 2}
    assert SettingsStore("p").as_dict() == {"a": 1, "b": 2}


def test_stores_are_isolated_by_id(isolated_config):
    SettingsStore("p1").set("k", "v1")
    assert SettingsStore("p2").get("k") is None


def test_malformed_file_reads_as_empty(isolated_config):
    store_dir = isolated_config / "bridgemix" / "plugin-data"
    store_dir.mkdir(parents=True)
    (store_dir / "p.json").write_text("}{ not json")
    assert SettingsStore("p").get("k") is None
