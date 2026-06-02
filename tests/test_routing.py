"""Tests for application-routing: backend parsers + the rules store.

Fixtures mirror real `pactl --format=json` output from a Bridge Cast V2, so the
suite stays hardware-free (no audio server required).
"""
from __future__ import annotations

import json

import pytest

from bridgemix.routing import backend, store

# ── canned `pactl --format=json list sinks` (trimmed to relevant fields) ──────
_SINKS = [
    {"index": 3679,
     "name": "alsa_output.usb-Roland_BRIDGE_CAST_V2_5C00-01.HiFi__Line1__sink",
     "properties": {"device.description": "BRIDGE CAST V2",
                    "device.profile.description": "Chat L/R"}},
    {"index": 3681,
     "name": "alsa_output.usb-Roland_BRIDGE_CAST_V2_5C00-01.HiFi__Line2__sink",
     "properties": {"device.description": "BRIDGE CAST V2",
                    "device.profile.description": "Game L/R"}},
    {"index": 3683,
     "name": "alsa_output.usb-Roland_BRIDGE_CAST_V2_5C00-01.HiFi__Line3__sink",
     "properties": {"device.description": "BRIDGE CAST V2",
                    "device.profile.description": "Music L/R"}},
    {"index": 3685,
     "name": "alsa_output.usb-Roland_BRIDGE_CAST_V2_5C00-01.HiFi__Line4__sink",
     "properties": {"device.description": "BRIDGE CAST V2",
                    "device.profile.description": "System L/R"}},
    {"index": 3802,
     "name": "alsa_output.pci-0000_43_00.1.hdmi-stereo",
     "properties": {"device.description": "GA102 HD Audio",
                    "device.profile.description": "Digital Stereo (HDMI)"}},
]

_SINK_INPUTS = [
    {"index": 1955, "sink": 3685,
     "properties": {"application.name": "Zen", "application.process.binary": "zen",
                    "media.name": "How To Crosspost on Reddit - YouTube"}},
    {"index": 3355, "sink": 3681,
     "properties": {"application.name": "Discord", "media.name": "Voice"}},
]


# ── parse_targets ─────────────────────────────────────────────────────────────

def test_parse_targets_filters_to_bridge_cast_only():
    targets = backend.parse_targets(_SINKS)
    assert [t.label for t in targets] == ["Chat", "Game", "Music", "System"]
    # The HDMI sink is excluded.
    assert all("hdmi" not in t.sink_name for t in targets)


def test_parse_targets_ordered_by_line_index():
    targets = backend.parse_targets(_SINKS)
    assert [t.sort_key for t in targets] == [1, 2, 3, 4]


def test_parse_targets_strips_lr_suffix():
    [chat] = [t for t in backend.parse_targets(_SINKS) if t.sort_key == 1]
    assert chat.label == "Chat"
    assert chat.sink_name.endswith("HiFi__Line1__sink")


def test_parse_targets_empty_when_no_device():
    assert backend.parse_targets([_SINKS[-1]]) == []


# ── parse_streams ─────────────────────────────────────────────────────────────

def test_parse_streams_resolves_sink_name_and_key():
    name_by_index = {s["index"]: s["name"] for s in _SINKS}
    streams = backend.parse_streams(_SINK_INPUTS, name_by_index)

    zen = streams[0]
    assert zen.app_key == "zen"              # prefers process.binary
    assert zen.label == "Zen"
    assert zen.sink_name.endswith("HiFi__Line4__sink")   # index 3685 → System


def test_parse_streams_falls_back_to_app_name_when_no_binary():
    name_by_index = {s["index"]: s["name"] for s in _SINKS}
    discord = backend.parse_streams(_SINK_INPUTS, name_by_index)[1]
    assert discord.app_key == "Discord"      # no process.binary → app name


def test_parse_streams_unknown_sink_index_is_none():
    streams = backend.parse_streams(_SINK_INPUTS, {})   # no name mapping
    assert all(s.sink_name is None for s in streams)


def test_desktop_entry_parser_main_group_only():
    from bridgemix.gui.panels.routing_panel import _parse_desktop_entry
    text = (
        "[Desktop Entry]\n"
        "Name=Zen Browser\n"
        "Icon=app.zen_browser.zen\n"
        "StartupWMClass=zen\n"
        "[Desktop Action new-window]\n"
        "Name=Open a New Window\n"
        "Icon=should-be-ignored\n"
    )
    assert _parse_desktop_entry(text) == ("app.zen_browser.zen", "zen")


def test_icon_index_maps_binary_and_stem(tmp_path):
    from bridgemix.gui.panels.routing_panel import _build_icon_index
    (tmp_path / "app.zen_browser.zen.desktop").write_text(
        "[Desktop Entry]\nIcon=app.zen_browser.zen\nStartupWMClass=zen\n"
    )
    (tmp_path / "noicon.desktop").write_text("[Desktop Entry]\nName=Nope\n")
    index = _build_icon_index([tmp_path])
    assert index["zen"] == "app.zen_browser.zen"                  # by StartupWMClass
    assert index["app.zen_browser.zen"] == "app.zen_browser.zen"  # by filename stem
    assert "noicon" not in index                                   # entries w/o Icon skipped


@pytest.mark.parametrize(
    "platform, has_pactl, expected",
    [
        ("linux", True, True),    # Linux with pactl → routing available
        ("linux", False, False),  # Linux without pactl → nothing to drive
        ("win32", True, False),   # Windows uses its own audio APIs → hidden
        ("win32", False, False),
        ("darwin", True, False),  # macOS likewise
    ],
)
def test_is_supported(monkeypatch, platform, has_pactl, expected):
    monkeypatch.setattr(backend.sys, "platform", platform)
    monkeypatch.setattr(backend, "available", lambda: has_pactl)
    assert backend.is_supported() is expected


def test_row_offers_default_only_when_unrouted(qapp):
    """The italic 'Default' entry appears only if the app isn't on our channel."""
    from bridgemix.gui.panels.routing_panel import _StreamRow
    from bridgemix.routing.backend import Stream, Target

    targets = [Target("sink_chat", "Chat", 1), Target("sink_game", "Game", 2)]
    monitor = type("M", (), {"note_manual": lambda self, i: None})()
    noop = lambda: None  # noqa: E731

    def datas(combo):
        return [combo.itemData(i) for i in range(combo.count())]

    # Unrouted (on some other sink) → Default offered and selected.
    unrouted = _StreamRow(Stream(1, "zen", "Zen", "", "other_sink", ""), targets, monitor, noop)
    assert unrouted._combo.itemText(0) == "Default"
    assert None in datas(unrouted._combo)
    assert unrouted._combo.currentData() is None

    # Already on a Bridge Cast channel → no Default, channel preselected.
    routed = _StreamRow(Stream(2, "spotify", "Spotify", "", "sink_chat", ""), targets, monitor, noop)
    assert None not in datas(routed._combo)
    assert routed._combo.currentData() == "sink_chat"

    # If it later moves off our channels, Default returns.
    routed.update_stream(Stream(2, "spotify", "Spotify", "", "other_sink", ""))
    assert None in datas(routed._combo)


def test_grouping_orders_default_first_then_channels(qapp):
    """Apps bucket by channel: Default on top, then channel order, names sorted."""
    from bridgemix.gui.panels.routing_panel import RoutingPanel
    from bridgemix.routing.backend import Stream, Target
    from bridgemix.routing.monitor import RoutingMonitor

    monitor = RoutingMonitor()
    panel = RoutingPanel(monitor)
    panel._targets = [Target("sink_chat", "Chat", 1), Target("sink_game", "Game", 2)]

    streams = [
        Stream(1, "zen", "Zen", "", "other_sink", ""),        # unrouted → Default
        Stream(2, "spotify", "Spotify", "", "sink_game", ""),  # Game
        Stream(3, "discord", "Discord", "", "sink_chat", ""),  # Chat
        Stream(4, "aaa", "AAA", "", "sink_chat", ""),          # Chat, sorts first
    ]
    grouped = panel._grouped(streams)

    assert [key for key, _ in grouped] == [None, "sink_chat", "sink_game"]
    chat_group = dict(grouped)["sink_chat"]
    assert [s.label for s in chat_group] == ["AAA", "Discord"]  # alphabetical within group
    monitor.stop()


def test_panel_contains_distinguishes_inside_from_outside(qapp):
    """Click-away dismissal: panel descendants are 'inside', everything else out."""
    from PyQt6.QtWidgets import QLabel
    from bridgemix.gui.panels.routing_panel import RoutingPanel
    from bridgemix.routing.monitor import RoutingMonitor

    monitor = RoutingMonitor()
    panel = RoutingPanel(monitor)

    inside_child = panel._body            # a descendant widget of the panel
    outside = QLabel()                    # unrelated top-level widget

    assert panel._contains(panel) is True
    assert panel._contains(inside_child) is True
    assert panel._contains(outside) is False
    assert panel._contains(None) is False  # click landed outside the app entirely

    monitor.stop()


def test_parse_streams_icon_name_captured_else_empty():
    si = [
        {"index": 1, "sink": 3683,
         "properties": {"application.process.binary": "spotify",
                        "application.icon_name": "com.spotify.Client"}},
        {"index": 2, "sink": 3683,
         "properties": {"application.process.binary": "zen"}},   # no icon hint
    ]
    spotify, zen = backend.parse_streams(si, {})
    assert spotify.icon == "com.spotify.Client"
    assert zen.icon == ""


# ── store round-trip ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_routing(tmp_path, monkeypatch):
    path = tmp_path / "routing.json"
    monkeypatch.setattr(store, "_ROUTING_PATH", path)
    return path


def test_load_rules_missing_file_is_empty(tmp_routing):
    assert store.load_rules() == {}


def test_set_and_load_rule(tmp_routing):
    store.set_rule("zen", "sink_music")
    assert store.load_rules() == {"zen": "sink_music"}
    # Written under a "rules" object.
    assert json.loads(tmp_routing.read_text()) == {"rules": {"zen": "sink_music"}}


def test_set_rule_overwrites(tmp_routing):
    store.set_rule("zen", "sink_music")
    store.set_rule("zen", "sink_game")
    assert store.load_rules() == {"zen": "sink_game"}


def test_remove_rule(tmp_routing):
    store.set_rule("zen", "sink_music")
    store.set_rule("discord", "sink_chat")
    store.remove_rule("zen")
    assert store.load_rules() == {"discord": "sink_chat"}


def test_remove_missing_rule_is_noop(tmp_routing):
    store.set_rule("zen", "sink_music")
    store.remove_rule("nope")
    assert store.load_rules() == {"zen": "sink_music"}


def test_load_rules_ignores_malformed(tmp_routing):
    tmp_routing.write_text("not json at all {{{")
    assert store.load_rules() == {}


def test_load_rules_drops_non_string_entries(tmp_routing):
    tmp_routing.write_text(json.dumps({"rules": {"zen": 5, "ok": "sink_x"}}))
    assert store.load_rules() == {"ok": "sink_x"}
