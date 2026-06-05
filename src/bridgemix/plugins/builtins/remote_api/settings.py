"""Connection settings for the REST API server.

Persistence is handled by the SDK's per-plugin ``SettingsStore`` (``ctx.settings``);
this module is just the typed bundle the server is started with, plus a helper to
read it back out of the store (validating the port, since the store is
schema-less).
"""
from __future__ import annotations

from dataclasses import dataclass

# Loopback only — the API is never exposed to the network.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ApiSettings:
    enabled: bool = False
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


def _coerce_port(value: object) -> int:
    return value if isinstance(value, int) and 1 <= value <= 65535 else DEFAULT_PORT


def from_store(store) -> ApiSettings:
    """Build :class:`ApiSettings` from a plugin ``SettingsStore``.

    The host is fixed; only ``enabled`` and ``port`` are user-controlled and
    persisted. An out-of-range or non-int stored port falls back to the default.
    """
    return ApiSettings(
        enabled=bool(store.get("enabled", False)),
        host=DEFAULT_HOST,
        port=_coerce_port(store.get("port", DEFAULT_PORT)),
    )
