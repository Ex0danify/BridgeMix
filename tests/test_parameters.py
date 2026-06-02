"""Tests for the parameter REGISTRY and address lookup
(``bridgemix.device.parameters``)."""
from __future__ import annotations

import pytest

from bridgemix.device import constants as C
from bridgemix.device.parameters import (
    REGISTRY,
    Parameter,
    lookup_by_address,
)


def test_registry_non_empty():
    assert len(REGISTRY) > 0


def test_every_registered_param_has_addr_lo_zero():
    # AGENTS.md invariant: all known parameters use addr_lo == 0x00.  The bulk RX
    # dispatcher relies on this (it hardcodes 0x00 in lookups).
    offenders = [name for name, p in REGISTRY.items() if p.addr_lo != 0x00]
    assert offenders == []


def test_default_within_declared_range():
    for name, p in REGISTRY.items():
        assert p.min_value <= p.default_value <= p.max_value, name


def test_min_not_greater_than_max():
    for name, p in REGISTRY.items():
        assert p.min_value <= p.max_value, name


def test_parameter_name_matches_registry_key():
    for name, p in REGISTRY.items():
        assert p.name == name


def test_lookup_round_trips_for_all_params():
    for name, p in REGISTRY.items():
        assert lookup_by_address(p.section, p.param_type, p.addr_hi, p.addr_lo) == name


def test_lookup_unknown_returns_none():
    assert lookup_by_address(0x7E, 0x7E, 0x7E, 0x7E) is None


def test_addresses_are_unique_per_section_type():
    # Two parameters must never share the same (section, type, addr) tuple, or the
    # reverse lookup would be ambiguous.
    seen: dict[tuple[int, int, int, int], str] = {}
    for name, p in REGISTRY.items():
        key = (p.section, p.param_type, p.addr_hi, p.addr_lo)
        assert key not in seen, f"{name} collides with {seen.get(key)}"
        seen[key] = name


def test_read_only_params_are_registered():
    # The hardware monitor knobs and high-bit surround angles are read-only.
    for name in ("stream_vol", "phones_vol", "line_out",
                 "game_vsurround_surround_angle", "game_vsurround_back_angle"):
        assert REGISTRY[name].read_only is True


def test_writable_fader_param_is_not_read_only():
    assert REGISTRY["submix_vol"].read_only is False


def test_parameter_is_frozen_dataclass():
    p = REGISTRY["st_mic_vol"]
    with pytest.raises(Exception):
        p.default_value = 99  # type: ignore[misc]


def test_st_mic_vol_wiring_matches_constants():
    p = REGISTRY["st_mic_vol"]
    assert p.section == C.SECTION_CHANNEL
    assert p.param_type == C.TYPE_FADER
    assert p.addr_hi == C.ADDR_ST_MIC_VOL
    assert (p.min_value, p.max_value) == (C.VOLUME_MIN, C.VOLUME_MAX)


def test_mute_polarity_constants():
    # 0 = muted, 1 = active — bus mutes use MUTE_ON/MUTE_OFF as range.
    p = REGISTRY["st_mic_mute"]
    assert p.min_value == C.MUTE_ON == 0
    assert p.max_value == C.MUTE_OFF == 1
