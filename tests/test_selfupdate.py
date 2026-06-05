"""Tests for the in-place updater (``bridgemix.selfupdate``).

git and pip are mocked and ``_run`` is invoked directly on the test thread (its
``finished`` signal fires synchronously over a direct connection), so no real
checkout switch, network, or event loop is needed.
"""
from __future__ import annotations

from types import SimpleNamespace

from bridgemix import selfupdate as su
from bridgemix.selfupdate import SelfUpdater


def _ok(stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str) -> SimpleNamespace:
    return SimpleNamespace(returncode=1, stdout="", stderr=stderr)


# ── Eligibility gating ────────────────────────────────────────────────────────

def test_repo_root_found_in_this_checkout():
    root = su.repo_root()
    assert root is not None and (root / ".git").exists()


def test_can_self_update_false_without_git(monkeypatch):
    monkeypatch.setattr(su.shutil, "which", lambda _: None)
    assert su.can_self_update() is False


def test_can_self_update_false_outside_checkout(monkeypatch):
    monkeypatch.setattr(su, "repo_root", lambda: None)
    monkeypatch.setattr(su.shutil, "which", lambda _: "/usr/bin/git")
    assert su.can_self_update() is False


def test_is_clean_reflects_porcelain(monkeypatch, tmp_path):
    monkeypatch.setattr(su, "_git", lambda root, *a, **k: _ok(""))
    assert su.is_clean(tmp_path) is True
    monkeypatch.setattr(su, "_git", lambda root, *a, **k: _ok(" M file.py\n"))
    assert su.is_clean(tmp_path) is False


# ── Update flow ───────────────────────────────────────────────────────────────

def _run_update(monkeypatch, tmp_path, *, clean=True, git=None, pip=None):
    """Drive SelfUpdater._run with mocked git/pip; return (success, message)."""
    monkeypatch.setattr(su, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(su, "is_clean", lambda root: clean)
    monkeypatch.setattr(su, "_git", git or (lambda root, *a, **k: _ok()))
    monkeypatch.setattr(su.subprocess, "run", pip or (lambda *a, **k: _ok()))

    updater = SelfUpdater("v9.9.9")
    out: list[tuple[bool, str]] = []
    updater.finished.connect(lambda ok, msg: out.append((ok, msg)))
    updater._run()
    assert len(out) == 1
    return out[0]


def test_update_happy_path(monkeypatch, tmp_path, qapp):
    calls: list[tuple] = []

    def fake_git(root, *args, **kw):
        calls.append(args)
        return _ok()

    ok, msg = _run_update(monkeypatch, tmp_path, git=fake_git)
    assert ok is True
    assert "v9.9.9" in msg and "Restart" in msg
    # Tag is checked out unambiguously and detached at the release.
    assert ("checkout", "--quiet", "tags/v9.9.9") in calls
    assert ("fetch", "--tags", "--force", "origin") in calls


def test_update_refuses_dirty_tree(monkeypatch, tmp_path, qapp):
    ok, msg = _run_update(monkeypatch, tmp_path, clean=False)
    assert ok is False and "local changes" in msg


def test_update_reports_fetch_failure(monkeypatch, tmp_path, qapp):
    def fake_git(root, *args, **kw):
        if args[0] == "fetch":
            return _fail("fatal: unable to access origin")
        return _ok()

    ok, msg = _run_update(monkeypatch, tmp_path, git=fake_git)
    assert ok is False and "unable to access origin" in msg


def test_update_reports_checkout_failure(monkeypatch, tmp_path, qapp):
    def fake_git(root, *args, **kw):
        if args[0] == "checkout":
            return _fail("error: pathspec 'tags/v9.9.9' did not match")
        return _ok()

    ok, msg = _run_update(monkeypatch, tmp_path, git=fake_git)
    assert ok is False and "did not match" in msg


def test_update_reports_pip_failure(monkeypatch, tmp_path, qapp):
    ok, msg = _run_update(
        monkeypatch, tmp_path, pip=lambda *a, **k: _fail("could not resolve deps")
    )
    assert ok is False and "dependency sync failed" in msg
    assert "could not resolve deps" in msg


def test_update_handles_missing_checkout(monkeypatch, tmp_path, qapp):
    monkeypatch.setattr(su, "repo_root", lambda: None)
    updater = SelfUpdater("v9.9.9")
    out: list[tuple[bool, str]] = []
    updater.finished.connect(lambda ok, msg: out.append((ok, msg)))
    updater._run()
    assert out == [(False, "Not running from a git checkout.")]
