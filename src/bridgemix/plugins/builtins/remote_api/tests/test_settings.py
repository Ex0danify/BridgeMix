"""Tests for reading Remote API settings out of a plugin store (``from_store``)."""
from __future__ import annotations

from bridgemix.plugins.builtins.remote_api.settings import (
    ApiSettings,
    DEFAULT_HOST,
    DEFAULT_PORT,
    from_store,
)


class _Store:
    """Minimal read-only stand-in for the SDK SettingsStore."""

    def __init__(self, data: dict) -> None:
        self._d = data

    def get(self, key, default=None):
        return self._d.get(key, default)


def test_empty_store_yields_defaults():
    assert from_store(_Store({})) == ApiSettings()


def test_reads_enabled_and_port():
    s = from_store(_Store({"enabled": True, "port": 9000}))
    assert s.enabled is True
    assert s.port == 9000
    assert s.host == DEFAULT_HOST  # host is fixed, never read from the store


def test_coerces_truthy_enabled():
    assert from_store(_Store({"enabled": 1})).enabled is True


def test_out_of_range_port_falls_back():
    assert from_store(_Store({"port": 99999})).port == DEFAULT_PORT


def test_non_int_port_falls_back():
    assert from_store(_Store({"port": "8080"})).port == DEFAULT_PORT
