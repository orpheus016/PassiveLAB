"""Reusable T-coil geometry primitives, ported from the golden notebook's tcoil_bias.py
(gdspy) to gdstk. Layer/datatype numbers and defaults are copied verbatim from the notebook
(reference/markdown/TCoil_Dataset_Generator_and_Training.md) so output is directly comparable.
"""
from __future__ import annotations

import math

import gdstk

# IHP SG13G2 layer/datatype numbers, copied from the notebook.
DEFAULT_PIN_DT = 2
THICK_METAL_LIST = [126, 134]  # [Thick Metal 1, Thick Metal 2]
V_THICK = 133  # Via Thick Metal, viasize=0.9um, viaspace=1.06um, enclosure=0.5um
M5_METAL = 67
M4_METAL = 50
V_BELOW = 125  # Via Below Metal, viasize=0.42um, viaspace=0.42um, enclosure=0.42/0.1um
ALL_LAYERS = THICK_METAL_LIST + [V_THICK, M5_METAL, V_BELOW, M4_METAL]
PORT_START = 200
PORT_LENGTH = 4


def create_via_array(midX, midY, sizX, sizY, viasize=0.9, viaspace=1.06, enclosure=0.5,
                      layer=V_THICK):
    """Via array filling a defined rectangle area. Returns a list of gdstk.Polygon."""
    shape_list = []
    num_viaX = int((sizX - 2 * enclosure + viaspace) // (viasize + viaspace))
    num_viaY = int((sizY - 2 * enclosure + viaspace) // (viasize + viaspace))
    startX = midX - (num_viaX * (viasize + viaspace) - viaspace) / 2 + viasize / 2
    startY = midY - (num_viaY * (viasize + viaspace) - viaspace) / 2 + viasize / 2
    for ix in range(num_viaX):
        for iy in range(num_viaY):
            via_centerX = startX + ix * (viasize + viaspace)
            via_centerY = startY + iy * (viasize + viaspace)
            shape_list.append(gdstk.rectangle(
                (via_centerX - viasize / 2, via_centerY - viasize / 2),
                (via_centerX + viasize / 2, via_centerY + viasize / 2),
                layer=layer, datatype=0))
    return shape_list


def create_ground_plane(sizX, sizY, gap, gnd_expansion=30, real_gnd_metal=M4_METAL):
    """Ground plane with a rectangular opening for the T-coil area. Returns a list of
    gdstk.Polygon (gdstk.boolean's return type)."""
    inner = gdstk.rectangle((-gap, -gap), (sizX + gap, sizY + gap))
    outer = gdstk.rectangle((-2 * gap - gnd_expansion, -gap - gnd_expansion),
                             (sizX + gap + gnd_expansion, sizY + gap + gnd_expansion))
    return gdstk.boolean(outer, inner, "not", layer=real_gnd_metal, datatype=0)


def create_octagon_points(midX, midY, siz):
    """8 vertices of a regular octagon centered at (midX, midY), 'diameter' siz, oriented
    with two horizontal sides."""
    start_angle = math.pi / 8
    r = siz / 2 / math.cos(start_angle)
    points = []
    angle_increment = math.pi / 4
    for i in range(8):
        angle = start_angle + i * angle_increment
        x = midX + r * math.cos(angle)
        y = midY + r * math.sin(angle)
        points.append((x, y))
    return points


def create_octagon_pad(midX, midY, siz=50, layer=THICK_METAL_LIST[1]):
    """Regular octagon pad, e.g. for the T-coil's bond pad."""
    points = create_octagon_points(midX, midY, siz)
    return gdstk.Polygon(points, layer=layer, datatype=0)
