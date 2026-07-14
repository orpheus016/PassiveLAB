"""``PassiveSpec`` — the L1->L2 interface: the canonical input to ``generate()``.

Deliberately near-empty. A passive's real parameters (e.g. the T-coil's 11 named fields) live in
the *plugin's* spec that structurally satisfies this Protocol, not here — the core level carries
no passive-specific fields (Master PRD §11 invariant 1; ``docs/CORE_INTERFACE_DESIGN.md``).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PassiveSpec(Protocol):
    """The canonical spec every generator consumes.

    ``passive_type`` discriminates which plugin handles it (e.g. ``"tcoil"``); ``validate()``
    raises on out-of-range parameters (the plugin defines the ranges, per the golden notebook's
    parameter table — see the tcoil plugin's ``rules.py``).
    """

    passive_type: str

    def validate(self) -> None: ...
