"""T-coil benchmark vectors (sub-phase 1.3.3, moved out of benchmark_generation_speed.py so both
that file and the cross-device validity/JSON suite share one definition).

Cases loaded from JSON via ``passivelab.core.load_spec()`` (config/ refactor) instead of
hardcoded ``TCoilSpec(...)`` literals. ``SMALL`` points at ``examples/tcoil.spec.json`` directly
(the canonical baseline spec, see ``src/passivelab/config/paths.py``) rather than adding a
redundant fourth copy of the same values (it was already duplicated in this file, in
``tests/test_cli.py``'s ``BASELINE_FIELDS``, and in the example itself); ``LARGE`` is new data at
``config/cases/tcoil/large.json``, since it had no existing canonical home.

Importing this module self-registers these cases into ``benchmark.geometry.registry`` under
``passive_type="tcoil"`` -- the same import-time self-registration pattern as
``geometry/tcoil/__init__.py``'s core-registry registration.
"""
from __future__ import annotations

import pathlib

import passivelab.geometry.tcoil  # noqa: F401 -- self-registers "tcoil" into the core registry
from benchmark.geometry.registry import BenchmarkCase, register_cases
from passivelab.core import load_spec

# tcoil/ -> geometry/ -> benchmark/ -> repo root. File-relative, not a bare relative string --
# this module runs at *import* time (self-registration side effect), so it can't assume CWD ==
# repo root the way a test function's relative path can (pytest's CWD is the repo root).
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

SMALL = load_spec(_REPO_ROOT / "examples" / "tcoil.spec.json")
LARGE = load_spec(_REPO_ROOT / "config" / "cases" / "tcoil" / "large.json")

CASES = [BenchmarkCase(id="nseg=10", spec=SMALL), BenchmarkCase(id="nseg=24", spec=LARGE)]

try:
    register_cases("tcoil", CASES)
except ValueError:
    pass  # already registered
