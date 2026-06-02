"""
MIDI transport — wraps mido for split TX/RX port operation.

TX port: "BRIDGE CAST MIDI 1"
RX port: "BRIDGE CAST MIDI 2"

The receive callback runs on a background mido thread.  Callers must
bounce any UI work back to the Qt main thread (done in bridge_cast.py
via a queued signal).
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

import mido

log = logging.getLogger(__name__)

# Max time to wait for an rtmidi port to close before abandoning it.  On Windows
# with the hooked BRIDGE CAST WinMM driver, close_port() can deadlock if called
# while RX buffers are still being flushed (midiInReset invokes the C callback,
# which needs the GIL the closing thread already holds).  We never block the GUI
# thread on it — see close().
_CLOSE_TIMEOUT_S = 1.0

SysExCallback = Callable[[tuple[int, ...]], None]


class MidiTransport:
    def __init__(self) -> None:
        self._out: Any | None = None
        self._in: Any | None = None
        self._callback: SysExCallback | None = None

    # ── Connection ────────────────────────────────────────────────────────────

    def open(self, tx_name: str, rx_name: str, callback: SysExCallback) -> None:
        """Open TX and RX ports.  Raises OSError on failure.

        If the input port fails to open after the output port has already
        opened, close the output again so we never leak a half-open transport.
        """
        self._callback = callback
        self._out = mido.open_output(tx_name)
        try:
            self._in = mido.open_input(rx_name, callback=self._mido_callback)
        except Exception:
            try:
                self._out.close()
            except Exception:
                pass
            self._out = None
            raise
        log.info("MIDI open: TX=%s  RX=%s", tx_name, rx_name)

    def close(self) -> None:
        """Close both ports without ever blocking the calling (GUI) thread.

        rtmidi's native close_port() can deadlock on Windows when called while RX
        buffers are still flushing (see _CLOSE_TIMEOUT_S).  We therefore run the
        actual close on a daemon thread and only wait _CLOSE_TIMEOUT_S for it.  If
        it wedges we abandon it: the daemon thread keeps the port objects alive
        (so no destructor runs on the main thread) and the OS reclaims the ports
        when the process exits.
        """
        # Clear our own callback ref first so _mido_callback becomes a no-op
        # immediately, regardless of what the port teardown does.
        self._callback = None
        in_port, out_port = self._in, self._out
        self._in = None
        self._out = None
        if in_port is None and out_port is None:
            return

        def _do_close() -> None:
            if in_port is not None:
                try:
                    in_port.callback = None
                except Exception:
                    pass
                try:
                    in_port.close()
                except Exception:
                    pass
            if out_port is not None:
                try:
                    out_port.close()
                except Exception:
                    pass

        t = threading.Thread(target=_do_close, name="midi-close", daemon=True)
        t.start()
        t.join(_CLOSE_TIMEOUT_S)
        if t.is_alive():
            log.warning(
                "MIDI close timed out after %.1fs (rtmidi close_port blocked); "
                "abandoning port — it will be freed on process exit.",
                _CLOSE_TIMEOUT_S,
            )
        else:
            log.info("MIDI closed")

    @property
    def is_open(self) -> bool:
        return self._out is not None and not self._out.closed

    # ── TX ────────────────────────────────────────────────────────────────────

    def send_sysex(self, data: tuple[int, ...]) -> None:
        """Send a SysEx frame (mido data tuple, F0/F7 stripped)."""
        if not self.is_open:
            return
        try:
            msg = mido.Message("sysex", data=data)
            self._out.send(msg)
        except Exception as exc:
            log.warning("TX error: %s", exc)

    # ── RX ────────────────────────────────────────────────────────────────────

    def _mido_callback(self, msg: Any) -> None:
        if msg.type == "sysex" and self._callback is not None:
            try:
                self._callback(tuple(msg.data))
            except Exception as exc:
                log.warning("RX callback error: %s", exc)
