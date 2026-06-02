"""
Bridge Cast MIDI port detection — cross-platform (Windows + Linux).

Roland's Windows driver exposes:
  Output: "BRIDGE CAST APP 1", "BRIDGE CAST CTRL 2"
  Input:  "BRIDGE CAST APP 0", "BRIDGE CAST CTRL 1"
"""
from __future__ import annotations

import mido

_KEYWORD = "BRIDGE CAST"      # case-insensitive match against all port names


def _best_port(names: list[str]) -> str | None:
    """
    Return the most appropriate Bridge Cast port from a port name list.
    Prefers any port with "APP" in the name over "CTRL" or others,
    since the APP port carries SysEx/application traffic.
    """
    bc = [n for n in names if _KEYWORD in n.upper()]
    if not bc:
        return None
    for n in bc:
        if "APP" in n.upper():
            return n
    return bc[0]  # fallback: first BRIDGE CAST port found


def find_midi_ports() -> tuple[str | None, str | None]:
    """Return (tx_output_port, rx_input_port) or (None, None)."""
    try:
        tx = _best_port(mido.get_output_names())
        rx = _best_port(mido.get_input_names())
        return tx, rx
    except Exception:
        return None, None


def find_device() -> tuple[str | None, str | None]:
    """High-level helper: return (tx, rx) if device is detectable, else (None, None)."""
    tx, rx = find_midi_ports()
    if tx and rx:
        return tx, rx
    return None, None
