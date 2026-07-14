"""No-leakage guard (sub-phase 1.2.2 validation bar).

``core/`` must have **zero references** to any passive device (``tcoil``) or geometry kit
(``gdstk``): the platform contract stays PDK- and device-agnostic; devices attach as plugins that
satisfy the Protocols. This test enforces that on the actual ``import`` statements of every
non-test module under ``core/`` — so it can't silently rot into a claim in a doc.

Note we check imported *module names*, not any word: the docstrings deliberately *mention* tcoil /
gdstk to explain intent, and that's fine — a dependency is an import, not a sentence.
"""
from __future__ import annotations

import pathlib
import re

import passivelab.core

CORE_DIR = pathlib.Path(passivelab.core.__file__).parent
_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)


def _core_source_files():
    return [p for p in CORE_DIR.rglob("*.py") if "tests" not in p.parts]


def test_core_imports_no_device_or_geometry_kit():
    offenders: dict[str, list[str]] = {}
    for path in _core_source_files():
        for mod in _IMPORT_RE.findall(path.read_text(encoding="utf-8")):
            leaks = (
                mod == "gdstk"
                or mod.startswith("gdstk.")
                or mod == "passivelab.geometry"          # the device implementations package
                or mod.startswith("passivelab.geometry.")
            )
            if leaks:
                offenders.setdefault(path.name, []).append(mod)
    assert not offenders, f"core/ must not import passive/geometry-kit modules: {offenders}"


def test_core_covers_every_core_source_file():
    # sanity: the scan actually sees the modules (guards against a bad path silently passing)
    names = {p.name for p in _core_source_files()}
    assert {"types.py", "spec.py", "generator.py", "backend.py",
            "optimizer.py", "validation.py"} <= names
