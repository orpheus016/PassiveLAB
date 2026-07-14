"""Tests for the T-coil PassiveSpec/LayoutGenerator plugin wrap (sub-phase 1.2.3).

The load-bearing check is the same-geometry regression: the plugin path must produce byte-for-byte
the same fingerprint as calling ``generate_tcoil()`` directly — proving this is a wrap, not a
rewrite (zero edits to generator.py/rules.py/templates.py).
"""
from __future__ import annotations

import dataclasses

import gdstk
import pytest

from passivelab.core import LayoutGenerator, PassiveSpec
from passivelab.geometry.tcoil.generator import TCoilParams, generate_tcoil
from passivelab.geometry.tcoil.plugin import TCoilLayoutGenerator
from passivelab.geometry.tcoil.spec import TCoilSpec

# Same fingerprint helper as tcoil/tests/test_generator.py (see there for rationale): polygon
# count, bounding box, and every polygon's rounded vertex coordinates.
def _summary(cell: gdstk.Cell) -> tuple:
    polys = cell.get_polygons()
    points = tuple(sorted(
        (p.layer, p.datatype, tuple((round(x, 6), round(y, 6)) for x, y in p.points))
        for p in polys
    ))
    return len(polys), cell.bounding_box(), points


# The same golden notebook smoke-test vector as test_generator.py's BASELINE, expressed as
# TCoilSpec instead of TCoilParams.
BASELINE_FIELDS = dict(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                       tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)
BASELINE_SPEC = TCoilSpec(**BASELINE_FIELDS)
BASELINE_PARAMS = TCoilParams(**BASELINE_FIELDS)


def test_tcoil_spec_satisfies_passive_spec_protocol():
    assert isinstance(BASELINE_SPEC, PassiveSpec)
    assert BASELINE_SPEC.passive_type == "tcoil"


def test_tcoil_generator_satisfies_layout_generator_protocol():
    assert isinstance(TCoilLayoutGenerator(), LayoutGenerator)


def test_tcoil_spec_is_still_a_tcoil_params():
    # the whole point of the inheritance design: no adaptation needed to call generate_tcoil
    assert isinstance(BASELINE_SPEC, TCoilParams)


def test_validate_passes_on_valid_spec():
    BASELINE_SPEC.validate()  # must not raise


def test_validate_raises_on_invalid_spec_same_as_rules():
    bad = dataclasses.replace(BASELINE_SPEC, wid=1)  # below rules.WID_RANGE [3, 12]
    with pytest.raises(ValueError):
        bad.validate()


def test_generate_returns_layout_with_manifest_and_metadata():
    layout = TCoilLayoutGenerator().generate(BASELINE_SPEC)
    assert isinstance(layout.cell, gdstk.Cell)
    assert layout.metadata == {"passive_type": "tcoil"}
    assert layout.parameter_manifest["wid"] == 7
    assert layout.parameter_manifest["nseg"] == 10


def test_plugin_path_produces_identical_geometry_to_direct_call():
    """The load-bearing regression: TCoilLayoutGenerator().generate(spec).cell must fingerprint
    identically to calling generate_tcoil() directly with the same parameters -- proving the wrap
    changes nothing about the generated geometry."""
    via_plugin = TCoilLayoutGenerator().generate(BASELINE_SPEC).cell
    via_direct = generate_tcoil(BASELINE_PARAMS)
    assert _summary(via_plugin) == _summary(via_direct)
