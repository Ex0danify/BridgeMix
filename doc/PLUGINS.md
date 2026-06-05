# Writing a BridgeMix plugin

BridgeMix's **Extras** panel is a plugin host. A plugin is a folder containing a
`plugin.toml` manifest and a Python entry module that exposes a `Plugin`
subclass. Drop it into the plugins directory, hit **Rescan** (or restart), and it
autowires its own card into the panel.

The REST API that ships with BridgeMix is itself a plugin — see
`src/bridgemix/plugins/builtins/remote_api/` for a complete, real example.

---

## Where plugins live

```
$XDG_DATA_HOME/bridgemix/plugins/        (default: ~/.local/share/bridgemix/plugins)
└── my-plugin/
    ├── plugin.toml      # manifest (required)
    └── my_plugin.py     # entry module (name is up to you)
```

The path is derived from XDG environment variables, so it resolves correctly
inside a Flatpak sandbox too (`~/.var/app/<app-id>/data/bridgemix/plugins`). The
exact folder is shown in the Plugins panel.

## ⚠️ Security — Read This!

A plugin is **arbitrary Python that runs with BridgeMix's full privileges**: your
files, your network, your environment. There is no sandbox. BridgeMix therefore:

- never executes a freshly discovered plugin — it appears **disabled**;
- shows a **one-time consent prompt** (manifest + declared permissions) the first
  time you enable a user plugin.

Only install plugins from sources you trust, exactly as you would an OBS or
VS Code extension.

## The manifest — `plugin.toml`

```toml
id = "io.github.you.my-plugin"     # unique; reverse-DNS recommended
name = "My Plugin"
version = "1.0.0"
description = "What it does, in one line."
maintainer = "Your Name <you@example.com>"
homepage = "https://github.com/you/my-plugin"
license = "MIT"

entry_point = "my_plugin:MyPlugin"  # "<entry module>:<Plugin subclass>"

host_api = ">=1.0,<2.0"             # plugin-API versions you support
requires = []                       # optional pip dependencies
permissions = ["device.read", "device.write", "network"]
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | ✓ | Stable unique identifier. Used for settings/consent storage. |
| `name`, `version` | ✓ | Shown on the card. |
| `entry_point` | ✓ | `module:ClassName`. The module is resolved inside your plugin folder. |
| `host_api` | – | Comma-separated version clauses (`>=1.0,<2.0`); `*`/omitted = any. Checked against the host's `PLUGIN_API_VERSION`, **not** the app version. |
| `requires` | – | pip requirement strings. If missing and the environment allows it, the host offers an in-app install (not under Flatpak). All plugins share one interpreter — see *Dependency conflicts* below. |
| `permissions` | – | Declared, shown at consent time. Informational in this version. |

A malformed or incompatible manifest produces a visible error/incompatible card
— it never crashes the app.

## The rules (what a plugin is)

- A plugin **MUST** subclass `bridgemix.plugins.Plugin` and implement
  `create_widget(ctx) -> QWidget`, returning a real `QWidget` — the host rejects
  anything else with an error card.
- Keep `__init__` cheap and side-effect-free (no I/O, no threads).
- A plugin **MAY** implement `shutdown()`; it must be safe to call even if
  `create_widget` never ran.
- Import **only** from `bridgemix.plugins`. Everything you may touch arrives via
  `PluginContext`; the rest of `bridgemix` is not a stable API.
- `create_widget` is called **once, on the GUI thread**, and only after the
  plugin is compatible + consented + enabled + dependency-satisfied +
  conflict-free. Reach the device only through `ctx.device`; persist state only
  through `ctx.settings`.
- **One plugin → one widget/card.**
- Any exception you raise during load is isolated into an error card — it never
  crashes the app.

## The entry module

Import **only** from `bridgemix.plugins` — that is the stable API. Everything else
in `bridgemix` may change without notice.

```python
from PyQt6.QtWidgets import QLabel, QWidget
from bridgemix.plugins import Plugin, PluginContext


class MyPlugin(Plugin):
    def create_widget(self, ctx: PluginContext) -> QWidget:
        # Called once, on the GUI thread, after the plugin is enabled.
        last = ctx.settings.get("last_value", 0)
        ctx.log.info("loading; last_value=%s", last)
        return QLabel(f"Hello from BridgeMix {ctx.host_version}")

    def shutdown(self) -> None:
        # Optional. Stop threads/servers here; called on quit or disable.
        ...
```

### What the context gives you

```python
ctx.device        # DeviceFacade — thread-safe device access (see below)
ctx.settings      # SettingsStore — your private persisted key/value store
ctx.log           # logging.Logger namespaced to your plugin
ctx.host_version  # BridgeMix's version string
ctx.plugin_dir    # Path to your plugin folder (for bundled assets)
```

### Optional: `PluginWidget`

You can return any `QWidget`. If you'd rather not write boilerplate, subclass the
optional `PluginWidget` base — it stashes the context (and exposes
`device`/`settings`/`log`) and gives you a ready `body` layout:

```python
from bridgemix.plugins import Plugin, PluginWidget

class MyWidget(PluginWidget):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.body.addWidget(QLabel(f"Hi from BridgeMix {self.ctx.host_version}"))

class MyPlugin(Plugin):
    def create_widget(self, ctx):
        return MyWidget(ctx)
```

`PluginWidget` also offers two optional overrides the host honours when it builds
your card:

* `header_widget()` — return a single compact control (typically your primary
  on/off toggle) and the host shows it in the card **header**, next to the name and
  version, instead of in the body. Return the *same* widget each call. Default:
  nothing.
* `card_width()` — return `CardWidth.COMPACT` to keep a small plugin from
  stretching across the panel (compact cards take their natural width and pack side
  by side); `CardWidth.FULL` (the default) spans the panel width.

```python
from bridgemix.plugins import CardWidth, PluginWidget

class MyWidget(PluginWidget):
    def header_widget(self):
        return self._toggle          # shown in the card header

    def card_width(self):
        return CardWidth.COMPACT     # don't hog the whole panel
```

### Matching the app's look (`style`)

The app's stylesheet is applied globally, so plain Qt widgets (`QPushButton`,
`QComboBox`, `QListWidget`, `QGroupBox`, `QSlider`, …) **already match BridgeMix**
inside your card — you usually don't need to do anything. For the rest,
`from bridgemix.plugins import style` gives you:

```python
from bridgemix.plugins import style

# Design tokens — colours for stylesheets / painting
label.setStyleSheet(f"color: {style.ACCENT};")
style.ACCENT_SOFT                    # rgba accent fill (selected/checked)
style.CHANNEL_COLORS["mic"]          # "#e05c12"
painter.setPen(style.Q_TEXT_MUTED)   # QColor for QPainter

# Role helpers — apply a named look (they return the widget)
style.primary_button(QPushButton("Save"))      # filled orange
style.danger_button(QPushButton("Reset"))      # red destructive
style.segmented_button(QPushButton("Mic"))     # checkable segmented selector
style.page_title(QLabel("My Plugin"))
style.section_label(QLabel("OPTIONS"))         # small uppercase caption
style.value_label(QLabel("0 dB"))              # monospace readout
style.muted(QLabel("hint"))
style.fader(QSlider(Qt.Orientation.Vertical))                  # orange fader
style.fader(QSlider(Qt.Orientation.Vertical), readonly=True)   # grey, display-only

# Signature controls
toggle = style.ToggleSwitch(checked=False)   # the orange pill toggle
meter  = style.PeakMeter(100)                # VU meter
combo  = style.ComboBox()                    # scroll-guarded inputs
spin   = style.SpinBox()
```

A plain **checkable `QPushButton`** already turns accent-orange when checked, and
a plain **`QListWidget`** already gets the app's selection styling — so simple
toggle buttons and list selectors need no helper at all.

### Talking to the device safely

The Bridge Cast is owned by the GUI thread and must never be touched from another
thread. `ctx.device` marshals every call onto the GUI thread for you, so it is
safe to use from your own worker threads:

```python
ctx.device.status()                       # {"connected": ..., "model": ...}
ctx.device.list_parameters()              # all params with ranges + values
ctx.device.get_parameter("st_mic_vol")
ctx.device.set_parameter("st_mic_vol", 42)

# Subscribe to device events (Qt delivers these across threads):
ctx.device.parameter_changed.connect(my_slot)
ctx.device.connected.connect(my_slot)

# Run arbitrary GUI-thread work and get the result back:
result = ctx.device.call(lambda: some_gui_only_thing())
```

Every parameter read/write needs a connected device: when none is attached they
raise `DeviceNotConnected`, so your plugin never acts on (or shows) stale values.
Only `status()` answers regardless — use it to check connectivity. The exceptions
are importable from `bridgemix.plugins`:

```python
from bridgemix.plugins import DeviceNotConnected

try:
    ctx.device.set_parameter("st_mic_vol", 42)
except DeviceNotConnected:
    ...  # device unplugged — skip, retry, or reflect it in your UI
```

`ParameterNotFound`, `ParameterReadOnly` and `ParameterOutOfRange` are exported the
same way for the write-validation cases.

### Persisting settings

```python
ctx.settings.get("key", default)
ctx.settings.set("key", value)            # persisted immediately
ctx.settings.update({"a": 1, "b": 2})     # persisted once
```

Stored as JSON under `$XDG_CONFIG_HOME/bridgemix/plugin-data/<id>.json`.

## Tests

A plugin owns its tests — keep them in a `tests/` folder inside the plugin.

```
my-plugin/
├── plugin.toml
├── my_plugin.py
└── tests/
    └── test_my_plugin.py
```

Import your plugin with absolute imports and use a `qapp` fixture (a shared
`QApplication`) for any widget tests. The built-in Remote API plugin's
`tests/` folder is a complete worked example. In this repo those tests are
discovered automatically by pytest and kept out of the built wheel.

## Versioning

The plugin contract is versioned (`PLUGIN_API_VERSION`).
Declare the range you support in `host_api`; the host refuses to load a plugin it
can't satisfy and shows it as *incompatible* rather than loading it blindly.

## Dependency conflicts

All plugins run in **one Python interpreter**, so there can only be a single
installed version of any package. The host:

- installs the **union** of every enabled plugin's `requires` in one resolved
  `pip install`, so versions are reconciled rather than overwritten one-by-one;
- **flags a conflict** when two enabled plugins need incompatible versions of the
  same distribution (e.g. `numpy<2` vs `numpy>=2`) — both show a *conflict* card
  and neither loads until you disable one.

Practical advice: depend on **wide ranges** (`numpy>=1.24`, not `numpy==1.26.4`)
to stay compatible with other plugins, and lean on packages already in the app
(`PyQt6`, `numpy`) instead of adding new ones.

## Limitations (current version)

- New plugins are picked up by **Rescan**; *removing* or *upgrading* a plugin
  needs an app restart for clean teardown.
- Entry-module names should be unique-ish; your folder is added to `sys.path`, so
  prefer a distinctive top-level module name (or ship a package).
- `permissions` are declared and shown, not enforced.
