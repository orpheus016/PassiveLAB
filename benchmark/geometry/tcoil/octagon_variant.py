"""Bonus/exploratory octagonal-spiral T-coil variant. NOT from the golden notebook -- the real
notebook's coil trace is rectangular/rectilinear (see src/passivelab/geometry/tcoil/generator.py,
a faithful port of CreateTCoilTraceVanilla); only its optional bond pad is octagonal
(templates.create_octagon_pad). This reuses that same octagon angle math to build a full
octagonal spiral instead, mainly to demonstrate gdstk handles non-rectilinear geometry equally
well and to have a second shape worth previewing.

Ring construction: each turn is a closed annulus -- gdstk.boolean("not") between an outer and
an inner concentric octagon polygon -- not a stroked FlexPath traced around the vertices.
dgrujic/pcLab's pclab/pclGeom.py::octSegment() (looked at on request) confirmed the general
approach octagon rings need to be built as explicit closed polygons, not stroked paths --
FlexPath's mitering doesn't close cleanly at the 45deg/135deg octagon corners, leaving gaps.
pcLab hand-derives one 8-point polygon per quadrant (with extra ground-contact/bridge details
not needed here); a plain boolean-difference annulus is simpler and still structurally gapless.
Ring width is only approximately `wid` (the inner octagon is offset by `2*wid` in `siz`, which
is a cos(pi/8) factor off an exact constant-width offset) -- fine for this exploratory demo.
"""
from __future__ import annotations

import gdstk

from passivelab.geometry.tcoil.spec import TCoilParams
from passivelab.geometry.tcoil.templates import THICK_METAL_LIST, create_octagon_pad, create_octagon_points


def generate_octagon_variant(params: TCoilParams, *, thick_metals=None,
                              cell_name: str = "tcoil_octagon") -> gdstk.Cell:
    """Concentric octagonal rings, decreasing radius per turn, alternating metal layers --
    the same spiral idea as generate_tcoil, built from octagon rings instead of rectangles.
    No ground plane -- purely a geometry-shape demo, not a DRC-complete structure."""
    thick_metals = thick_metals if thick_metals is not None else THICK_METAL_LIST
    shape_list = [create_octagon_pad(0, 0, siz=params.pad_siz, layer=thick_metals[1])]

    base_siz = max(params.sizX, params.sizY)
    n_turns = max(2, params.nseg // 4)
    for turn in range(n_turns):
        siz = base_siz - turn * 2 * params.gap
        inner_siz = siz - 2 * params.wid
        if inner_siz <= params.wid:
            break
        ring_layer = thick_metals[turn % 2]
        outer = gdstk.Polygon(create_octagon_points(0, 0, siz))
        inner = gdstk.Polygon(create_octagon_points(0, 0, inner_siz))
        shape_list += gdstk.boolean(outer, inner, "not", layer=ring_layer, datatype=0)

    library = gdstk.Library()
    cell = library.new_cell(cell_name)
    cell.add(*shape_list)
    return cell
