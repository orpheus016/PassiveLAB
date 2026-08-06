"""pytest-benchmark suite for the T-coil generator, through the real platform path. Run with:

    pytest benchmark/ --benchmark-only --benchmark-autosave

Measures generation time at a couple of `nseg` scales (the notebook batches thousands of
samples in Stage 3 -- does gdstk stay fast as turn count grows?) and records GDS output size.
Not part of the fast CI gate (see benchmark/geometry/tcoil/README.md).

1.3.3: measures ``passivelab.core.generate`` (registry dispatch + 1.3.2's port-marker split),
not the bypassed ``generate_tcoil()`` internal -- this is what a real designer/researcher call
actually costs, not just the raw geometry math. SMALL/LARGE moved to `cases.py`, shared with
`benchmark/geometry/tests/`'s cross-device validity+JSON suite.
"""
from __future__ import annotations

import gdstk
import pytest

from benchmark.geometry.tcoil.cases import LARGE, SMALL
from passivelab.core import generate


@pytest.mark.parametrize("spec", [SMALL, LARGE], ids=["nseg=10", "nseg=24"])
def test_generation_speed(benchmark, spec):
    layout = benchmark(generate, spec)
    assert len(layout.cell.get_polygons()) > 0


@pytest.mark.parametrize("spec", [SMALL, LARGE], ids=["nseg=10", "nseg=24"])
def test_gds_file_size(spec, tmp_path):
    layout = generate(spec)
    lib = gdstk.Library()
    lib.add(layout.cell)
    out = tmp_path / "tcoil.gds"
    lib.write_gds(str(out))
    size = out.stat().st_size
    print(f"\n[gds size] nseg={spec.nseg}: {size} bytes, {len(layout.cell.get_polygons())} polygons")
    assert size > 0
