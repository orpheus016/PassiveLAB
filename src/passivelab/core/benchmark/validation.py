"""``ValidationRunner`` — the L9-L10 interface behind ``evaluate(candidate) -> Score``.

The inverse-design evaluation seam, paired with :class:`~passivelab.core.optimization.optimizer.
Optimizer`: it scores a candidate for the algorithm-developer archetype's "fair benchmark vs
baseline", and closes the analog-designer's loop with a final implementability score.

Invariant: an implementation must characterize the candidate first — never skip straight to a
score (Master PRD §8; "no optimization without characterization"). Concrete benchmark applications
(CCIA, BMS-AFE) are later, out of Phase 1; the notebook's own circuit-level validation (1.7/1.8) is
the near-term backend. See ``core/benchmark/GOAL.md``.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from passivelab.core.types import Candidate, Score


@runtime_checkable
class ValidationRunner(Protocol):
    def evaluate(self, candidate: Candidate) -> Score: ...
