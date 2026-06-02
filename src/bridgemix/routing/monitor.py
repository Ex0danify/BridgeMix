"""
Live routing monitor.

Polls the audio server on a timer, emits the current set of application streams
for the UI, and auto-applies saved rules to streams as they appear — the
continuous equivalent of the official app routing new apps the moment they start
playing.

"If not already set" semantics: a saved rule moves a stream only when the stream
is not already on its target sink, and only **once** per stream — so a manual
override the user makes afterwards is never fought.  Per-stream bookkeeping is
keyed on the sink-input index and pruned as streams disappear.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from bridgemix.routing import backend, store


class RoutingMonitor(QObject):
    """Emits ``streams_changed(list[Stream])`` and enforces saved rules."""

    streams_changed = pyqtSignal(list)

    def __init__(self, interval_ms: int = 1500, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._applied: set[int] = set()   # sink-input indices we've auto-routed
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        if backend.available():
            self._tick()
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def note_manual(self, stream_index: int) -> None:
        """Mark a stream the user routed by hand so auto-apply leaves it alone."""
        self._applied.add(stream_index)

    # ── internals ─────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        streams = backend.list_streams()
        self._apply_rules(streams)
        self.streams_changed.emit(streams)

    def _apply_rules(self, streams: list) -> None:
        rules = store.load_rules()
        present = {s.index for s in streams}
        self._applied &= present  # forget streams that have gone away

        for s in streams:
            if s.index in self._applied:
                continue
            target = rules.get(s.app_key)
            if not target:
                continue
            if s.sink_name == target:
                self._applied.add(s.index)        # already where it belongs
            elif backend.move(s.index, target):
                self._applied.add(s.index)
