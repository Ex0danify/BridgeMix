"""Guard against drift between the two declarations of the REST API's deps.

``API_REQUIREMENTS`` (used by the in-app installer) and the ``api`` extra in
pyproject.toml must stay identical — otherwise the installer and ``pip install
bridgemix[api]`` could fetch different versions. This welds them in CI.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from bridgemix.api import API_REQUIREMENTS


def test_api_requirements_match_pyproject_extra():
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extra = pyproject["project"]["optional-dependencies"]["api"]
    assert list(API_REQUIREMENTS) == extra
