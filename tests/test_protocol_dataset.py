"""Consistency checks for the protocol dataset (``bridgemix.device.protocol``)."""

from __future__ import annotations

from collections import Counter

import pytest

from bridgemix.device import protocol
from bridgemix.device.parameters import REGISTRY
from bridgemix.device.protocol import Family, Kind, firmware

DS = protocol.load()
PARAMS = DS.params


def test_header_counts_match_sections():
    counts = DS.header["counts"]
    assert counts == {
        "parameters": len(PARAMS),
        "blocks": len(DS.blocks),
        "values": len(DS.values),
        "sync": len(DS.sync),
        "commands": len(DS.commands),
        "meters": len(DS.meters),
    }


def test_addresses_unique_and_word_aligned():
    assert len({p.address for p in PARAMS}) == len(PARAMS)
    assert all(p.address >> 24 == 0x7F and p.address % 2 == 0 for p in PARAMS)


def test_block_matches_address():
    for p in PARAMS:
        sec, typ = f"{p.address:08x}"[2:4], f"{p.address:08x}"[4:6]
        assert p.block == f"{sec}/{typ}", hex(p.address)


def test_names_unique_per_memory_and_bank():
    keys = Counter((p.name, p.memory, p.bank) for p in PARAMS if p.name and not p.alias_of)
    assert [k for k, n in keys.items() if n > 1] == []


def test_default_within_range_or_flagged():
    outside = [p for p in PARAMS if not p.min <= p.default <= p.max and not p.reserved]
    assert outside  # the official app ships EQ band 10 frequency with default above max
    assert all("clamp" in (p.note or "") for p in outside)


def test_registry_names_map_to_same_address():
    for name, reg in REGISTRY.items():
        param = DS.lookup(name)
        assert param is not None, name
        expected = 0x7F000000 | reg.section << 16 | reg.param_type << 8 | reg.addr_hi
        assert param.address == expected, name


def test_value_tables_cover_the_parameter_range():
    for p in PARAMS:
        if p.values:
            table = DS.values[p.values]
            assert all(v in table for v in range(p.min, p.max + 1)), hex(p.address)


def test_alias_targets_exist_and_are_not_aliases():
    for p in PARAMS:
        if p.alias_of:
            target = DS.by_address(p.alias_of)
            assert target is not None and target.alias_of is None, hex(p.address)


def test_since_fw_is_above_the_family_floor():
    floors = DS.models["fw_floor"]
    for p in PARAMS:
        for fam, fw in p.since_fw.items():
            assert fw > floors[fam.value], hex(p.address)
            assert p.families is None or fam in p.families, hex(p.address)


def test_sync_entries_lie_in_known_blocks():
    blocks = {b["block"] for b in DS.blocks}
    for entry in DS.sync:
        addr = entry["address"]
        assert f"{addr[2:4]}/{addr[4:6]}" in blocks, addr


def test_command_and_meter_addresses_exist():
    for cmd in DS.commands:
        assert DS.by_address(int(cmd["address"], 16)) is not None, cmd["slot"]
    for meter in DS.meters:
        param = DS.by_address(int(meter["address"], 16))
        assert param is not None, meter["address"]
        if meter["side"] != "mono":
            assert param.kind is Kind.METER, meter["address"]


def test_meter_scale_is_ascending_up_to_full_scale():
    scale = DS.meter_scale
    thresholds = scale["thresholds"]
    assert thresholds == sorted(set(thresholds))
    assert thresholds[-1] == scale["full_scale"]


def test_dataset_carries_no_app_internals():
    text = protocol._DATA_FILE.read_text(encoding="utf-8")
    for marker in ("descriptor", "state_offset", "formatter", "CModelSpec", "0x14"):
        assert marker not in text, marker


def test_lookup_live_word_and_memory_copy():
    live = DS.lookup("mic_compressor_ratio")
    assert (live.address, live.min, live.max) == (0x7F030178, 0, 13)
    copy = DS.lookup("mic_compressor_ratio", "profile", 0)
    assert copy.address == 0x7F200178
    assert DS.by_address(0x7F030178) is live


def test_alias_is_reachable_by_address_but_not_by_name():
    alias = DS.by_address(0x7F030B00)
    assert alias.alias_of == 0x7F030A00
    assert DS.lookup(alias.name) is DS.by_address(0x7F030A00)


def test_firmware_helper():
    assert firmware(1, 5) == 105
    assert firmware(3, 0) == 300


def test_available_follows_family_and_firmware_gates():
    sub_mix = DS.lookup("sub_mix_mode")
    assert sub_mix.since_fw == {Family.BC: 200, Family.X: 200, Family.ONE: 101}
    assert sub_mix.available(Family.BC, 300)
    assert not sub_mix.available(Family.BC, firmware(1, 7))
    assert sub_mix.available(Family.ONE, firmware(1, 1))
    assert not sub_mix.available(Family.ONE, firmware(1, 0))
    assert sub_mix.available(Family.BC)  # firmware unknown: do not hide


def test_available_respects_families_and_reserved():
    hot_key_opt = DS.by_address(0x7F030916)
    assert hot_key_opt.families == {Family.BC, Family.ONE}
    assert not hot_key_opt.available(Family.X)
    reserved = next(p for p in PARAMS if p.reserved)
    assert not reserved.available(Family.BC)


@pytest.mark.parametrize("fam", list(Family))
def test_every_family_has_a_model_entry(fam):
    assert fam.value in DS.models
