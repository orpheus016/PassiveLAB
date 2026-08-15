"""Tests for the gdspy -> gdstk port of the vendored openEMS GDS reader (sub-phase 1.4.6). Needs
only `gdstk` (a hard PassiveLAB dependency) + `numpy` (declared in the `sim` extra, not core --
hence the ``importorskip`` guard) -- no `gdspy`, no `openEMS`/`CSXCAD`. Regression coverage for
the port itself; the pre-existing "does the backend produce correct S-parameters" question is
still 1.4.1's own open item (`docs/OPENEMS_BACKEND.md`), unrelated to this port.

There's no gdspy install available in this environment to diff old-vs-new output against (no MSVC
toolchain -- the whole reason for this port), so these tests validate the ported reader's own
correctness properties directly (area conservation through fracture, exact count parity on the
paths neither via-merge nor fracture touch) rather than a side-by-side comparison.
"""
from __future__ import annotations

import pathlib
import tempfile

import gdstk
import pytest

pytest.importorskip("numpy")

import passivelab.geometry.tcoil  # noqa: E402 -- self-registers "tcoil"
from passivelab.characterization.openems.ports import merge_layout_for_solver  # noqa: E402
from passivelab.characterization.openems.vendor.modules import util_gds_reader as gds_reader  # noqa: E402
from passivelab.core import generate  # noqa: E402
from passivelab.geometry.tcoil.spec import TCoilSpec  # noqa: E402

_BASELINE_FIELDS = dict(
    wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
    tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True,
)


def _merged_tcoil_cell():
    layout = generate(TCoilSpec(**_BASELINE_FIELDS))
    return merge_layout_for_solver(layout)


class _NoMetals:
    """Minimal ``metals_list`` stand-in: every layer reports "not a via, unknown to the
    stackup" -- exercises ``read_gds()`` without needing the real SG13G2.xml."""

    def getbylayernumber(self, layernum):
        return None


def test_util_gds_reader_imports_without_gdspy():
    # The test module itself already imported util_gds_reader above without error -- this just
    # makes that guarantee explicit and regression-tested, so a future accidental
    # `import gdspy` reintroduction fails loudly here instead of only at solver-run time.
    import sys
    assert "gdspy" not in sys.modules


def test_fracture_preserves_area_on_a_real_self_intersecting_polygon():
    # The T-coil ground plane (M4_METAL, layer 50) is built via gdstk.boolean(outer, inner,
    # "not", ...) in generator.py -- a real polygon-with-a-hole, encoded as one GDSII path with
    # a duplicate vertex (the standard "keyhole" convention), not a synthetic construction. This
    # is exactly the shape read_gds()'s preprocessing step exists to handle.
    merged = _merged_tcoil_cell()
    m4_polys = [p for p in merged.polygons if p.layer == 50]
    assert len(m4_polys) == 1
    ground_plane = m4_polys[0]

    seen = set()
    has_duplicate_vertex = False
    for x, y in ground_plane.points:
        key = f"{x},{y}"
        if key in seen:
            has_duplicate_vertex = True
        seen.add(key)
    assert has_duplicate_vertex  # sanity: this really is the self-intersecting case

    fractured = ground_plane.copy().fracture(max_points=6)

    assert len(fractured) > 1  # fracture actually split it
    assert sum(f.area() for f in fractured) == ground_plane.area()  # lossless decomposition
    for piece in fractured:
        pts = [f"{x},{y}" for x, y in piece.points]
        assert len(set(pts)) == len(pts)  # no duplicate vertices survive fracturing


def test_read_gds_fractures_the_ground_plane_only_when_preprocessing_is_enabled(tmp_path):
    merged = _merged_tcoil_cell()
    gds_path = tmp_path / "merged.gds"
    lib = gdstk.Library()
    lib.add(merged)
    lib.write_gds(str(gds_path))

    no_prep = gds_reader.read_gds(str(gds_path), [50], purposelist=[0], metals_list=_NoMetals(),
                                   preprocess=False)
    prep = gds_reader.read_gds(str(gds_path), [50], purposelist=[0], metals_list=_NoMetals(),
                                preprocess=True)

    assert len(no_prep.polygons) == 1     # raw self-intersecting polygon, untouched
    assert len(prep.polygons) > 1         # preprocessing fractured it


def test_read_gds_matches_direct_polygon_count_on_simple_layers():
    # Control case: layers with no hole (no fracture trigger) and no via merging should read back
    # with exactly the same count as a direct gdstk count -- proving the core per-layer
    # extraction loop (the part rewritten for gdstk's get_polygons()/flatten() API) is correct,
    # independent of the two special-case transforms tested elsewhere in this file.
    merged = _merged_tcoil_cell()
    simple_layers = [67, 126, 134, 201]  # Metal5, TopMetal1, TopMetal2, PAD port marker

    direct_counts = {layer: len([p for p in merged.polygons if p.layer == layer])
                      for layer in simple_layers}
    assert all(count > 0 for count in direct_counts.values())  # sanity: baseline spec has these

    with tempfile.TemporaryDirectory() as tmp:
        gds_path = pathlib.Path(tmp) / "merged.gds"
        lib = gdstk.Library()
        lib.add(merged)
        lib.write_gds(str(gds_path))

        result = gds_reader.read_gds(str(gds_path), simple_layers, purposelist=[0],
                                      metals_list=_NoMetals(), preprocess=True)

    reader_counts = {layer: 0 for layer in simple_layers}
    for poly in result.polygons:
        reader_counts[poly.layernum] += 1

    assert reader_counts == direct_counts


def test_read_gds_merges_via_arrays_when_enabled_and_not_when_disabled(tmp_path):
    class _ViaMetal:
        is_via = True

    class _AllVia:
        def getbylayernumber(self, layernum):
            return _ViaMetal()

    merged = _merged_tcoil_cell()
    via_layer = 125  # V_BELOW -- many individual via squares, per generator.py's create_via_array
    direct_count = len([p for p in merged.polygons if p.layer == via_layer])
    assert direct_count > 1  # sanity: this baseline spec exercises multiple via squares

    gds_path = tmp_path / "merged.gds"
    lib = gdstk.Library()
    lib.add(merged)
    lib.write_gds(str(gds_path))

    merged_result = gds_reader.read_gds(str(gds_path), [via_layer], purposelist=[0],
                                         metals_list=_AllVia(), preprocess=False,
                                         merge_polygon_size=1.5)
    unmerged_result = gds_reader.read_gds(str(gds_path), [via_layer], purposelist=[0],
                                           metals_list=_AllVia(), preprocess=False,
                                           merge_polygon_size=0)

    assert len(merged_result.polygons) < direct_count      # via-array merging ran
    assert len(unmerged_result.polygons) == direct_count   # merge_polygon_size=0 disables it
