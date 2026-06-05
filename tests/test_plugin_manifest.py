"""Tests for plugin manifest parsing and host-API compatibility matching."""
from __future__ import annotations

import pytest

from bridgemix.plugins.manifest import (
    ManifestError,
    PluginManifest,
    is_compatible,
    parse_manifest,
)


def _valid_raw(**overrides) -> dict:
    raw = {
        "id": "com.example.demo",
        "name": "Demo",
        "version": "1.0.0",
        "entry_point": "demo:DemoPlugin",
    }
    raw.update(overrides)
    return raw


# ── parse_manifest ──────────────────────────────────────────────────────────────

def test_minimal_manifest_parses_with_defaults():
    m = parse_manifest(_valid_raw())
    assert isinstance(m, PluginManifest)
    assert m.id == "com.example.demo"
    assert m.host_api == "*"          # default: matches any host
    assert m.requires == ()
    assert m.permissions == ()
    assert m.entry_module == "demo"
    assert m.entry_attr == "DemoPlugin"


def test_full_manifest_round_trips_fields():
    m = parse_manifest(_valid_raw(
        description="d", maintainer="Jane", homepage="http://x",
        license="MIT", host_api=">=1.0,<2.0",
        requires=["foo>=1"], permissions=["network", "device.read"],
    ))
    assert m.requires == ("foo>=1",)
    assert m.permissions == ("network", "device.read")
    assert m.host_api == ">=1.0,<2.0"


@pytest.mark.parametrize("missing", ["id", "name", "version", "entry_point"])
def test_missing_required_field_raises(missing):
    raw = _valid_raw()
    del raw[missing]
    with pytest.raises(ManifestError):
        parse_manifest(raw)


def test_blank_required_field_raises():
    with pytest.raises(ManifestError):
        parse_manifest(_valid_raw(name="   "))


def test_entry_point_without_colon_raises():
    with pytest.raises(ManifestError):
        parse_manifest(_valid_raw(entry_point="demo"))


def test_requires_must_be_list_of_strings():
    with pytest.raises(ManifestError):
        parse_manifest(_valid_raw(requires="foo"))
    with pytest.raises(ManifestError):
        parse_manifest(_valid_raw(requires=[1, 2]))


# ── is_compatible ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spec", ["", "*", "  "])
def test_wildcard_specs_always_match(spec):
    assert is_compatible(spec, "1.0.0") is True


@pytest.mark.parametrize("spec,version,expected", [
    (">=1.0,<2.0", "1.0.0", True),
    (">=1.0,<2.0", "1.5.0", True),
    (">=1.0,<2.0", "2.0.0", False),
    (">=1.0,<2.0", "0.9.0", False),
    (">=1.2", "1.1.0", False),
    (">=1.2", "1.2.0", True),
    ("==1.0.0", "1.0.0", True),
    ("==1.0.0", "1.0.1", False),
    ("!=1.0.0", "1.0.1", True),
    ("1.0", "1.0.0", True),          # bare version == equality
    ("1.0", "1.1.0", False),
])
def test_version_specs(spec, version, expected):
    assert is_compatible(spec, version) is expected


def test_unparseable_clause_fails_closed():
    # An operator with no version is meaningless → refuse rather than guess.
    assert is_compatible(">=", "1.0.0") is False
