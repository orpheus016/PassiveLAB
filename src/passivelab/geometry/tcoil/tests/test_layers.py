"""Layer/datatype legality tests for the T-coil plugin (sub-phase 1.3.2).

Covers the task's two fixes: `_combine_layer`'s duplicate-geometry bug (generator.py) and
`split_ports`'s separation of openEMS-only port markers from the PDK-facing cell.
"""
from __future__ import annotations

import gdstk
import pytest

from passivelab.geometry.tcoil.generator import generate_tcoil, split_ports
from passivelab.geometry.tcoil.plugin import TCoilLayoutGenerator
from passivelab.geometry.tcoil.spec import TCoilParams, TCoilSpec
from passivelab.geometry.tcoil.templates import ALL_LAYERS, PORT_START

BASELINE_FIELDS = dict(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                       tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)
PDK_LAYER_DATATYPES = {(layer, 0) for layer in ALL_LAYERS}


def _by_layer(cell: gdstk.Cell, layer: int, datatype: int = 0):
    return cell.get_polygons(layer=layer, datatype=datatype)


def test_combine_layer_leaves_no_duplicate_overlapping_geometry():
    """Re-unioning an already-generated layer must be a no-op (same area) -- if _combine_layer
    left duplicate/overlapping originals behind (the pre-1.3.2 bug), re-unioning would collapse
    them and shrink the area."""
    cell = generate_tcoil(TCoilParams(**BASELINE_FIELDS))
    for layer in ALL_LAYERS:
        polys = _by_layer(cell, layer)
        if not polys:
            continue
        before_area = sum(p.area() for p in polys)
        reunioned = gdstk.boolean(polys, [], "or")
        after_area = sum(p.area() for p in reunioned)
        assert after_area == pytest.approx(before_area), (
            f"layer {layer} has duplicate/overlapping geometry: "
            f"{before_area} area before re-union, {after_area} after"
        )


def test_split_ports_conserves_polygon_count():
    cell = generate_tcoil(TCoilParams(**BASELINE_FIELDS))
    original_count = len(cell.get_polygons())
    clean, ports = split_ports(cell)
    assert len(clean.get_polygons()) + len(ports.get_polygons()) == original_count


def test_split_ports_removes_port_layers_from_the_clean_cell():
    cell = generate_tcoil(TCoilParams(**BASELINE_FIELDS))
    clean, _ports = split_ports(cell)
    assert all(not (PORT_START <= p.layer < PORT_START + 4) for p in clean.get_polygons())


def test_split_ports_isolates_only_port_layers_and_is_nonempty():
    cell = generate_tcoil(TCoilParams(**BASELINE_FIELDS))
    _clean, ports = split_ports(cell)
    port_polys = ports.get_polygons()
    assert len(port_polys) > 0
    assert all(PORT_START <= p.layer < PORT_START + 4 for p in port_polys)


def test_plugin_boundary_layout_cell_has_no_foreign_layers():
    """The task's literal validation criterion: the generated GDS a platform caller actually
    receives (Layout.cell, through the plugin) contains only sourced SG13G2 (layer, datatype)
    pairs -- zero layers KLayout would flag as unknown against sg13g2.lyp."""
    layout = TCoilLayoutGenerator().generate(TCoilSpec(**BASELINE_FIELDS))
    inventory = {(p.layer, p.datatype) for p in layout.cell.get_polygons()}
    assert inventory <= PDK_LAYER_DATATYPES, f"foreign (layer, datatype) pairs: {inventory - PDK_LAYER_DATATYPES}"
