# Goal: `src/passivelab/core/benchmark/`

The **evaluate** north star (L9-L10):

```
evaluate(candidate: Candidate) -> Score
```

One interface:
- `ValidationRunner` (`validation.py`) — scores a candidate; the inverse-design evaluation seam
  paired with `Optimizer`.

## Who it serves

- **Algorithm developer** — a *fair, reproducible* benchmark score vs baseline methods (the primary
  consumer; Master PRD §3).
- **Analog / IC designer** — closes the loop: a final implementability/quality score on the chosen
  candidate.

## Invariant

`evaluate()` must score a **characterized** candidate — never skip straight from geometry to a score
(Master PRD §8; "no optimization without characterization"). A `ValidationRunner` implementation
characterizes (or consumes already-characterized `Metrics`) before scoring.

## In scope now (1.2.2)

The `ValidationRunner` Protocol + `Score` shape. No scoring logic, no benchmark suites.

## Deferred (not here)

- **The notebook's circuit-level validation** (the near-term concrete backend): sub-phases **1.7 / 1.8**.
- **Concrete benchmark applications** — CCIA, BMS-AFE — are named *applications* on this interface,
  explicitly out of Phase 1 ("Explicit Future Extensions"). 1.2.4's validation report must claim
  only that the T-coil is *expressible* through `ValidationRunner`, not that it passes any benchmark.
- **Algorithm-benchmark tooling** — the common-centroid / interdigitization algorithm test suite and
  the gdspy-vs-gdstk generation-backend harness are algo-dev tooling tracked as board tasks; the
  benchmark ecosystem lives under `benchmark/` (run on demand), not in the fast CI gate.
- **mlflow tracking** — how benchmark runs are logged/compared is part of the mlflow adoption study
  (`docs/adoption/MLFLOW_ADOPTION_STUDY.md`), deferred.

## See also
- `docs/CORE_INTERFACE_DESIGN.md` · `../GOAL.md` · `docs/PRD/00 Master PRD.md` §3.
