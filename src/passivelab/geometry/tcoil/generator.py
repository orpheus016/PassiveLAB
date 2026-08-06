"""T-coil geometry generator — faithful gdstk port of the golden notebook's
`CreateTCoilTraceVanilla` + `CombineLayer` (tcoil_bias.py, gdspy). Geometry math and control
flow are unchanged from the notebook; only the shape-construction API calls are translated to
gdstk (see docs/GENERATOR_COMPARISON_MATRIX.md for the API map and porting notes).

Pure generation logic only — `TCoilParams` (the params dataclass) lives in `spec.py`, per the
per-device folder pattern in `geometry/GOAL.md`.

Source: reference/markdown/TCoil_Dataset_Generator_and_Training.md, lines 204-524.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import gdstk

from passivelab.geometry.tcoil.templates import (
    M4_METAL,
    M5_METAL,
    PORT_LENGTH,
    PORT_START,
    THICK_METAL_LIST,
    V_BELOW,
    create_ground_plane,
    create_octagon_pad,
    create_via_array,
)

if TYPE_CHECKING:  # type-only: spec.py imports rules.py, which type-hints against TCoilParams
    from passivelab.geometry.tcoil.spec import TCoilParams  # too -- avoid a runtime import cycle


def _combine_layer(cell: gdstk.Cell, target_layer: int) -> None:
    """Merge all polygons on `target_layer` into their union, replacing the pre-merge originals.
    gdstk equivalent of the notebook's CombineLayer (which used gdspy's predicate-based
    remove_polygons).

    1.3.2 fix: `cell.get_polygons()` returns *copies* ("Return a copy of all polygons in the
    cell", its own docstring), so the previous `cell.remove(*cell.get_polygons(...))` was a
    silent no-op -- the true originals never left the cell, and the freshly unioned polygon was
    added on top of them. Reproduced against the baseline T-coil: layer 126 (Thick Metal 2)
    carried 7 polygons totaling 7903 area units where the true union is 2 polygons totaling
    3878 -- every combined layer was silently doubled. Filtering the cell's *real* children
    (`cell.polygons`/`cell.paths`) gives `cell.remove()` actual targets instead.
    """
    originals = [p for p in cell.polygons if p.layer == target_layer and p.datatype == 0]
    originals += [p for p in cell.paths
                  if p.layers == (target_layer,) and p.datatypes == (0,)]
    if not originals:
        return
    merged = gdstk.boolean(originals, [], "or", layer=target_layer, datatype=0)
    cell.remove(*originals)
    cell.add(*merged)


def split_ports(cell: gdstk.Cell, *, port_start: int = PORT_START, port_count: int = 4,
                 ports_cell_name: str | None = None) -> tuple[gdstk.Cell, gdstk.Cell]:
    """Separate the openEMS-only port-marker shapes (layers `port_start..port_start+port_count-1`)
    out of `cell` into their own cell, leaving only PDK-legal geometry behind (1.3.2).

    The port markers are simulation scaffolding inherited verbatim from the golden notebook
    (`port_start = 200`, `reference/python/TCoil_Dataset_Generator_and_Training.py:222`) -- real
    generated content, needed by a future openEMS `SimulationBackend` (1.4), but on layer numbers
    foreign to any real SG13G2 GDS layer (unlike `THICK_METAL_LIST`/`V_THICK`/`M5_METAL`/
    `M4_METAL`/`V_BELOW`, which are cited PDK numbers). They only became a problem once the
    platform started handing this cell out as a general-purpose `Layout` for tools like KLayout
    to open directly. Filters the cell's real children the same way `_combine_layer` does, so
    `cell.remove()` has actual targets (see that function's docstring for why `get_polygons()`
    copies don't work for this).
    """
    port_layers = range(port_start, port_start + port_count)
    ports = [p for p in cell.polygons if p.layer in port_layers]
    ports += [p for p in cell.paths if any(layer in port_layers for layer in p.layers)]
    if ports:
        cell.remove(*ports)
    ports_cell = gdstk.Cell(ports_cell_name or f"{cell.name}_ports")
    if ports:
        ports_cell.add(*ports)
    return cell, ports_cell


def generate_tcoil(params: TCoilParams, *, thick_metals=None, gnd_metal=M5_METAL,
                    real_gnd_metal=M4_METAL, cell_name: str = "tcoil") -> gdstk.Cell:
    """Generate one T-coil trace as a gdstk.Cell, combined per layer (matches the notebook's
    own usage pattern: build shapes, add to a cell, CombineLayer each layer)."""
    thick_metals = thick_metals if thick_metals is not None else THICK_METAL_LIST
    wid, gap, sizX, sizY, firY = params.wid, params.gap, params.sizX, params.sizY, params.firY
    tapseg, nseg = params.tapseg, params.nseg
    tapratio, endratio, Lext = params.tapratio, params.endratio, params.Lext
    pad_siz, includepad = params.pad_siz, params.includepad

    shape_list = []

    if includepad:
        shape_list.append(create_octagon_pad(-gap - Lext - pad_siz / 2, firY, siz=pad_siz,
                                              layer=thick_metals[1]))
        gnd_plane = gdstk.boolean(
            create_ground_plane(sizX, sizY, gap),
            create_octagon_pad(-gap - Lext - pad_siz / 2, firY, siz=pad_siz + 10),
            "not", layer=real_gnd_metal, datatype=0)
    else:
        gnd_plane = create_ground_plane(sizX, sizY, gap, real_gnd_metal=real_gnd_metal)

    shape_list.append(gdstk.FlexPath(
        [(-gap - Lext, firY), (-gap, firY), (-gap, 0), (0, 0)], wid,
        layer=thick_metals[1], datatype=0))
    gnd_plane = gdstk.boolean(
        gnd_plane,
        gdstk.FlexPath([(-gap - (gap + wid) / 2, firY), (-gap, firY), (-gap, 0), (0, 0)],
                       gap + wid),
        "not", layer=real_gnd_metal, datatype=0)
    shape_list += gnd_plane

    # Create #1 port (PAD)
    if includepad:
        shape_list.append(gdstk.rectangle(
            (-gap - Lext - pad_siz / 2 - PORT_LENGTH / 2, firY - PORT_LENGTH / 2),
            (-gap - Lext - pad_siz / 2 + PORT_LENGTH / 2, firY + PORT_LENGTH / 2),
            layer=PORT_START + 1, datatype=0))
        shape_list.append(gdstk.FlexPath(
            [(-gap - Lext - pad_siz / 2 - PORT_LENGTH / 2, firY), (-gap - Lext + 10, firY)],
            PORT_LENGTH, layer=real_gnd_metal, datatype=0))
    else:
        shape_list.append(gdstk.FlexPath(
            [(-gap - Lext, firY), (-gap - Lext + PORT_LENGTH, firY)], wid,
            layer=PORT_START + 1, datatype=0))

    for tid in range(nseg):
        org_id_turn = tid // 4
        cur_metal = (org_id_turn + 1) % 2
        id_turn = org_id_turn // 2

        if tid == nseg - 1:
            match tid % 4:
                case 0:  # Bottom horizontal
                    if org_id_turn > 0:
                        shape_list += create_via_array(
                            max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0),
                            org_id_turn * gap, wid, wid)
                    startx = max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0)
                    termix = sizX - id_turn * gap
                    tmp_list = [(startx, org_id_turn * gap + wid / 2), (startx, id_turn * gap),
                                (startx + (termix - startx) * endratio + wid / 2, id_turn * gap)]
                    shape_list.append(gdstk.FlexPath(tmp_list, wid, layer=thick_metals[cur_metal], datatype=0))
                    lstx, lsty = tmp_list[-1]
                    lstx -= wid / 2
                    shape_list.append(gdstk.FlexPath([(lstx, lsty + wid / 2), (lstx, -Lext)], wid,
                                                      layer=gnd_metal, datatype=0))
                    port_loc = [(lstx, -Lext + PORT_LENGTH), (lstx, -Lext)]
                case 1:  # Right vertical
                    startx, termix = id_turn * gap, sizY - id_turn * gap
                    tmp_list = [(sizX - id_turn * gap, -wid / 2 + startx),
                                (sizX - id_turn * gap, wid / 2 + startx + (termix - startx) * endratio)]
                    shape_list.append(gdstk.FlexPath(tmp_list, wid, layer=thick_metals[cur_metal], datatype=0))
                    lstx, lsty = tmp_list[-1]
                    lsty -= wid / 2
                    shape_list.append(gdstk.FlexPath([(lstx - wid / 2, lsty), (sizX + Lext, lsty)], wid,
                                                      layer=gnd_metal, datatype=0))
                    port_loc = [(sizX + Lext - PORT_LENGTH, lsty), (sizX + Lext, lsty)]
                case 2:  # Top horizontal
                    startx, termix = sizX - id_turn * gap, id_turn * gap
                    tmp_list = [(-wid / 2 + startx, sizY - id_turn * gap),
                                (wid / 2 + startx + (termix - startx) * endratio, sizY - id_turn * gap)]
                    shape_list.append(gdstk.FlexPath(tmp_list, wid, layer=thick_metals[cur_metal], datatype=0))
                    lstx, lsty = tmp_list[-1]
                    lstx += wid / 2
                    shape_list.append(gdstk.FlexPath([(lstx, lsty - wid / 2), (lstx, sizY + Lext)], wid,
                                                      layer=gnd_metal, datatype=0))
                    port_loc = [(lstx, sizY + Lext - PORT_LENGTH), (lstx, sizY + Lext)]
                case 3:  # Left vertical
                    startx = sizY - id_turn * gap
                    termix = id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap)
                    tmp_list = [(id_turn * gap, wid / 2 + startx),
                                (id_turn * gap, -wid / 2 + startx - (startx - termix) * endratio)]
                    shape_list.append(gdstk.FlexPath(tmp_list, wid, layer=thick_metals[cur_metal], datatype=0))
                    lstx, lsty = tmp_list[-1]
                    lsty += wid / 2
                    shape_list.append(gdstk.FlexPath([(lstx + wid / 2, lsty), (-Lext, lsty)], wid,
                                                      layer=gnd_metal, datatype=0))
                    port_loc = [(-Lext + PORT_LENGTH, lsty), (-Lext, lsty)]

            # Create #3 port (CIR)
            shape_list.append(gdstk.FlexPath(port_loc, wid, layer=PORT_START + 3, datatype=0))
            shape_list += create_via_array(lstx, lsty, wid, wid, viasize=0.42, viaspace=0.42,
                                            enclosure=0.1, layer=V_BELOW)
            shape_list.append(gdstk.rectangle((lstx - wid / 2, lsty - wid / 2),
                                               (lstx + wid / 2, lsty + wid / 2),
                                               layer=gnd_metal, datatype=0))
            if cur_metal == 1:
                shape_list += create_via_array(lstx, lsty, wid, wid)
                shape_list.append(gdstk.rectangle((lstx - wid / 2, lsty - wid / 2),
                                                   (lstx + wid / 2, lsty + wid / 2),
                                                   layer=thick_metals[0], datatype=0))
        else:
            if tid == tapseg:
                flag_add_tap = False
                if cur_metal == 0 or cur_metal == 1 and id_turn == (nseg - 1) // 8 and nseg - 1 - tid < 4:
                    flag_add_tap = True
                    match tid % 4:
                        case 0:  # Bottom horizontal
                            startx = max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0)
                            termix = sizX - id_turn * gap
                            lstx, lsty = (startx + (termix - startx) * tapratio + wid / 2, id_turn * gap)
                            lstx -= wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty + wid / 2), (lstx, -Lext)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(lstx, -Lext + PORT_LENGTH), (lstx, -Lext)]
                        case 1:  # Right vertical
                            startx, termix = id_turn * gap, sizY - id_turn * gap
                            lstx, lsty = (sizX - id_turn * gap, wid / 2 + startx + (termix - startx) * tapratio)
                            lsty -= wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx - wid / 2, lsty), (sizX + Lext, lsty)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(sizX + Lext - PORT_LENGTH, lsty), (sizX + Lext, lsty)]
                        case 2:  # Top horizontal
                            startx, termix = sizX - id_turn * gap, id_turn * gap
                            lstx, lsty = (wid / 2 + startx + (termix - startx) * tapratio, sizY - id_turn * gap)
                            lstx += wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty - wid / 2), (lstx, sizY + Lext)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(lstx, sizY + Lext - PORT_LENGTH), (lstx, sizY + Lext)]
                        case 3:  # Left vertical
                            startx = sizY - id_turn * gap
                            termix = id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap)
                            lstx, lsty = (id_turn * gap, -wid / 2 + startx - (startx - termix) * tapratio)
                            lsty += wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx + wid / 2, lsty), (-Lext, lsty)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(-Lext + PORT_LENGTH, lsty), (-Lext, lsty)]
                elif cur_metal == 1 and id_turn == 0:
                    flag_add_tap = True
                    match tid % 4:
                        case 0:  # Bottom horizontal
                            startx = max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0)
                            termix = sizX - id_turn * gap
                            lstx, lsty = (startx + (termix - startx) * tapratio + wid / 2, id_turn * gap)
                            lstx -= wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx, lsty - gap - wid / 2)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lsty -= gap
                            shape_list.append(gdstk.FlexPath([(lstx, lsty + wid / 2), (lstx, -Lext - gap)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(lstx, -Lext - gap + PORT_LENGTH), (lstx, -Lext - gap)]
                        case 1:  # Right vertical
                            startx, termix = id_turn * gap, sizY - id_turn * gap
                            lstx, lsty = (sizX - id_turn * gap, wid / 2 + startx + (termix - startx) * tapratio)
                            lsty -= wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx + gap + wid / 2, lsty)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lstx += gap
                            shape_list.append(gdstk.FlexPath([(lstx + wid / 2, lsty), (sizX + Lext + gap, lsty)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(sizX + Lext + gap - PORT_LENGTH, lsty), (sizX + Lext + gap, lsty)]
                        case 2:  # Top horizontal
                            startx, termix = sizX - id_turn * gap, id_turn * gap
                            lstx, lsty = (wid / 2 + startx + (termix - startx) * tapratio, sizY - id_turn * gap)
                            lstx += wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx, lsty + gap + wid / 2)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lsty += gap
                            shape_list.append(gdstk.FlexPath([(lstx, lsty + wid / 2), (lstx, sizY + Lext + gap)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(lstx, sizY + Lext + gap - PORT_LENGTH), (lstx, sizY + Lext + gap)]
                        case 3:  # Left vertical
                            startx = sizY - id_turn * gap
                            termix = id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap)
                            lstx, lsty = (id_turn * gap, -wid / 2 + startx - (startx - termix) * tapratio)
                            lsty += wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx - gap - wid / 2, lsty)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lstx -= gap
                            shape_list.append(gdstk.FlexPath([(lstx - wid / 2, lsty), (-Lext - gap, lsty)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(-Lext - gap + PORT_LENGTH, lsty), (-Lext - gap, lsty)]
                elif cur_metal == 1 and id_turn == (nseg - 1) // 8:
                    flag_add_tap = True
                    match tid % 4:
                        case 0:  # Bottom horizontal
                            startx = max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0)
                            termix = sizX - id_turn * gap
                            lstx, lsty = (startx + (termix - startx) * tapratio + wid / 2, id_turn * gap)
                            lstx -= wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx, lsty + gap + wid / 2)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lsty += gap
                            shape_list.append(gdstk.FlexPath([(lstx, lsty + wid / 2), (lstx, -Lext)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(lstx, -Lext + PORT_LENGTH), (lstx, -Lext)]
                        case 1:  # Right vertical
                            startx, termix = id_turn * gap, sizY - id_turn * gap
                            lstx, lsty = (sizX - id_turn * gap, wid / 2 + startx + (termix - startx) * tapratio)
                            lsty -= wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx - gap - wid / 2, lsty)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lstx -= gap
                            shape_list.append(gdstk.FlexPath([(lstx - wid / 2, lsty), (sizX + Lext, lsty)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(sizX + Lext - PORT_LENGTH, lsty), (sizX + Lext, lsty)]
                        case 2:  # Top horizontal
                            startx, termix = sizX - id_turn * gap, id_turn * gap
                            lstx, lsty = (wid / 2 + startx + (termix - startx) * tapratio, sizY - id_turn * gap)
                            lstx += wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx, lsty - gap - wid / 2)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lsty -= gap
                            shape_list.append(gdstk.FlexPath([(lstx, lsty - wid / 2), (lstx, sizY + Lext)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(lstx, sizY + Lext - PORT_LENGTH), (lstx, sizY + Lext)]
                        case 3:  # Left vertical
                            startx = sizY - id_turn * gap
                            termix = id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap)
                            lstx, lsty = (id_turn * gap, -wid / 2 + startx - (startx - termix) * tapratio)
                            lsty += wid / 2
                            shape_list.append(gdstk.FlexPath([(lstx, lsty), (lstx + gap + wid / 2, lsty)], wid,
                                                              layer=thick_metals[cur_metal], datatype=0))
                            lstx += gap
                            shape_list.append(gdstk.FlexPath([(lstx + wid / 2, lsty), (-Lext, lsty)], wid,
                                                              layer=gnd_metal, datatype=0))
                            port_loc = [(-Lext + PORT_LENGTH, lsty), (-Lext, lsty)]
                if flag_add_tap:
                    # Create #2 port (TAP)
                    shape_list.append(gdstk.FlexPath(port_loc, wid, layer=PORT_START + 2, datatype=0))
                    shape_list += create_via_array(lstx, lsty, wid, wid, viasize=0.42, viaspace=0.42,
                                                    enclosure=0.1, layer=V_BELOW)
                    shape_list.append(gdstk.rectangle((lstx - wid / 2, lsty - wid / 2),
                                                       (lstx + wid / 2, lsty + wid / 2),
                                                       layer=gnd_metal, datatype=0))
                    if cur_metal == 1:
                        shape_list += create_via_array(lstx, lsty, wid, wid)
                        shape_list.append(gdstk.rectangle((lstx - wid / 2, lsty - wid / 2),
                                                           (lstx + wid / 2, lsty + wid / 2),
                                                           layer=thick_metals[0], datatype=0))
            match tid % 4:
                case 0:  # Bottom horizontal
                    if org_id_turn > 0:
                        shape_list += create_via_array(
                            max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0),
                            org_id_turn * gap, wid, wid)
                    base = max(0, id_turn * 2 - 1) * gap + (gap if id_turn > 0 and cur_metal == 0 else 0)
                    tmp_list = [(base, org_id_turn * gap + wid / 2), (base, id_turn * gap),
                                (sizX + wid / 2 - id_turn * gap, id_turn * gap)]
                case 1:  # Right vertical
                    tmp_list = [(sizX - id_turn * gap, -wid / 2 + id_turn * gap),
                                (sizX - id_turn * gap, sizY + wid / 2 - id_turn * gap)]
                case 2:  # Top horizontal
                    tmp_list = [(-wid / 2 + id_turn * gap, sizY - id_turn * gap),
                                (sizX + wid / 2 - id_turn * gap, sizY - id_turn * gap)]
                case 3:  # Left vertical
                    tmp_list = [(id_turn * gap, sizY + wid / 2 - id_turn * gap),
                                (id_turn * gap, -wid / 2 + id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap))]
                    if org_id_turn > 0:
                        tmp_list.pop()
                        tmp_list += [(id_turn * gap, id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap)),
                                     (org_id_turn * gap + wid / 2,
                                      id_turn * 2 * gap + (gap if cur_metal == 1 else 2 * gap))]
            shape_list.append(gdstk.FlexPath(tmp_list, wid, layer=thick_metals[cur_metal], datatype=0))

    library = gdstk.Library()
    cell = library.new_cell(cell_name)
    cell.add(*shape_list)
    for layer in {*thick_metals, gnd_metal, real_gnd_metal, V_BELOW}:
        _combine_layer(cell, layer)
    return cell
