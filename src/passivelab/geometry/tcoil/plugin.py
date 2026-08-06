"""``TCoilLayoutGenerator`` — the ``LayoutGenerator``-conforming T-coil plugin (sub-phase 1.2.3).

Wraps ``generate_tcoil()`` (1.1.2) unmodified: a ``TCoilSpec`` *is* a ``TCoilParams``, so
``generate_tcoil(spec)`` needs no adaptation at all — only the return value is wrapped, in a
``Layout``. This is the plugin boundary: outside this module, callers should drive T-coil through
``TCoilSpec``/``TCoilLayoutGenerator`` (the ``passivelab.core`` interfaces), never by importing
``generate_tcoil``/``TCoilParams`` directly.

1.3.2: this is also where ``generate_tcoil()``'s openEMS port markers get separated out via
``split_ports()`` — the plugin boundary is the actual "generated GDS" a platform caller receives,
so it's the one place that must guarantee ``Layout.cell`` is PDK-clean (zero layers foreign to
SG13G2), regardless of what ``generate_tcoil()`` emits internally. The port geometry isn't
discarded — a future 1.4 openEMS ``SimulationBackend`` needs it — so it rides in
``Layout.metadata["ports_cell"]``.
"""
from __future__ import annotations

import dataclasses

from passivelab.core.types import Layout
from passivelab.geometry.tcoil.generator import generate_tcoil, split_ports
from passivelab.geometry.tcoil.spec import TCoilSpec


class TCoilLayoutGenerator:
    """Does not call ``spec.validate()`` internally — callers validate before generating, the
    same convention already established by the archetype journeys (validate then generate)."""

    def generate(self, spec: TCoilSpec) -> Layout:
        cell, ports_cell = split_ports(generate_tcoil(spec))
        return Layout(
            cell=cell,
            metadata={"passive_type": spec.passive_type, "ports_cell": ports_cell},
            parameter_manifest=dataclasses.asdict(spec),
        )
