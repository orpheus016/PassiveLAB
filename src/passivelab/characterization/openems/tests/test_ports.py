"""Tests for port re-embedding + port-definition derivation (sub-phase 1.4.1). Pure gdstk/Python,
no openEMS/CSXCAD needed -- runs in every CI build, not just the on-demand integration test.

This is the regression coverage for the specific concern raised during planning: ``split_ports()``
(sub-phase 1.3.2) strips the openEMS-only port markers out of the PDK-facing ``Layout.cell`` into
``Layout.metadata["ports_cell"]`` -- correct for keeping the PDK-facing GDS clean, but it means a
GDS written from ``layout.cell`` alone has zero port markers, which the vendored
``addPorts_to_CSX`` needs to create any excitation at all. These tests prove the merge puts them
back before anything reaches the solver, using the *real* T-coil generator (not a stub), since a
stub wouldn't exercise ``split_ports()``'s actual layer assignment.
"""
from __future__ import annotations

import gdstk
import pytest

import passivelab.geometry.tcoil  # self-registers "tcoil"
from passivelab.characterization.openems.ports import (
    PORT_LENGTH,
    PORT_START,
    derive_port_definitions,
    merge_layout_for_solver,
)
from passivelab.core import generate
from passivelab.geometry.tcoil.spec import TCoilSpec

_BASELINE_FIELDS = dict(
    wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
    tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True,
)


def _tcoil_layout(**overrides):
    spec = TCoilSpec(**{**_BASELINE_FIELDS, **overrides})
    return generate(spec)


def test_split_ports_leaves_the_pdk_cell_with_no_port_layers():
    # sanity check on the precondition this module exists to fix -- if this ever stops being
    # true, the merge below becomes a no-op and the "load-bearing" framing is wrong.
    layout = _tcoil_layout()
    cell_layers = {p.layer for p in layout.cell.polygons}
    cell_layers |= {layer for p in layout.cell.paths for layer in p.layers}
    port_layers = set(range(PORT_START, PORT_START + 4))
    assert not (cell_layers & port_layers)


def test_merge_layout_for_solver_reembeds_all_present_port_layers():
    layout = _tcoil_layout()
    ports_cell = layout.metadata["ports_cell"]
    expected_port_layers = {p.layer for p in ports_cell.polygons}
    expected_port_layers |= {layer for p in ports_cell.paths for layer in p.layers}
    assert expected_port_layers  # this baseline spec is known to exercise the tap (202 present)
    assert {PORT_START + 1, PORT_START + 2, PORT_START + 3} <= expected_port_layers

    merged = merge_layout_for_solver(layout)

    merged_layers = {p.layer for p in merged.polygons}
    merged_layers |= {layer for p in merged.paths for layer in p.layers}
    assert expected_port_layers <= merged_layers


def test_merge_layout_for_solver_does_not_mutate_the_input_layout():
    layout = _tcoil_layout()
    before_cell_count = len(layout.cell.polygons) + len(layout.cell.paths)
    before_ports_count = (len(layout.metadata["ports_cell"].polygons)
                           + len(layout.metadata["ports_cell"].paths))

    merge_layout_for_solver(layout)

    assert len(layout.cell.polygons) + len(layout.cell.paths) == before_cell_count
    assert (len(layout.metadata["ports_cell"].polygons)
            + len(layout.metadata["ports_cell"].paths)) == before_ports_count


def test_merge_layout_for_solver_requires_ports_cell():
    from passivelab.core.types import Layout

    layout = Layout(cell=gdstk.Cell("bare"), metadata={})
    with pytest.raises(KeyError):
        merge_layout_for_solver(layout)


def test_derive_port_definitions_finds_all_three_ports_when_tap_is_exercised():
    layout = _tcoil_layout()
    port_defs = derive_port_definitions(layout.metadata["ports_cell"])

    assert [pd.portnumber for pd in port_defs] == [1, 2, 3]
    assert [pd.source_layernum for pd in port_defs] == [PORT_START + 1, PORT_START + 2, PORT_START + 3]
    assert all(pd.port_z0 == 50.0 for pd in port_defs)
    assert all(pd.direction == "z" for pd in port_defs)
    # 1.4.2: reference-plane/de-embedding convention is explicit data on every port, not just
    # implicit in the generator's geometry.
    assert all(pd.reference_plane_offset == PORT_LENGTH for pd in port_defs)
    assert all(pd.de_embedded is False for pd in port_defs)


def test_derive_port_definitions_renumbers_contiguously_when_tap_is_absent():
    # Simulate an untapped sample directly (rather than searching sampled geometry for one --
    # empirically rare per the 1.4.1 plan) by building a ports_cell with only the PAD/CIR layers,
    # matching what split_ports() would produce if the tap condition (generator.py's
    # `flag_add_tap`) isn't hit for a given geometry.
    ports_cell = gdstk.Cell("ports_untapped")
    ports_cell.add(gdstk.rectangle((0, 0), (1, 1), layer=PORT_START + 1, datatype=0))
    ports_cell.add(gdstk.rectangle((0, 0), (1, 1), layer=PORT_START + 3, datatype=0))

    port_defs = derive_port_definitions(ports_cell)

    # Must be [1, 2], not [1, 3] -- all_simulation_ports.get_port_by_number(n) in the vendored
    # solver indexes its port list as self.ports[n-1], so a gap at "port 2" would either read the
    # wrong port or index out of range for whatever's numbered 3.
    assert [pd.portnumber for pd in port_defs] == [1, 2]
    assert [pd.source_layernum for pd in port_defs] == [PORT_START + 1, PORT_START + 3]
    assert all(pd.reference_plane_offset == PORT_LENGTH for pd in port_defs)
    assert all(pd.de_embedded is False for pd in port_defs)


def test_derive_port_definitions_empty_ports_cell_returns_empty_list():
    assert derive_port_definitions(gdstk.Cell("empty")) == []
