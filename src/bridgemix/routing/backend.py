"""
PulseAudio / PipeWire routing backend.

Routing is performed through the **PulseAudio control API** via the ``pactl``
CLI with JSON output.  PipeWire implements this same API, so a single code path
covers both audio servers and every desktop environment — the routing lives in
the audio server, not the DE.

The JSON parsers (`parse_targets`, `parse_streams`) are pure functions over
already-decoded ``pactl`` output, so they are unit-tested without a sound server.
The thin `_run_json` / `move` wrappers are the only parts that shell out.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

log = logging.getLogger(__name__)

# A sink belongs to the Bridge Cast if its description or node name says so.
# Matches the original Bridge Cast, V2 and X (all report "BRIDGE CAST …").
_DEVICE_DESC_MATCH = "bridge cast"
_DEVICE_NAME_MATCH = "bridge_cast"

_LINE_RE = re.compile(r"Line(\d+)", re.IGNORECASE)
_LR_SUFFIX_RE = re.compile(r"\s*(l/r|stereo)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Target:
    """A Bridge Cast output channel a stream can be routed to."""

    sink_name: str   # PulseAudio sink name (stable identifier for `move`)
    label: str       # short channel name, e.g. "Chat", "Game"
    sort_key: int    # ordering hint (the device's LineN index)


@dataclass(frozen=True)
class Stream:
    """An application stream currently producing audio (a sink-input)."""

    index: int            # PulseAudio sink-input index (changes per stream)
    app_key: str          # stable key for rules: process binary / app name
    label: str            # display name, e.g. "Discord"
    media: str            # current media title (tooltip), may be ""
    sink_name: str | None  # name of the sink it is currently on
    icon: str             # freedesktop icon name hint (application.icon_name), may be ""


# ── pure parsers ──────────────────────────────────────────────────────────────

def _is_bridge_sink(name: str, props: dict) -> bool:
    desc = str(props.get("device.description", "")).lower()
    return _DEVICE_DESC_MATCH in desc or _DEVICE_NAME_MATCH in name.lower()


def _target_label(name: str, props: dict) -> str:
    """Human channel name from the sink's profile description (e.g. 'Chat')."""
    prof = props.get("device.profile.description") or ""
    label = _LR_SUFFIX_RE.sub("", prof).strip()
    if label:
        return label
    m = _LINE_RE.search(name)
    return f"Line {m.group(1)}" if m else name


def parse_targets(sinks: list[dict]) -> list[Target]:
    """Bridge Cast output channels, ordered by their LineN index."""
    targets: list[Target] = []
    for s in sinks:
        name = s.get("name", "")
        props = s.get("properties", {}) or {}
        if not _is_bridge_sink(name, props):
            continue
        m = _LINE_RE.search(name)
        sort_key = int(m.group(1)) if m else s.get("index", 0)
        targets.append(Target(name, _target_label(name, props), sort_key))
    targets.sort(key=lambda t: t.sort_key)
    return targets


def parse_streams(sink_inputs: list[dict], sink_name_by_index: dict[int, str]) -> list[Stream]:
    """Active application streams, with their current sink resolved to a name."""
    streams: list[Stream] = []
    for si in sink_inputs:
        props = si.get("properties", {}) or {}
        app_key = (
            props.get("application.process.binary")
            or props.get("application.name")
            or "unknown"
        )
        label = props.get("application.name") or app_key
        media = props.get("media.name") or ""
        icon = props.get("application.icon_name") or ""
        sink_idx = si.get("sink")
        sink_name = sink_name_by_index.get(sink_idx) if isinstance(sink_idx, int) else None
        streams.append(Stream(si.get("index", -1), app_key, label, media, sink_name, icon))
    return streams


# ── pactl wrappers ────────────────────────────────────────────────────────────

def available() -> bool:
    """True if the `pactl` CLI is present (PulseAudio or PipeWire)."""
    return shutil.which("pactl") is not None


def is_supported() -> bool:
    """True only where per-application routing applies.

    Routing is a Linux concept here (PipeWire / PulseAudio via `pactl`).  On
    Windows and macOS the official Roland app drives the OS's own audio APIs, so
    the feature is hidden entirely rather than shown disabled.
    """
    return sys.platform.startswith("linux") and available()


def _run_json(args: list[str]) -> list[dict]:
    """Run `pactl --format=json <args>` and return the decoded list, or []."""
    try:
        out = subprocess.run(
            ["pactl", "--format=json", *args],
            capture_output=True, text=True, timeout=4, check=True,
        ).stdout
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        log.debug("pactl %s failed: %s", args, exc)
        return []


def list_targets() -> list[Target]:
    return parse_targets(_run_json(["list", "sinks"]))


def list_streams() -> list[Stream]:
    sinks = _run_json(["list", "sinks"])
    name_by_index = {s["index"]: s["name"] for s in sinks if "index" in s and "name" in s}
    return parse_streams(_run_json(["list", "sink-inputs"]), name_by_index)


def move(stream_index: int, sink_name: str) -> bool:
    """Route a sink-input to a sink. Returns True on success."""
    try:
        subprocess.run(
            ["pactl", "move-sink-input", str(stream_index), sink_name],
            capture_output=True, text=True, timeout=4, check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Failed to move stream %s → %s: %s", stream_index, sink_name, exc)
        return False
