"""Tests for plugin discovery, gating, loading and error isolation.

A bare BridgeCast (no device) backs the DeviceFacade, qapp supplies the
QApplication, and XDG_* point at a temp dir so nothing touches the real config.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bridgemix.device.bridge_cast import BridgeCast
from bridgemix.plugins.device import DeviceFacade
from bridgemix.plugins.manager import PluginManager, PluginStatus

# A working user plugin: returns a trivial widget and records that it ran.
_GOOD_PLUGIN = textwrap.dedent('''
    from PyQt6.QtWidgets import QLabel
    from bridgemix.plugins import Plugin

    class GoodPlugin(Plugin):
        def create_widget(self, ctx):
            return QLabel("ok")
''')

# Entry attribute that is not a Plugin subclass.
_NOT_A_PLUGIN = textwrap.dedent('''
    class NotAPlugin:
        pass
''')

# Returns something that isn't a QWidget — the host must reject it.
_NON_WIDGET_PLUGIN = textwrap.dedent('''
    from bridgemix.plugins import Plugin

    class NonWidgetPlugin(Plugin):
        def create_widget(self, ctx):
            return "not a widget"
''')

# Raises while building its widget — must be caught and reported, not propagated.
_RAISING_PLUGIN = textwrap.dedent('''
    from bridgemix.plugins import Plugin

    class BoomPlugin(Plugin):
        def create_widget(self, ctx):
            raise RuntimeError("kaboom")
''')


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


@pytest.fixture
def manager(env, qapp):
    return PluginManager(DeviceFacade(BridgeCast()))


def _write_plugin(env: Path, folder: str, *, pid: str, module: str, body: str,
                  entry: str, host_api: str = ">=1.0,<2.0",
                  module_name: str = "entry", requires: list[str] | None = None) -> Path:
    pdir = env / "data" / "bridgemix" / "plugins" / folder
    pdir.mkdir(parents=True, exist_ok=True)
    requires_line = f"requires = {list(requires or [])!r}\n"
    (pdir / "plugin.toml").write_text(textwrap.dedent(f'''
        id = "{pid}"
        name = "{folder}"
        version = "1.0.0"
        entry_point = "{module_name}:{entry}"
        host_api = "{host_api}"
    ''') + requires_line)
    (pdir / f"{module_name}.py").write_text(body)
    return pdir


def _find(manager: PluginManager, pid: str):
    return next(r for r in manager.records if r.id == pid)


# ── Built-in ─────────────────────────────────────────────────────────────────────

def test_builtin_remote_api_discovered(manager):
    import importlib.util
    has_deps = bool(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("uvicorn")
    )
    manager.discover()
    rec = next(r for r in manager.records if r.id.endswith("remote-api"))
    assert rec.is_builtin
    # Loads when its declared deps are present; otherwise it's gated, not errored.
    if has_deps:
        assert rec.status is PluginStatus.LOADED
        assert rec.widget is not None
    else:
        assert rec.status is PluginStatus.MISSING_DEPS
        assert rec.missing_deps


# ── User-plugin gating ───────────────────────────────────────────────────────────

def test_user_plugin_needs_consent_before_loading(env, manager):
    _write_plugin(env, "good", pid="com.x.good", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin")
    manager.discover()
    rec = _find(manager, "com.x.good")
    assert rec.status is PluginStatus.NEEDS_CONSENT
    assert rec.widget is None  # not executed without consent


def test_consent_loads_and_persists(env, qapp):
    _write_plugin(env, "good", pid="com.x.good", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin")
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    mgr.grant_consent(_find(mgr, "com.x.good"))
    assert _find(mgr, "com.x.good").status is PluginStatus.LOADED

    # A fresh manager sees the persisted consent + enabled and loads immediately.
    mgr2 = PluginManager(DeviceFacade(BridgeCast()))
    mgr2.discover()
    assert _find(mgr2, "com.x.good").status is PluginStatus.LOADED


def test_disable_after_load(env, qapp):
    _write_plugin(env, "good", pid="com.x.good", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin")
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    rec = _find(mgr, "com.x.good")
    mgr.grant_consent(rec)
    mgr.disable(rec)
    assert rec.status is PluginStatus.DISABLED
    assert rec.widget is None


def test_missing_dependency_blocks_load(env, qapp):
    # A declared requirement that isn't installed gates the plugin: it is not
    # imported, and the missing list is surfaced for the install card.
    _write_plugin(env, "needsdep", pid="com.x.needsdep", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin",
                  requires=["no-such-dist-xyz>=9"])
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    rec = _find(mgr, "com.x.needsdep")
    mgr.grant_consent(rec)  # consent → attempt load, which hits the dep gate
    assert rec.status is PluginStatus.MISSING_DEPS
    assert rec.missing_deps == ["no-such-dist-xyz>=9"]
    assert rec.widget is None


# ── Cross-plugin dependency conflicts ─────────────────────────────────────────────

def _two_conflicting(env):
    _write_plugin(env, "a", pid="com.x.a", module="entry", body=_GOOD_PLUGIN,
                  entry="GoodPlugin", requires=["shared-xyz<2"])
    _write_plugin(env, "b", pid="com.x.b", module="entry", body=_GOOD_PLUGIN,
                  entry="GoodPlugin", requires=["shared-xyz>=2"])
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    mgr.grant_consent(_find(mgr, "com.x.a"))
    mgr.grant_consent(_find(mgr, "com.x.b"))
    return mgr


def test_conflicting_plugins_flag_both(env, qapp):
    mgr = _two_conflicting(env)
    a, b = _find(mgr, "com.x.a"), _find(mgr, "com.x.b")
    assert a.status is PluginStatus.CONFLICT
    assert b.status is PluginStatus.CONFLICT
    assert "shared-xyz" in a.conflict
    assert a.widget is None and b.widget is None


def test_disabling_one_clears_the_others_conflict(env, qapp):
    mgr = _two_conflicting(env)
    b = _find(mgr, "com.x.b")
    mgr.disable(b)
    a = _find(mgr, "com.x.a")
    assert b.status is PluginStatus.DISABLED
    # With B gone, A no longer conflicts — it's just missing its (absent) dep.
    assert a.status is PluginStatus.MISSING_DEPS
    assert a.conflict == ""


def test_install_set_unions_active_plugin_requires(env, qapp):
    _write_plugin(env, "a", pid="com.x.a", module="entry", body=_GOOD_PLUGIN,
                  entry="GoodPlugin", requires=["alpha>=1"])
    _write_plugin(env, "b", pid="com.x.b", module="entry", body=_GOOD_PLUGIN,
                  entry="GoodPlugin", requires=["beta>=2"])
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    a, b = _find(mgr, "com.x.a"), _find(mgr, "com.x.b")
    mgr.grant_consent(a)
    mgr.grant_consent(b)
    # Installing for A resolves jointly with every other active plugin's requires
    # (B's here, plus the built-in REST API's), so pip reconciles them together.
    install_set = set(mgr.dependency_install_set(a))
    assert {"alpha>=1", "beta>=2"} <= install_set


# ── Compatibility & validation ───────────────────────────────────────────────────

def test_incompatible_host_api(env, manager):
    _write_plugin(env, "old", pid="com.x.old", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin", host_api=">=2.0")
    manager.discover()
    rec = _find(manager, "com.x.old")
    assert rec.status is PluginStatus.INCOMPATIBLE


def test_malformed_manifest_is_error(env, manager):
    pdir = env / "data" / "bridgemix" / "plugins" / "broken"
    pdir.mkdir(parents=True)
    (pdir / "plugin.toml").write_text("this is not = valid = toml ===")
    manager.discover()
    rec = next(r for r in manager.records if r.id == "broken")
    assert rec.status is PluginStatus.ERROR
    assert rec.error


# ── Error isolation ──────────────────────────────────────────────────────────────

def test_entry_not_a_plugin_is_isolated(env, qapp):
    _write_plugin(env, "bad", pid="com.x.bad", module="entry",
                  body=_NOT_A_PLUGIN, entry="NotAPlugin")
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    mgr.grant_consent(_find(mgr, "com.x.bad"))  # consent → attempt load
    rec = _find(mgr, "com.x.bad")
    assert rec.status is PluginStatus.ERROR
    assert "Plugin" in rec.error


def test_raising_create_widget_is_isolated(env, qapp):
    _write_plugin(env, "boom", pid="com.x.boom", module="entry",
                  body=_RAISING_PLUGIN, entry="BoomPlugin")
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    mgr.grant_consent(_find(mgr, "com.x.boom"))
    rec = _find(mgr, "com.x.boom")
    assert rec.status is PluginStatus.ERROR
    assert "kaboom" in rec.error


def test_non_widget_return_is_rejected(env, qapp):
    _write_plugin(env, "badw", pid="com.x.badw", module="entry",
                  body=_NON_WIDGET_PLUGIN, entry="NonWidgetPlugin")
    mgr = PluginManager(DeviceFacade(BridgeCast()))
    mgr.discover()
    mgr.grant_consent(_find(mgr, "com.x.badw"))
    rec = _find(mgr, "com.x.badw")
    assert rec.status is PluginStatus.ERROR
    assert "QWidget" in rec.error
    assert rec.widget is None


def test_duplicate_id_keeps_first(env, manager):
    _write_plugin(env, "a_dup", pid="com.x.dup", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin")
    _write_plugin(env, "b_dup", pid="com.x.dup", module="entry",
                  body=_GOOD_PLUGIN, entry="GoodPlugin")
    manager.discover()
    matches = [r for r in manager.records if r.id == "com.x.dup"]
    assert len(matches) == 1
