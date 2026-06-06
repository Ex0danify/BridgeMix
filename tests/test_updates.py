"""Tests for the update checker (``bridgemix.updates``)."""
from __future__ import annotations

from bridgemix import updates


def test_check_falls_back_to_stale_cache_when_offline(monkeypatch):
    """A failed network fetch returns the stale cache, not ``None``."""
    monkeypatch.setattr(updates, "current_version", lambda: "1.0.0")
    monkeypatch.setattr(
        updates, "_read_cache",
        lambda: {"checked_at": 0, "latest": "2.0.0", "url": "https://example/2.0.0"},
    )
    monkeypatch.setattr(updates, "_fetch_latest", lambda: None)   # network down

    info = updates.check(force=True)

    assert info is not None
    assert info.latest == "2.0.0"
    assert info.url == "https://example/2.0.0"
    assert info.available
