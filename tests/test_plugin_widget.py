"""Tests for the optional PluginWidget convenience base."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from PyQt6.QtWidgets import QLabel

from bridgemix.plugins import PluginWidget


def _ctx():
    return SimpleNamespace(
        device="dev", settings="store", log=logging.getLogger("test.plugin"),
        host_version="1.0.0", plugin_dir=None,
    )


def test_exposes_context_shortcuts(qapp):
    ctx = _ctx()
    w = PluginWidget(ctx)
    assert w.ctx is ctx
    assert w.device == "dev"
    assert w.settings == "store"
    assert w.log is ctx.log


def test_body_layout_accepts_widgets(qapp):
    w = PluginWidget(_ctx())
    w.body.addWidget(QLabel("hi"))
    assert w.body.count() == 1


def test_is_a_qwidget(qapp):
    from PyQt6.QtWidgets import QWidget
    assert isinstance(PluginWidget(_ctx()), QWidget)
