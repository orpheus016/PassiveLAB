"""``TCoilSpec`` — the ``PassiveSpec``-conforming T-coil spec (sub-phase 1.2.3).

A pure wrap: ``TCoilSpec`` *is* a ``TCoilParams`` (dataclass inheritance), plus the two members
``passivelab.core.geometry.PassiveSpec`` requires (``passive_type``, ``validate()``). No change to
``TCoilParams`` or its 11 geometry fields — ``generate_tcoil(spec)`` needs zero adaptation, because
a ``TCoilSpec`` instance is already a valid ``TCoilParams`` positionally and by attribute.

``validate()`` delegates to the existing ``rules.validate()`` unmodified — it stays scoped to
parameter-range checks (e.g. ``wid`` in ``[3, 12]``). Design-rule checking (DRC) against a real PDK
deck is a distinct, deferred concern (see the PassiveLAB board's DRC-checking task) — it would
operate on the generated ``Layout``, not the spec, and is not part of this interface.
"""
from __future__ import annotations

from dataclasses import dataclass

from passivelab.geometry.tcoil.generator import TCoilParams
from passivelab.geometry.tcoil.rules import validate as _validate_params


@dataclass
class TCoilSpec(TCoilParams):
    passive_type: str = "tcoil"

    def validate(self) -> None:
        _validate_params(self)
