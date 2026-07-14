"""``Optimizer`` — the L8 interface behind ``optimize(objective) -> Candidate``.

Ask-tell shape, matching every mainstream optimizer library (Optuna, Nevergrad, pymoo, BoTorch):
``ask()`` proposes the next spec to try, ``tell()`` reports back the candidate and its score.

Structural typing (Protocol, not a base class to subclass) is deliberate — the **algorithm-
developer archetype** brings their own optimizer and conforms *structurally*, without importing or
inheriting anything from passivelab. See ``core/optimization/GOAL.md``.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.types import Candidate, Score


@runtime_checkable
class Optimizer(Protocol):
    def ask(self) -> PassiveSpec: ...

    def tell(self, candidate: Candidate, score: Score) -> None: ...
