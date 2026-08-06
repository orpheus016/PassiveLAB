"""Multi-plugin conformance (sub-phase 1.2.3): the core interfaces generalize beyond a sample of
one device.

Drives the REAL T-coil plugin and a **test-only dummy MoM Cap stub** through the exact same
generic caller code, with no ``isinstance``/type-branching — proving ``PassiveSpec``/
``LayoutGenerator`` are genuinely device-agnostic (Master PRD: "a new passive is a new plugin, not
a core change"), not accidentally shaped around tcoil alone.

The dummy MoM Cap stub below is **test infrastructure only** — fake geometry (a handful of
rectangles), no real MOM-cap generation logic. It is **not** the real Phase 2 MOMCap plugin; that
is tracked as its own future board task (Phase 2, per Master PRD §4.3 "tcoil first, then MOM cap").
It lives here, in test code, precisely so nobody mistakes it for that real deliverable.
"""
from __future__ import annotations

import dataclasses

import gdstk
import pytest

import passivelab.core as core
from passivelab.core import LayoutGenerator, Layout, PassiveSpec
from passivelab.core.geometry.registry import register
from passivelab.geometry.tcoil import TCoilLayoutGenerator, TCoilSpec  # noqa: F401 (self-registers "tcoil")

TCOIL_BASELINE = dict(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                      tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)


@dataclasses.dataclass
class _DummyMomCapSpec:
    """TEST-ONLY stub PassiveSpec. NOT the real Phase 2 MOMCap plugin -- see module docstring."""

    finger_width: float = 1.0
    finger_count: int = 4
    passive_type: str = "momcap_stub"

    def validate(self) -> None:
        if self.finger_count < 1:
            raise ValueError("finger_count must be >= 1")


class _DummyMomCapGenerator:
    """TEST-ONLY stub LayoutGenerator: one rectangle per finger, no real MOM-cap logic."""

    def generate(self, spec: _DummyMomCapSpec) -> Layout:
        lib = gdstk.Library()
        cell = lib.new_cell(f"momcap_stub_{id(spec)}")
        for i in range(spec.finger_count):
            x = i * spec.finger_width * 2
            cell.add(gdstk.rectangle((x, 0), (x + spec.finger_width, 10)))
        return Layout(cell=cell, metadata={"passive_type": spec.passive_type},
                     parameter_manifest=dataclasses.asdict(spec))


# Self-register into the SAME core registry "tcoil" registers into on import above -- this is
# the "registry is not a one-device special case" proof (sub-phase 1.3.1): a second, independent
# PassiveSpec/LayoutGenerator pair dispatches through the identical passivelab.core.generate(spec)
# free function, with no isinstance/type-branching anywhere in the calling code.
register("momcap_stub", _DummyMomCapGenerator())


def generate_and_count_polygons(spec: PassiveSpec, generator: LayoutGenerator) -> int:
    """The generic caller: no knowledge of which device it's driving, no type-branching."""
    spec.validate()
    layout = generator.generate(spec)
    return len(layout.cell.get_polygons())


def test_tcoil_and_dummy_momcap_share_the_same_generic_caller():
    n_tcoil = generate_and_count_polygons(TCoilSpec(**TCOIL_BASELINE), TCoilLayoutGenerator())
    n_momcap = generate_and_count_polygons(_DummyMomCapSpec(finger_count=6),
                                           _DummyMomCapGenerator())

    assert n_tcoil > 0
    assert n_momcap == 6  # one rectangle per finger, real (if trivial) generated geometry


def test_both_devices_conform_structurally_with_no_shared_base_class():
    assert isinstance(TCoilSpec(**TCOIL_BASELINE), PassiveSpec)
    assert isinstance(_DummyMomCapSpec(), PassiveSpec)
    assert isinstance(TCoilLayoutGenerator(), LayoutGenerator)
    assert isinstance(_DummyMomCapGenerator(), LayoutGenerator)
    # independence: the dummy stub does not inherit from anything tcoil-related
    assert not issubclass(_DummyMomCapSpec, TCoilSpec.__mro__[1])  # not a TCoilParams subclass


def test_dummy_momcap_validate_raises_like_a_real_spec_would():
    with pytest.raises(ValueError):
        _DummyMomCapSpec(finger_count=0).validate()


def test_core_generate_dispatches_tcoil_and_dummy_momcap_through_the_same_registry():
    """The 1.3.1 validation criterion: core.generate(spec) resolves T-coil and the dummy MoM Cap
    stub to their own generators purely from spec.passive_type, via the shared plugin registry --
    with no isinstance/type-branching in this calling code, proving the registry generalizes."""
    tcoil_layout = core.generate(TCoilSpec(**TCOIL_BASELINE))
    momcap_layout = core.generate(_DummyMomCapSpec(finger_count=6))

    assert len(tcoil_layout.cell.get_polygons()) > 0
    assert len(momcap_layout.cell.get_polygons()) == 6
