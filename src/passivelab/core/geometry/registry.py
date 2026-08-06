"""Plugin registry for ``LayoutGenerator``, keyed by ``PassiveSpec.passive_type`` (sub-phase 1.3.1).

This is the seam ``core/geometry/GOAL.md`` and ``docs/CORE_INTERFACE_DESIGN.md`` flagged and
deliberately did not build in 1.2.1/1.2.2: top-level ``generate(spec)`` must find the right
``LayoutGenerator`` (e.g. the T-coil plugin) without ``core/`` ever importing a device package
(``tcoil``) or a geometry kit (``gdstk``) — enforced by ``core/tests/test_no_leakage.py``.

The dependency arrow only ever points one way: a plugin imports ``core`` and calls
:func:`register` on itself (typically as an import-time side effect in the plugin package's
``__init__.py`` — see ``geometry/tcoil/__init__.py``); ``core`` never imports the plugin.
"""
from __future__ import annotations

from passivelab.core.geometry.generator import LayoutGenerator
from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.types import Layout

_REGISTRY: dict[str, LayoutGenerator] = {}


def register(passive_type: str, generator: LayoutGenerator) -> None:
    """Register ``generator`` as the handler for ``passive_type``.

    Raises if ``passive_type`` is already registered — a silent overwrite would hide a plugin
    naming collision rather than surface it.
    """
    if passive_type in _REGISTRY:
        raise ValueError(
            f"passive_type {passive_type!r} is already registered to "
            f"{_REGISTRY[passive_type]!r}"
        )
    _REGISTRY[passive_type] = generator


def get(passive_type: str) -> LayoutGenerator:
    """Look up the ``LayoutGenerator`` registered for ``passive_type``."""
    try:
        return _REGISTRY[passive_type]
    except KeyError:
        raise KeyError(
            f"no LayoutGenerator registered for passive_type {passive_type!r}; "
            f"registered types: {sorted(_REGISTRY)}"
        ) from None


def generate(spec: PassiveSpec) -> Layout:
    """The top-level ``generate(spec)`` dispatcher: resolve a backend by ``spec.passive_type``
    and call its ``generate(spec)``. This is the free function ``core/GOAL.md`` names as deferred
    until a registry exists to back it."""
    return get(spec.passive_type).generate(spec)
