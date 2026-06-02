"""
Optional REST API for BridgeMix.

A thin HTTP layer over the :class:`~bridgemix.device.bridge_cast.BridgeCast`
facade so third-party tools (Stream Deck, OBS, scripts) can read and set device
parameters. Everything here is lazily imported and gated behind the Extras ▸
Remote API setting — the app runs fine without ``fastapi``/``uvicorn`` installed.
"""

# The optional runtime dependencies for the REST API, used by the in-app
# installer. This mirrors the ``api`` extra in pyproject.toml; the two are kept
# in lock-step by ``tests/test_api_requirements_sync.py`` (CI fails on drift).
API_REQUIREMENTS = ["fastapi>=0.110", "uvicorn>=0.27"]
