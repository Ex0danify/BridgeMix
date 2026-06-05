"""Shared pytest fixtures, at the repo root so both the global suite and each
plugin's own ``tests/``  can use them.

A single session-scoped ``QApplication`` is provided for tests that construct
``QObject`` subclasses or widgets. Qt signal emission for direct connections is
synchronous, so no running event loop is required — the fixture only needs to
ensure a ``QApplication`` instance exists.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Return the process-wide QApplication, creating it once if needed."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
