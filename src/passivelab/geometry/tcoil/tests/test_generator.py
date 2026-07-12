"""Validation for the gdstk T-coil generator (Phase 1 sub-phase 1.1.2). Criterion: "prototype
emits valid GDS with the 11 parameters wired" -- tested here as (1) a real GDS write/read-back
round trip and (2) each of the 11 TCoilParams fields measurably changing the output geometry.
"""
from __future__ import annotations

import dataclasses
import pathlib

import gdstk
import pytest

from passivelab.geometry.tcoil import TCoilParams, generate_tcoil

# The golden notebook's own smoke-test vector (tcoil_bias.py, cell 10):
# CreateTCoilTraceVanilla(7, 12, 150, 120, 10, 4, 10, 0.5, 0.5, 30, includepad=True)
BASELINE = TCoilParams(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                        tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)


def _summary(cell: gdstk.Cell) -> tuple:
    """A fingerprint of a cell's full geometry: polygon count, bounding box, and every
    polygon's rounded vertex coordinates (so interior-only coordinate shifts -- e.g. a tap
    port moving along an already-placed segment -- are detected, not just bbox/count changes)."""
    polys = cell.get_polygons()
    points = tuple(sorted(
        (p.layer, p.datatype, tuple((round(x, 6), round(y, 6)) for x, y in p.points))
        for p in polys
    ))
    return len(polys), cell.bounding_box(), points


def test_generates_nonempty_cell():
    cell = generate_tcoil(BASELINE)
    assert len(cell.get_polygons()) > 0


def test_gds_round_trip(tmp_path: pathlib.Path):
    cell = generate_tcoil(BASELINE)
    lib = gdstk.Library()
    lib.add(cell)
    out = tmp_path / "tcoil.gds"
    lib.write_gds(str(out))

    assert out.exists() and out.stat().st_size > 0

    read_back = gdstk.read_gds(str(out))
    cells = read_back.top_level()
    assert len(cells) == 1
    assert cells[0].name == cell.name
    assert len(cells[0].get_polygons()) == len(cell.get_polygons())


def test_determinism():
    """Same params -> identical geometry across repeated runs (golden-layout regression
    philosophy, Master PRD §9)."""
    a = _summary(generate_tcoil(BASELINE))
    b = _summary(generate_tcoil(BASELINE))
    assert a == b


@pytest.mark.parametrize("field,delta", [
    ("wid", 2),
    ("gap", 4),
    ("sizX", 20),
    ("sizY", 20),
    ("firY", 10),
    ("tapseg", 2),
    ("nseg", 4),
    ("tapratio", 0.15),
    ("endratio", 0.15),
    ("Lext", 10),
    ("pad_siz", 20),
])
def test_all_eleven_params_wired(field, delta):
    """Each of the 11 TCoilParams fields measurably changes the generated geometry."""
    perturbed = dataclasses.replace(BASELINE, **{field: getattr(BASELINE, field) + delta})
    baseline_summary = _summary(generate_tcoil(BASELINE))
    perturbed_summary = _summary(generate_tcoil(perturbed))
    assert baseline_summary != perturbed_summary, f"changing {field} had no effect on the geometry"


def test_includepad_toggles_pad_geometry():
    with_pad = _summary(generate_tcoil(BASELINE))
    without_pad = _summary(generate_tcoil(dataclasses.replace(BASELINE, includepad=False)))
    assert with_pad != without_pad
