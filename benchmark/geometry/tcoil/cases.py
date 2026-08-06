"""T-coil benchmark vectors (sub-phase 1.3.3, moved out of benchmark_generation_speed.py so both
that file and the cross-device validity/JSON suite share one definition).

Importing this module self-registers these cases into ``benchmark.geometry.registry`` under
``passive_type="tcoil"`` -- the same import-time self-registration pattern as
``geometry/tcoil/__init__.py``'s core-registry registration.
"""
from __future__ import annotations

import passivelab.geometry.tcoil  # noqa: F401 -- self-registers "tcoil" into the core registry
from benchmark.geometry.registry import BenchmarkCase, register_cases
from passivelab.geometry.tcoil import TCoilSpec

SMALL = TCoilSpec(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                   tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)
LARGE = TCoilSpec(wid=5, gap=8, sizX=150, sizY=120, firY=10, tapseg=6, nseg=24,
                   tapratio=0.5, endratio=0.5, Lext=20, pad_siz=50, includepad=True)

CASES = [BenchmarkCase(id="nseg=10", spec=SMALL), BenchmarkCase(id="nseg=24", spec=LARGE)]

try:
    register_cases("tcoil", CASES)
except ValueError:
    pass  # already registered
