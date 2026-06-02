"""
SubMix spectrum analyzer.

The BRIDGE CAST does **not** stream FFT data over MIDI — enabling the Game EQ
analyzer only reroutes the Game channel into the SUB MIX and echoes an on/off
flag (state-vector byte 36).  The actual spectrum is computed host-side, the same
way the official app does it: capture the SUB MIX USB audio input and run an FFT.

`SpectrumAnalyzer` opens a `sounddevice` input stream on the SubMix capture
endpoint and emits a log-frequency magnitude spectrum (~30 fps) for the EQ
overlay.  All heavy work runs off a QTimer on the GUI thread; the audio callback
only copies the latest block.
"""
from __future__ import annotations

import logging
import sys
import threading

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

try:  # sounddevice is a hard dep, but guard so the GUI still loads if the
    import sounddevice as _sd  # backend/PortAudio is missing on a given host.
except Exception as _exc:  # pragma: no cover - environment dependent
    _sd = None
    _SD_IMPORT_ERROR = str(_exc)
else:
    _SD_IMPORT_ERROR = ""

log = logging.getLogger(__name__)

_FFT_SIZE = 4096          # samples per FFT (≈85 ms @ 48 kHz)
_DEFAULT_RATE = 48000
_FPS = 45                 # spectrum refresh rate (FFT recomputed from a rolling
                          # buffer, decoupled from the audio block size)


class SpectrumAnalyzer(QObject):
    """Captures the SubMix input and emits a log-frequency dB spectrum.

    Signals
    -------
    spectrum_ready(freqs_hz: np.ndarray, db: np.ndarray)
        Emitted ~`_FPS` times/sec while running.
    error(message: str)
        Emitted when capture cannot start or fails.
    """

    spectrum_ready = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, device_hint: str = "sub", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._device_hint = device_hint
        self._stream = None
        # When capturing the raw Linux multichannel device, the two channel
        # indices to extract for this hint (None = use the named stereo device).
        self._channel_pair: tuple[int, int] | None = None
        self._rate = _DEFAULT_RATE
        self._buf = np.zeros(_FFT_SIZE, dtype=np.float32)
        self._lock = threading.Lock()
        self._window = np.hanning(_FFT_SIZE).astype(np.float32)
        self._running = False

        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / _FPS))
        self._timer.timeout.connect(self._tick)

    # ── device discovery ───────────────────────────────────────────────────────

    @staticmethod
    def available() -> bool:
        return _sd is not None

    # Brand tokens identifying the device across OSes.
    _BRAND_TOKENS = ("bridge cast", "roland")

    # Windows and Linux (UCM2/PipeWire) use different names for the same
    # endpoints.  Map each logical hint to all known OS-specific names.
    _HINT_ALIASES: dict[str, tuple[str, ...]] = {
        "sub": ("sub", "sfx"),          # Windows: "SUB MIX", Linux UCM2: "SFX"
        "mic": ("mic",),
        "stream": ("stream",),          # Windows: "STREAM", Linux: "StreamMix"
    }

    # On Linux the device exposes one raw multichannel ALSA capture (hw:N,0)
    # carrying every mix interleaved.  The per-mix PipeWire/JACK "split" nodes
    # have unstable indices, duplicate names ("… Mic" vs "Split … Mic"), and
    # unreliable port auto-connection, so we capture the raw device and slice the
    # right channel pair ourselves.  Offsets follow the shipped ALSA UCM
    # (USB-Audio/Roland/BridgeCastV2-Hifi.conf): StreamMix=0/1, Mic=2/3, SFX=4/5.
    # Only "mic" is wired up + verified; the SUB MIX channel pair is unconfirmed.
    _LINUX_HW_CHANNELS: dict[str, tuple[int, int]] = {
        "mic": (2, 3),
    }

    @classmethod
    def _find_raw_multichannel(cls) -> int | None:
        """Linux only: the raw ALSA ``hw:N,0`` input exposing all mix channels.

        Matched by the ALSA host-API name (``… USB Audio (hw:0,0)``) and an input
        channel count high enough to hold the requested pair.  Returns its index
        (stable, enumerated ahead of the PipeWire virtual nodes) or None.
        """
        if _sd is None:
            return None
        try:
            devices = _sd.query_devices()
        except Exception:  # pragma: no cover
            return None
        for idx, d in enumerate(devices):
            low = str(d.get("name", "")).lower()
            if (
                "hw:" in low
                and "usb audio" in low
                and any(t in low for t in cls._BRAND_TOKENS)
                and d.get("max_input_channels", 0) >= 6
            ):
                return idx
        return None

    @classmethod
    def find_device(cls, hint: str = "sub") -> int | None:
        """Best-effort match of the capture endpoint by name (cross-platform).

        Prefers an input device whose name contains both *hint* (or an
        OS-dependent alias) and a brand token; falls back to any brand-matching
        input.  Pass an explicit index to ``start(device=...)`` to override.
        """
        if _sd is None:
            return None
        hints = tuple(
            h.lower() for h in cls._HINT_ALIASES.get(hint.lower(), (hint,))
        )
        try:
            devices = _sd.query_devices()
        except Exception as exc:  # pragma: no cover
            log.warning("query_devices failed: %s", exc)
            return None
        fallback: int | None = None
        inputs: list[str] = []
        for idx, d in enumerate(devices):
            if d.get("max_input_channels", 0) < 1:
                continue
            name = str(d.get("name", ""))
            inputs.append(f"[{idx}] {name}")
            low = name.lower()
            is_brand = any(t in low for t in cls._BRAND_TOKENS)
            if is_brand and any(h in low for h in hints):
                return idx
            if is_brand and fallback is None:
                fallback = idx
        if fallback is None:
            log.info("no BRIDGE CAST input matched hints %r; inputs: %s", hints, inputs)
        return fallback

    # ── lifecycle ───────────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    def start(self, device: int | None = None) -> bool:
        """Open the capture stream. Returns True on success, else emits error()."""
        if _sd is None:
            self.error.emit(f"sounddevice unavailable: {_SD_IMPORT_ERROR}")
            return False
        if self._running:
            return True
        # Linux: prefer the stable raw multichannel device + channel slicing over
        # the flaky PipeWire/JACK virtual nodes (see _LINUX_HW_CHANNELS).
        self._channel_pair = None
        dev = device
        if dev is None and sys.platform.startswith("linux"):
            pair = self._LINUX_HW_CHANNELS.get(self._device_hint)
            raw = self._find_raw_multichannel() if pair is not None else None
            if raw is not None:
                dev, self._channel_pair = raw, pair
        if dev is None:
            dev = self.find_device(self._device_hint)
        if dev is None:
            self.error.emit("SubMix input device not found")
            return False
        try:
            info = _sd.query_devices(dev)
            self._rate = int(info.get("default_samplerate") or _DEFAULT_RATE)
            if self._channel_pair is not None:
                # Open enough channels to cover the pair; slice in the callback.
                channels = max(self._channel_pair) + 1
            else:
                channels = min(2, int(info.get("max_input_channels", 1)) or 1)
            self._stream = _sd.InputStream(
                device=dev,
                channels=channels,
                samplerate=self._rate,
                blocksize=0,          # let PortAudio pick a low-latency block;
                latency="low",        # the callback rolls samples into _buf and
                dtype="float32",      # the FFT is recomputed on the GUI timer.
                callback=self._on_audio,
            )
            self._stream.start()
        except Exception as exc:
            log.warning("spectrum analyzer start failed: %s", exc)
            self._stream = None
            # Raw multichannel device busy/unavailable: fall back to the named
            # PipeWire/JACK node before giving up.
            if device is None and self._channel_pair is not None:
                self._channel_pair = None
                named = self.find_device(self._device_hint)
                if named is not None and named != dev:
                    log.info("raw capture failed; falling back to named node %d", named)
                    return self.start(device=named)
            self.error.emit(str(exc))
            return False
        self._buf[:] = 0.0
        self._running = True
        self._timer.start()
        return True

    def stop(self) -> None:
        self._timer.stop()
        self._running = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:  # pragma: no cover
                log.debug("stream close error: %s", exc)

    # ── audio thread ─────────────────────────────────────────────────────────────

    def _on_audio(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            log.debug("audio status: %s", status)
        pair = self._channel_pair
        if pair is not None and getattr(indata, "ndim", 1) > 1 and indata.shape[1] > pair[1]:
            x = indata[:, pair].mean(axis=1)        # extract this mix's L/R pair
        elif getattr(indata, "ndim", 1) > 1:
            x = indata.mean(axis=1)
        else:
            x = indata
        n = min(len(x), _FFT_SIZE)
        with self._lock:
            if n >= _FFT_SIZE:
                self._buf[:] = x[-_FFT_SIZE:]
            else:  # shift in a short block (only if host uses <_FFT_SIZE blocks)
                self._buf[:-n] = self._buf[n:]
                self._buf[-n:] = x[:n]

    # ── GUI thread (timer) ───────────────────────────────────────────────────────

    def _tick(self) -> None:
        with self._lock:
            block = self._buf.copy()
        spec = np.abs(np.fft.rfft(block * self._window))
        freqs = np.fft.rfftfreq(_FFT_SIZE, 1.0 / self._rate)
        # Normalize to a dBFS-like scale (window coherent gain ≈ N/2).
        db = 20.0 * np.log10(np.maximum(spec / (_FFT_SIZE / 2.0), 1e-7))
        self.spectrum_ready.emit(freqs, db)
