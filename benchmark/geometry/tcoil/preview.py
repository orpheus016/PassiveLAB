"""Render a gdstk.Cell to PNG with matplotlib, colored per layer -- a lightweight "no KLayout
GUI needed" viewer. Neither gdstk nor the `klayout` PyPI package (UI-stripped) ship inline
rendering; this is the practical alternative (same pattern photonics tooling like gdsfactory
uses for Jupyter/IDE previews).
"""
from __future__ import annotations

import itertools
import pathlib

import gdstk
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]


def render_png(cell: gdstk.Cell, path: str | pathlib.Path, *, title: str | None = None) -> None:
    """Save a top-down PNG of `cell`'s polygons, one color per (layer, datatype)."""
    polys = cell.get_polygons()
    layer_ids = sorted({(p.layer, p.datatype) for p in polys})
    color_of = {lid: _PALETTE[i % len(_PALETTE)] for i, lid in enumerate(layer_ids)}

    fig, ax = plt.subplots(figsize=(8, 8))
    for poly in polys:
        patch = MplPolygon(poly.points, closed=True,
                            facecolor=color_of[(poly.layer, poly.datatype)],
                            edgecolor="none", alpha=0.85)
        ax.add_patch(patch)

    handles = [plt.Line2D([0], [0], marker="s", linestyle="", color=color_of[lid],
                           label=f"layer {lid[0]}/{lid[1]}")
               for lid in layer_ids]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8)

    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
