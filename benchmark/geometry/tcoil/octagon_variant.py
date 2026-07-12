"""Bonus/exploratory octagonal-spiral T-coil variant. NOT from the golden notebook -- the real
notebook's coil trace is rectangular/rectilinear (see src/passivelab/geometry/tcoil/generator.py,
a faithful port of CreateTCoilTraceVanilla); only its optional bond pad is octagonal
(templates.create_octagon_pad). This reuses that same octagon angle math to build a full
octagonal spiral instead, mainly to demonstrate gdstk handles non-rectilinear geometry equally
well and to have a second shape worth previewing.
"""
from __future__ import annotations

import gdstk

from passivelab.geometry.tcoil.generator import TCoilParams
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
        if siz <= params.wid * 3:
            break
        pts = create_octagon_points(0, 0, siz)
        ring_layer = thick_metals[turn % 2]
        shape_list.append(gdstk.FlexPath(pts + [pts[0]], params.wid, layer=ring_layer, datatype=0))

    library = gdstk.Library()
    cell = library.new_cell(cell_name)
    cell.add(*shape_list)
    return cell
