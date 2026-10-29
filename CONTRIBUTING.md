# Contributing to BridgeMix

Thanks for your interest in improving BridgeMix! Bug reports, fixes, and
protocol findings are all welcome.

> **Heads up:** BridgeMix talks to real audio hardware over an
> independently-reverse-engineered MIDI SysEx protocol. There's no official
> spec, so some addresses are inferred. Please be careful when testing writes
> against a device — see [`doc/PROTOCOL.md`](doc/PROTOCOL.md) for what is
> confirmed vs. inferred.

## Getting set up

The project uses a `src/` layout and targets **Python 3.11+**.

```bash
git clone https://github.com/Ex0danify/BridgeMix.git
cd BridgeMix
pip install -e ".[dev]"     # installs runtime + dev deps (pytest, ruff)
```

`./setup.sh` is the end-user installer (conda/venv auto-detect + apps-menu
integration); for development a plain editable install as above is simplest.

## Running the tests

```bash
QT_QPA_PLATFORM=offscreen pytest
```

The suite is hardware-free — the MIDI transport is mocked, so you don't need a
Bridge Cast connected. `QT_QPA_PLATFORM=offscreen` lets the Qt-dependent tests
run without a display. CI runs this same command on Python 3.11 and 3.12 (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

Coverage is highest in the protocol/logic layers (`device/`, `midi/`,
`preset/`). When adding or changing protocol encoding, please add a test that
asserts the exact wire frame — `tests/test_bridge_cast.py` and
`tests/test_sysex.py` show the pattern (build a frame, decode with
`sysex.parse`, assert section/type/address/value).

## Code style

We use [ruff](https://docs.astral.sh/ruff/) (config in `pyproject.toml`,
100-col lines):

```bash
ruff check .
ruff check --fix .   # auto-fix what it can
ruff format .        # CI runs `ruff format --check`
```

Match the surrounding code's conventions. The codebase favours small, focused
modules and keeps all SysEx frame construction behind `midi/sysex.py` — please
don't hand-roll byte arrays elsewhere.

## Packaged builds

Windows (installer plus a portable zip) and macOS (`.dmg`) builds are frozen with PyInstaller from
[`packaging/bridgemix.spec`](packaging/bridgemix.spec) and attached to each release by
`.github/workflows/release.yml`. To try one locally:

```bash
pip install -e ".[build]"
pyinstaller --noconfirm packaging/bridgemix.spec
dist/BridgeMix/BridgeMix --smoke-test
```

Frozen builds can't self-update from git or install plugin dependencies with pip.

## Submitting changes

1. Branch off `master`.
2. Keep changes focused; add tests for protocol/logic changes.
3. Make sure `pytest` passes and `ruff check` and `ruff format --check` are clean.
4. Give the pull request a [Conventional Commit](https://www.conventionalcommits.org/) title,
   e.g. `fix(midi): reopen the port after unplug` or `feat(plugins): add a settings page`
   (types: feat, fix, perf, revert, refactor, docs, style, test, build, ci, chore; `!` before the
   colon marks a breaking change). PRs are squash-merged with that title, and release-please
   writes the release notes and picks the next version from it. Don't edit `__version__` by hand.
5. Open a pull request describing **what** changed and, for protocol work,
   **how** you confirmed it (e.g. MIDI capture from the official app, observed
   device behaviour). Note your device model and firmware version.

## Reporting bugs

Open an issue with:

- your device model (Bridge Cast original / V2 / X) and firmware version,
- your OS and Python version,
- what you did, what you expected, and what happened.

For protocol discoveries (new addresses, corrections), a MIDI capture or a
clear description of the device's response is incredibly helpful.

## License

By contributing you agree that your contributions are licensed under the
project's **GPL-3.0-or-later** license.
