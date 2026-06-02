"""Shared pytest fixtures for the BridgeMix test suite.

The package uses a ``src`` layout; ``pythonpath = ["src"]`` in pyproject.toml
makes ``bridgemix`` importable without an editable install.

A single session-scoped ``QApplication`` is provided for the tests that
construct ``QObject`` subclasses (BridgeCast, SpectrumAnalyzer).  Qt signal
emission for direct connections is synchronous, so no running event loop is
required — the fixture only needs to ensure a ``QApplication`` instance exists.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Return the process-wide QApplication, creating it once if needed."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
