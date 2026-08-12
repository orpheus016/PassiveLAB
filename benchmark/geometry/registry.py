"""Benchmark-case registry, keyed by ``passive_type`` (sub-phase 1.3.3).

Mirrors ``passivelab.core.geometry.registry``'s plugin-registry pattern one level down, in
benchmark-only tooling: each device's own ``benchmark/geometry/<device>/cases.py`` self-registers
its benchmark vectors here on import (see ``geometry/tcoil/cases.py``), so
``benchmark/geometry/tests/test_layout_validity_and_performance.py`` can iterate every device's
cases generically -- adding MoM Cap or another passive later means adding a `cases.py`, not
touching the shared test.

Deliberately separate from ``core``'s registry: benchmark cases aren't part of the platform
contract, just dev-tooling fixtures. Built on ``passivelab.utils.registry.Registry`` (refactor
pass, 1.3.6) -- previously a hand-rolled dict with the same register/get-all shape as
``core.geometry.registry``, which is exactly the duplication that module now exists to avoid.
"""
from __future__ import annotations

from typing import NamedTuple

from passivelab.core import PassiveSpec
from passivelab.utils.registry import Registry


class BenchmarkCase(NamedTuple):
    id: str
    spec: PassiveSpec


_CASES: Registry[list[BenchmarkCase]] = Registry("benchmark cases")


def register_cases(passive_type: str, cases: list[BenchmarkCase]) -> None:
    _CASES.register(passive_type, list(cases))


def all_cases() -> dict[str, list[BenchmarkCase]]:
    return _CASES.items()
