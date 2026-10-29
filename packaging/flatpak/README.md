# Flatpak

`io.github.ex0danify.BridgeMix.yaml` is the manifest. PyQt6 comes from the PyQt base app; PortAudio is built from source; the other
Python dependencies are listed with URLs and checksums in `python-deps.json`, because `flatpak-builder` builds offline.

Build and run it locally (needs `flatpak-builder` and the KDE 6.11 SDK and PyQt base app from Flathub):

```bash
flatpak-builder --user --install --install-deps-from=flathub --force-clean build-dir \
  packaging/flatpak/io.github.ex0danify.BridgeMix.yaml
flatpak run io.github.ex0danify.BridgeMix
```

## Updating the dependencies

`python-deps.json` is generated from `pyproject.toml` and the built-in plugins' `plugin.toml` files. Run this again when their
dependencies change, or to pick up newer versions (Dependabot does not touch this file):

```bash
python packaging/flatpak/generate-deps.py
```

`python-rtmidi` has no wheel for the runtime's Python, so it is built from source with the tools in `BUILD_TOOLS`. If the
runtime moves to another Python, pass `--python 3.14` and update the `python3.13` path in the generator.

## Permissions

| Permission | Why |
|---|---|
| `--device=all` | the Bridge Cast is a MIDI device; python-rtmidi opens the ALSA sequencer under `/dev/snd` |
| `--socket=pulseaudio` | the routing page and level meters talk to PulseAudio or PipeWire through `pactl` and PortAudio |
| `--share=network` | the optional REST API plugin and the update check |
| `--talk-name=org.kde.StatusNotifierWatcher` | the tray icon |

In the sandbox the app cannot update itself from git or install plugin dependencies with pip. Updates come from Flatpak.
