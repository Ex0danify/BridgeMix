#!/usr/bin/env python3
"""Regenerate python-deps.json, the offline Python dependencies of the Flatpak.

flatpak-builder builds without network access, so every dependency has to be listed with its URL and checksum. This resolves
the app's dependencies from pyproject.toml (everything except PyQt6, which the PyQt base app provides, plus the built-in
plugins' requirements) to prebuilt wheels for the runtime's Python, and writes them as one flatpak-builder module.

    python packaging/flatpak/generate-deps.py [--python 3.13] [--platform manylinux_2_28_x86_64]

Run it again when pyproject.toml's dependencies change or to move to newer versions. It only talks to PyPI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name("python-deps.json")
PROVIDED_BY_RUNTIME = {"pyqt6"}
# No wheel exists for the runtime's Python, so these are built from source in the sandbox with these build tools.
BUILT_FROM_SOURCE = {"python-rtmidi"}
BUILD_TOOLS = ["cython", "meson-python", "ninja", "wheel"]


def requirements() -> list[str]:
    reqs = list(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"])
    # Built-in plugins declare their own requirements in their manifest.
    for manifest in sorted((ROOT / "src/bridgemix/plugins/builtins").glob("*/plugin.toml")):
        reqs += tomllib.loads(manifest.read_text()).get("requires", [])
    return [r for r in reqs if not r.lower().startswith(tuple(PROVIDED_BY_RUNTIME))]


def pip_download(
    reqs: list[str], dest: Path, python: str, platforms: list[str], *extra: str
) -> None:
    cmd = [
        sys.executable, "-m", "pip", "download", "--quiet", "--dest", str(dest),
        "--python-version", python, "--implementation", "cp", "--abi", f"cp{python.replace('.', '')}",
    ]  # fmt: skip
    for platform in platforms:
        cmd += ["--platform", platform]
    subprocess.run([*cmd, *extra, *reqs], check=True)


def source_entry(path: Path, name: str, version: str) -> dict:
    return {
        "type": "file",
        "url": file_url(name, version, path.name),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def file_url(name: str, version: str, filename: str) -> str:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as response:
        data = json.load(response)
    for item in data["urls"]:
        if item["filename"] == filename:
            return item["url"]
    raise SystemExit(f"{filename} is not on PyPI")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--python", default="3.13", help="the runtime's Python (default: %(default)s)"
    )
    parser.add_argument(
        "--platform",
        action="append",
        help="wheel platform tag, repeatable (default: manylinux x86_64)",
    )
    args = parser.parse_args()
    platforms = args.platform or ["manylinux_2_28_x86_64", "manylinux2014_x86_64", "any"]

    reqs = requirements()
    wheel_reqs = [r for r in reqs if _name(r) not in BUILT_FROM_SOURCE]
    source_reqs = [r for r in reqs if _name(r) in BUILT_FROM_SOURCE]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        runtime_dir, tools_dir, source_dir = root / "runtime", root / "tools", root / "source"
        pip_download(wheel_reqs, runtime_dir, args.python, platforms, "--only-binary=:all:")
        pip_download(BUILD_TOOLS, tools_dir, args.python, platforms, "--only-binary=:all:")
        # Dependencies of a source build come from the lists above, so skip resolving them again.
        pip_download(
            source_reqs, source_dir, args.python, platforms, "--no-binary=:all:", "--no-deps"
        )

        sources, groups = [], {}
        for key, directory in (
            ("runtime", runtime_dir),
            ("tools", tools_dir),
            ("source", source_dir),
        ):
            groups[key] = []
            for path in sorted(directory.iterdir()):
                name, version = _split(path.name)
                if path.name not in {s["url"].rsplit("/", 1)[1] for s in sources}:
                    sources.append(source_entry(path, name, version))
                groups[key].append(path.name)

    find = '--no-index --find-links="file://${PWD}" --no-deps --ignore-installed'
    quote = lambda names: " ".join(f'"{n}"' for n in names)  # noqa: E731
    module = {
        "name": "python-deps",
        "buildsystem": "simple",
        "build-commands": [
            f"pip3 install --verbose {find} --prefix=${{PWD}}/build-tools {quote(groups['tools'])}",
            f"pip3 install --verbose {find} --prefix=${{FLATPAK_DEST}} {quote(groups['runtime'])}",
            # Build from source against the tools above (no isolation: there is no network to fetch them).
            "PYTHONPATH=${PWD}/build-tools/lib/python3.13/site-packages PATH=${PWD}/build-tools/bin:$PATH "
            f"pip3 install --verbose {find} --no-build-isolation --prefix=${{FLATPAK_DEST}} "
            + quote(groups["source"]),
        ],
        "sources": sources,
    }
    names = [n for g in groups.values() for n in g]
    OUTPUT.write_text(json.dumps(module, indent=4) + "\n")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(names)} wheels")


def _name(req: str) -> str:
    return req.split(">")[0].split("=")[0].split("<")[0].strip().lower()


def _split(filename: str) -> tuple[str, str]:
    """Distribution name and version of a wheel or sdist file name."""
    if filename.endswith(".whl"):
        name, version = filename.split("-")[:2]
    else:
        name, _, rest = filename.rpartition("-")
        version = rest.removesuffix(".tar.gz")
    return name, version


if __name__ == "__main__":
    main()
