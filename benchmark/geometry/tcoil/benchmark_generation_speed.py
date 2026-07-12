"""pytest-benchmark suite for the gdstk T-coil generator. Run with:

    pytest benchmark/ --benchmark-only --benchmark-autosave

Measures generation time at a couple of `nseg` scales (the notebook batches thousands of
samples in Stage 3 -- does gdstk stay fast as turn count grows?) and records GDS output size.
Not part of the fast CI gate (see benchmark/geometry/tcoil/README.md).
"""
from __future__ import annotations

import gdstk
import pytest

from passivelab.geometry.tcoil import TCoilParams, generate_tcoil

SMALL = TCoilParams(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                     tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)
LARGE = TCoilParams(wid=5, gap=8, sizX=150, sizY=120, firY=10, tapseg=6, nseg=24,
                     tapratio=0.5, endratio=0.5, Lext=20, pad_siz=50, includepad=True)


@pytest.mark.parametrize("params", [SMALL, LARGE], ids=["nseg=10", "nseg=24"])
def test_generation_speed(benchmark, params):
    cell = benchmark(generate_tcoil, params)
    assert len(cell.get_polygons()) > 0


@pytest.mark.parametrize("params", [SMALL, LARGE], ids=["nseg=10", "nseg=24"])
def test_gds_file_size(params, tmp_path):
    cell = generate_tcoil(params)
    lib = gdstk.Library()
    lib.add(cell)
    out = tmp_path / "tcoil.gds"
    lib.write_gds(str(out))
    size = out.stat().st_size
    print(f"\n[gds size] nseg={params.nseg}: {size} bytes, {len(cell.get_polygons())} polygons")
    assert size > 0
