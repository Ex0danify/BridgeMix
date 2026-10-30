"""Protocol dataset, see doc/protocol/README.md for the field guide."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

_DATA_FILE = Path(__file__).with_name("bridgecast.json")


class Family(StrEnum):
    BC = "bc"
    ONE = "one"
    X = "x"


class Kind(StrEnum):
    SWITCH = "switch"
    INT = "int"
    WORD = "word"
    NAME = "name"
    METER = "meter"


def firmware(major: int, minor: int) -> int:
    """Firmware as the dataset writes it: 1.05 is 105."""
    return major * 100 + minor


@dataclass(frozen=True)
class Param:
    address: int  # 0x7F_SS_TT_AA
    name: str | None
    block: str
    memory: str | None
    bank: int | None
    backup_key: str | None
    kind: Kind | None
    min: int
    max: int
    default: int
    families: frozenset[Family] | None  # None: not known
    values: str | None  # key into Dataset.values
    status: str
    evidence: str
    since_fw: Mapping[Family, int] = field(default_factory=dict, compare=False, hash=False)
    max_by_family: Mapping[Family, int] = field(default_factory=dict, compare=False, hash=False)
    alias_of: int | None = None
    note: str | None = None

    @property
    def reserved(self) -> bool:
        return self.status == "reserved"

    def available(self, family: Family, fw: int | None = None) -> bool:
        """Whether the device can have this word. Gates come from the changelogs (inferred)."""
        if self.reserved or (self.families is not None and family not in self.families):
            return False
        need = self.since_fw.get(family)
        return fw is None or need is None or fw >= need


@dataclass(frozen=True, eq=False)
class Dataset:
    header: dict[str, Any]
    models: dict[str, Any]
    blocks: tuple[dict[str, Any], ...]
    sync: tuple[dict[str, Any], ...]
    poll: tuple[dict[str, Any], ...]
    connect: tuple[dict[str, Any], ...]
    commands: tuple[dict[str, Any], ...]
    meters: tuple[dict[str, Any], ...]
    meter_scale: dict[str, Any]
    values: dict[str, dict[int, str]]
    params: tuple[Param, ...]
    _by_address: dict[int, Param]
    _by_name: dict[tuple[str, str | None, int | None], Param]

    def by_address(self, address: int) -> Param | None:
        return self._by_address.get(address)

    def lookup(self, name: str, memory: str | None = None, bank: int | None = None) -> Param | None:
        """Live word by default, or the copy in a profile or effect memory."""
        return self._by_name.get((name, memory, bank))


def _hex(text: str) -> int:
    return int(text, 16)


def _param(rec: dict[str, Any]) -> Param:
    fams = rec["families"]
    return Param(
        address=_hex(rec["address"]),
        name=rec["name"],
        block=rec["block"],
        memory=rec["memory"],
        bank=rec["bank"],
        backup_key=rec["backup_key"],
        kind=Kind(rec["kind"]) if rec["kind"] else None,
        min=rec["min"],
        max=rec["max"],
        default=rec["default"],
        families=frozenset(Family(f) for f in fams) if fams is not None else None,
        values=rec["values"],
        status=rec["status"],
        evidence=rec["evidence"],
        since_fw=MappingProxyType({Family(f): v for f, v in (rec["since_fw"] or {}).items()}),
        max_by_family=MappingProxyType(
            {Family(f): v for f, v in rec.get("max_by_family", {}).items()}
        ),
        alias_of=_hex(rec["alias_of"]) if rec.get("alias_of") else None,
        note=rec.get("note"),
    )


@cache
def load() -> Dataset:
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    params = tuple(_param(r) for r in raw["parameters"])
    by_name = {(p.name, p.memory, p.bank): p for p in params if p.name and p.alias_of is None}
    return Dataset(
        header=raw["header"],
        models=raw["models"],
        blocks=tuple(raw["blocks"]),
        sync=tuple(raw["sync"]),
        poll=tuple(raw["poll"]),
        connect=tuple(raw["connect"]),
        commands=tuple(raw["commands"]),
        meters=tuple(raw["meters"]),
        meter_scale=raw["meter_scale"],
        values={k: {int(v): t for v, t in tbl.items()} for k, tbl in raw["values"].items()},
        params=params,
        _by_address={p.address: p for p in params},
        _by_name=by_name,
    )
