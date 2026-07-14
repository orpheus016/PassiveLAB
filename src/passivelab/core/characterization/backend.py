"""``SimulationBackend`` — the L4-L5 interface underlying ``characterize()``.

One backend per solver (electrostatic FastCap, magnetic FastHenry, EM openEMS, ...). Extraction
(mesh / netlists / ports / boundary conditions) folds *into* each backend's ``simulate()`` rather
than a separate L4 interface, because extraction is inherently solver-specific — a universal
``Extractor`` would be a fake abstraction (``docs/CORE_INTERFACE_DESIGN.md``, deferred scope).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from passivelab.core.types import Layout, SimulationResult


@runtime_checkable
class SimulationBackend(Protocol):
    def simulate(self, layout: Layout) -> SimulationResult: ...
