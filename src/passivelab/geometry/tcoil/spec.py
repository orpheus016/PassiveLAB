"""T-coil parameters and the ``PassiveSpec``-conforming spec wrap (sub-phase 1.2.3, follow-up:
all of a device's parameters live in ``spec.py`` — moved out of ``generator.py`` so that module
stays pure generation logic, per the pattern documented in ``geometry/GOAL.md``).

``TCoilSpec`` is a pure wrap: it *is* a ``TCoilParams`` (dataclass inheritance), plus the two
members ``passivelab.core.geometry.PassiveSpec`` requires (``passive_type``, ``validate()``). No
change to ``TCoilParams`` or its 11 geometry fields — ``generate_tcoil(spec)`` needs zero
adaptation, because a ``TCoilSpec`` instance is already a valid ``TCoilParams`` positionally and by
attribute.

``validate()`` delegates to the existing ``rules.validate()`` unmodified — it stays scoped to
parameter-range checks (e.g. ``wid`` in ``[3, 12]``). Design-rule checking (DRC) against a real PDK
deck is a distinct, deferred concern (see the PassiveLAB board's DRC-checking task) — it would
operate on the generated ``Layout``, not the spec, and is not part of this interface.
"""
from __future__ import annotations

from dataclasses import dataclass

from passivelab.geometry.tcoil.rules import validate as _validate_params


@dataclass
class TCoilParams:
    """The T-coil's 11 named parameters (docs/PRD/Phase 1 -- TCoil Platformization.md sub-phase
    1.3 / the golden notebook's parameter table). `pad_siz` was hardcoded to 50 inside the
    notebook's `CreateTCoilTraceVanilla`; it's promoted to an explicit field here so all 11
    parameters named in the PRD table are genuinely wired, not 10."""

    wid: float
    gap: float
    sizX: float
    sizY: float
    firY: float
    tapseg: int
    nseg: int
    tapratio: float
    endratio: float
    Lext: float = 20
    pad_siz: float = 50
    includepad: bool = False


@dataclass
class TCoilSpec(TCoilParams):
    passive_type: str = "tcoil"

    def validate(self) -> None:
        _validate_params(self)
