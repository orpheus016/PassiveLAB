"""Plugin registry for ``SimulationBackend`` classes, keyed by a solver name (sub-phase 1.4.1).

Mirrors ``core/geometry/registry.py``'s ``_SPEC_REGISTRY`` (its ``register_spec``/``get_spec``
pair) rather than its ``_REGISTRY`` (``register``/``get``) -- this registry holds **classes**, not
ready-made instances, because a ``SimulationBackend`` needs per-run construction arguments (solver
config, an output directory) that aren't known at plugin-import time, unlike a ``LayoutGenerator``
(stateless, no-arg constructible). A solver plugin (e.g. the openEMS backend) imports ``core`` and
calls :func:`register` on itself (typically as an import-time side effect in the plugin package's
``__init__.py`` -- see ``characterization/openems/__init__.py``); ``core`` never imports the
plugin. Enforced by ``core/tests/test_no_leakage.py``.

Built now, unlike the geometry registry (deferred in 1.2.1/1.3 until a second real caller existed):
1.4.1 has an explicit, immediate multi-solver requirement, so there's no "designed against a sample
of one" risk to defer against.
"""
from __future__ import annotations

from typing import Type

from passivelab.core.characterization.backend import SimulationBackend
from passivelab.utils.registry import Registry

_REGISTRY: Registry[Type[SimulationBackend]] = Registry("SimulationBackend class")


def register(solver: str, backend_cls: Type[SimulationBackend]) -> None:
    """Register ``backend_cls`` as the ``SimulationBackend`` implementation for ``solver``.

    Raises if ``solver`` is already registered -- a silent overwrite would hide a plugin naming
    collision rather than surface it.
    """
    _REGISTRY.register(solver, backend_cls)


def get(solver: str) -> Type[SimulationBackend]:
    """Look up the ``SimulationBackend`` class registered for ``solver`` -- callers construct it
    themselves with whatever config/output-directory arguments that backend needs."""
    return _REGISTRY.get(solver)
