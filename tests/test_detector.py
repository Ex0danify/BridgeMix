"""Tests for MIDI port detection (``bridgemix.midi.detector``)."""
from __future__ import annotations

from bridgemix.midi import detector


# ── _best_port ────────────────────────────────────────────────────────────────

def test_best_port_prefers_app_over_ctrl():
    names = ["BRIDGE CAST CTRL 2", "BRIDGE CAST APP 1", "Other Device"]
    assert detector._best_port(names) == "BRIDGE CAST APP 1"


def test_best_port_case_insensitive():
    assert detector._best_port(["bridge cast app 1"]) == "bridge cast app 1"


def test_best_port_falls_back_to_first_bridge_cast():
    names = ["Some Synth", "BRIDGE CAST CTRL 2", "BRIDGE CAST MIDI 3"]
    assert detector._best_port(names) == "BRIDGE CAST CTRL 2"


def test_best_port_returns_none_when_absent():
    assert detector._best_port(["Focusrite", "Komplete Audio"]) is None


def test_best_port_empty_list():
    assert detector._best_port([]) is None


# ── find_midi_ports / find_device ─────────────────────────────────────────────

def test_find_midi_ports_returns_app_ports(monkeypatch):
    monkeypatch.setattr(detector.mido, "get_output_names",
                        lambda: ["BRIDGE CAST APP 1", "BRIDGE CAST CTRL 2"])
    monkeypatch.setattr(detector.mido, "get_input_names",
                        lambda: ["BRIDGE CAST APP 0", "BRIDGE CAST CTRL 1"])
    tx, rx = detector.find_midi_ports()
    assert tx == "BRIDGE CAST APP 1"
    assert rx == "BRIDGE CAST APP 0"


def test_find_midi_ports_handles_missing_device(monkeypatch):
    monkeypatch.setattr(detector.mido, "get_output_names", lambda: ["Other"])
    monkeypatch.setattr(detector.mido, "get_input_names", lambda: ["Other"])
    assert detector.find_midi_ports() == (None, None)


def test_find_midi_ports_swallows_backend_errors(monkeypatch):
    def boom():
        raise RuntimeError("no MIDI backend")
    monkeypatch.setattr(detector.mido, "get_output_names", boom)
    assert detector.find_midi_ports() == (None, None)


def test_find_device_returns_none_unless_both_present(monkeypatch):
    monkeypatch.setattr(detector.mido, "get_output_names",
                        lambda: ["BRIDGE CAST APP 1"])
    monkeypatch.setattr(detector.mido, "get_input_names", lambda: ["Other"])
    assert detector.find_device() == (None, None)


def test_find_device_returns_pair_when_present(monkeypatch):
    monkeypatch.setattr(detector.mido, "get_output_names",
                        lambda: ["BRIDGE CAST APP 1"])
    monkeypatch.setattr(detector.mido, "get_input_names",
                        lambda: ["BRIDGE CAST APP 0"])
    assert detector.find_device() == ("BRIDGE CAST APP 1", "BRIDGE CAST APP 0")
