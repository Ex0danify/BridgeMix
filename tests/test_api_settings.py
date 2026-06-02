"""Tests for the REST-API settings store (``bridgemix.api.settings``).

Pure persistence logic — no Qt, no FastAPI.  The module-level ``_API_PATH`` is
redirected to a tmp file, mirroring the routing-store tests.
"""
from __future__ import annotations

import pytest

from bridgemix.api import settings as s
from bridgemix.api.settings import ApiSettings, DEFAULT_HOST, DEFAULT_PORT


@pytest.fixture
def tmp_api(tmp_path, monkeypatch):
    path = tmp_path / "api.json"
    monkeypatch.setattr(s, "_API_PATH", path)
    return path


def test_load_missing_file_returns_defaults(tmp_api):
    loaded = s.load_settings()
    assert loaded == ApiSettings()
    assert loaded.enabled is False
    assert loaded.host == DEFAULT_HOST
    assert loaded.port == DEFAULT_PORT


def test_save_then_load_roundtrip(tmp_api):
    s.save_settings(ApiSettings(enabled=True, host="0.0.0.0", port=9000))
    loaded = s.load_settings()
    assert loaded == ApiSettings(enabled=True, host="0.0.0.0", port=9000)


def test_load_malformed_json_returns_defaults(tmp_api):
    tmp_api.write_text("{ this is not json", encoding="utf-8")
    assert s.load_settings() == ApiSettings()


def test_load_non_object_returns_defaults(tmp_api):
    tmp_api.write_text("[1, 2, 3]", encoding="utf-8")
    assert s.load_settings() == ApiSettings()


def test_load_clamps_out_of_range_port(tmp_api):
    tmp_api.write_text('{"port": 99999}', encoding="utf-8")
    assert s.load_settings().port == DEFAULT_PORT


def test_load_rejects_non_int_port(tmp_api):
    tmp_api.write_text('{"port": "8080"}', encoding="utf-8")
    assert s.load_settings().port == DEFAULT_PORT


def test_load_empty_host_falls_back(tmp_api):
    tmp_api.write_text('{"host": ""}', encoding="utf-8")
    assert s.load_settings().host == DEFAULT_HOST


def test_load_coerces_truthy_enabled(tmp_api):
    tmp_api.write_text('{"enabled": 1}', encoding="utf-8")
    assert s.load_settings().enabled is True


def test_save_creates_parent_dir(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "config" / "api.json"
    monkeypatch.setattr(s, "_API_PATH", nested)
    s.save_settings(ApiSettings(enabled=True))
    assert nested.exists()
    assert s.load_settings().enabled is True
