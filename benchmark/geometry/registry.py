"""Benchmark-case registry, keyed by ``passive_type`` (sub-phase 1.3.3).

Mirrors ``passivelab.core.geometry.registry``'s plugin-registry pattern one level down, in
benchmark-only tooling: each device's own ``benchmark/geometry/<device>/cases.py`` self-registers
its benchmark vectors here on import (see ``geometry/tcoil/cases.py``), so
``benchmark/geometry/tests/test_layout_validity_and_performance.py`` can iterate every device's
cases generically -- adding MoM Cap or another passive later means adding a `cases.py`, not
touching the shared test.

Deliberately separate from ``core``'s registry: benchmark cases aren't part of the platform
contract, just dev-tooling fixtures.
"""
from __future__ import annotations

from typing import NamedTuple

from passivelab.core import PassiveSpec


class BenchmarkCase(NamedTuple):
    id: str
    spec: PassiveSpec


_CASES: dict[str, list[BenchmarkCase]] = {}


def register_cases(passive_type: str, cases: list[BenchmarkCase]) -> None:
    if passive_type in _CASES:
        raise ValueError(f"passive_type {passive_type!r} already has registered benchmark cases")
    _CASES[passive_type] = list(cases)


def all_cases() -> dict[str, list[BenchmarkCase]]:
    return dict(_CASES)
