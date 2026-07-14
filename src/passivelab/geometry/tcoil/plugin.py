"""``TCoilLayoutGenerator`` — the ``LayoutGenerator``-conforming T-coil plugin (sub-phase 1.2.3).

Wraps ``generate_tcoil()`` (1.1.2) unmodified: a ``TCoilSpec`` *is* a ``TCoilParams``, so
``generate_tcoil(spec)`` needs no adaptation at all — only the return value is wrapped, in a
``Layout``. This is the plugin boundary: outside this module, callers should drive T-coil through
``TCoilSpec``/``TCoilLayoutGenerator`` (the ``passivelab.core`` interfaces), never by importing
``generate_tcoil``/``TCoilParams`` directly.
"""
from __future__ import annotations

import dataclasses

from passivelab.core.types import Layout
from passivelab.geometry.tcoil.generator import generate_tcoil
from passivelab.geometry.tcoil.spec import TCoilSpec


class TCoilLayoutGenerator:
    """Does not call ``spec.validate()`` internally — callers validate before generating, the
    same convention already established by the archetype journeys (validate then generate)."""

    def generate(self, spec: TCoilSpec) -> Layout:
        cell = generate_tcoil(spec)
        return Layout(
            cell=cell,
            metadata={"passive_type": spec.passive_type},
            parameter_manifest=dataclasses.asdict(spec),
        )
