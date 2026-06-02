"""
Persistent settings for the optional REST API server.

File: ``~/.config/bridgemix/api.json`` ::

    {
      "enabled": false,
      "host": "127.0.0.1",
      "port": 8765
    }

Mirrors the never-raises contract of :mod:`bridgemix.routing.store`: a missing or
malformed file yields safe defaults so the app always starts.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_API_PATH = Path.home() / ".config" / "bridgemix" / "api.json"

# Default to loopback only — the API is never exposed to the network unless the
# user deliberately changes the host.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ApiSettings:
    enabled: bool = False
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


def settings_path() -> Path:
    return _API_PATH


def load_settings() -> ApiSettings:
    """Return saved settings; defaults on any read/parse error."""
    try:
        raw = json.loads(_API_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ApiSettings()
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        log.warning("Could not read API settings %s: %s", _API_PATH, exc)
        return ApiSettings()

    if not isinstance(raw, dict):
        return ApiSettings()

    enabled = raw.get("enabled", False)
    host = raw.get("host", DEFAULT_HOST)
    port = raw.get("port", DEFAULT_PORT)

    return ApiSettings(
        enabled=bool(enabled),
        host=host if isinstance(host, str) and host else DEFAULT_HOST,
        port=port if isinstance(port, int) and 1 <= port <= 65535 else DEFAULT_PORT,
    )


def save_settings(settings: ApiSettings) -> None:
    """Write settings, creating the config dir if needed."""
    _API_PATH.parent.mkdir(parents=True, exist_ok=True)
    _API_PATH.write_text(
        json.dumps(
            {
                "enabled": settings.enabled,
                "host": settings.host,
                "port": settings.port,
            },
            indent=2,
        )
    )
    log.info("API settings saved to %s (enabled=%s, %s:%d)",
             _API_PATH, settings.enabled, settings.host, settings.port)
