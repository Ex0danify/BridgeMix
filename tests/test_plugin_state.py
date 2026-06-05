"""Tests for plugin enable/consent persistence (``bridgemix.plugins.state``)."""
from __future__ import annotations

import pytest

from bridgemix.plugins.state import PluginState


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config_dir() at a temp directory for the duration of a test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def test_defaults_are_empty(isolated_config):
    st = PluginState()
    assert st.has_entry("x") is False
    assert st.is_enabled("x") is False
    assert st.is_consented("x") is False


def test_set_and_read_back(isolated_config):
    st = PluginState()
    st.set_consented("p", True)
    st.set_enabled("p", True)
    assert st.has_entry("p") is True
    assert st.is_consented("p") is True
    assert st.is_enabled("p") is True


def test_persists_across_instances(isolated_config):
    PluginState().set_enabled("p", True)
    assert PluginState().is_enabled("p") is True


def test_forget_removes_entry(isolated_config):
    st = PluginState()
    st.set_enabled("p", True)
    st.forget("p")
    assert PluginState().has_entry("p") is False


def test_malformed_file_reads_as_empty(isolated_config):
    (isolated_config / "bridgemix").mkdir()
    (isolated_config / "bridgemix" / "plugins.json").write_text("}{ not json")
    st = PluginState()
    assert st.is_enabled("anything") is False
