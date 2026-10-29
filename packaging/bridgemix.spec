# PyInstaller spec for the Windows and macOS builds:  pyinstaller packaging/bridgemix.spec
# Run it from the repository root with the "build" extra installed (pip install -e ".[build]").
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH).parent
version = {}
exec((root / "src" / "bridgemix" / "__init__.py").read_text(), version)

# Built-in plugins are imported by name at runtime and their manifests are read from
# disk, so neither the code nor the plugin.toml files would be found by static analysis.
hiddenimports = collect_submodules("bridgemix.plugins.builtins")
# The REST API plugin imports these lazily, and checks them via importlib.metadata.
hiddenimports += collect_submodules("uvicorn") + collect_submodules("fastapi")
datas = [
    (str(path), str(path.parent.relative_to(root / "src")))
    for path in (root / "src" / "bridgemix" / "plugins" / "builtins").rglob("plugin.toml")
]
datas += copy_metadata("fastapi") + copy_metadata("uvicorn")
datas += [(str(root / "assets" / "icon.svg"), "assets")]

# Not needed at runtime and large.
excludes = ["tkinter", "matplotlib", "scipy", "pandas", "IPython", "pytest"]

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BridgeMix",
    console=False,  # a GUI app: no terminal window on Windows
    icon=str(root / "assets" / "icon.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="BridgeMix")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="BridgeMix.app",
        icon=str(root / "assets" / "icon.ico"),
        bundle_identifier="io.github.ex0danify.BridgeMix",
        version=version["__version__"],
        info_plist={
            "CFBundleDisplayName": "BridgeMix",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "GPL-3.0-or-later",
        },
    )
