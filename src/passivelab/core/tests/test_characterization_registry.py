"""Tests for the ``SimulationBackend`` plugin registry (sub-phase 1.4.1).

Solver-agnostic, like the rest of ``core/tests/``: uses a structural stub, never imports a solver
package (``openems``) or a solver kit (``openEMS``/``CSXCAD``) -- that would defeat the point of a
test proving the registry itself is solver-agnostic. Mirrors ``test_registry.py``'s
``register_spec``/``get_spec`` half (the geometry registry's class-registry) one layer up -- this
registry holds classes, not instances (see ``registry.py``'s module docstring for why).
"""
from __future__ import annotations

import pytest

from passivelab.core.characterization.registry import get, register
from passivelab.core.types import Layout, SimulationResult


class _StubBackend:
    def __init__(self, out_dir: str = ""):
        self.out_dir = out_dir

    def simulate(self, layout: Layout) -> SimulationResult:
        return SimulationResult(backend="stub", raw={"out_dir": self.out_dir})


def test_register_then_get_returns_the_same_class():
    register("registry-test-roundtrip", _StubBackend)
    assert get("registry-test-roundtrip") is _StubBackend
    assert get("registry-test-roundtrip")(out_dir="x").simulate(Layout()).raw == {"out_dir": "x"}


def test_register_duplicate_solver_raises():
    register("registry-test-dup", _StubBackend)
    with pytest.raises(ValueError, match="registry-test-dup"):
        register("registry-test-dup", _StubBackend)


def test_get_unknown_solver_raises_with_known_solvers_listed():
    register("registry-test-known", _StubBackend)
    with pytest.raises(KeyError, match="registry-test-known"):
        get("registry-test-unknown-xyz")
