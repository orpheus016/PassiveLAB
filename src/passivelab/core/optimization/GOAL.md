# Goal: `src/passivelab/core/optimization/`

The **optimize** north star (L8):

```
optimize(objective: Objective) -> Candidate
```

One interface:
- `Optimizer` (`optimizer.py`) — **ask-tell**: `ask() -> PassiveSpec`, `tell(candidate, score) -> None`.
  This shape matches every mainstream library (Optuna, Nevergrad, pymoo, BoTorch), so adopting one
  as a backend later is a thin adapter, not a redesign.

## Who it serves

- **Analog / IC designer** — inverse design: drive a spec toward an `Objective`
  (`target_value` / `max_area` / `min_voltage_margin`).
- **Algorithm developer** — the primary reason this is a **Protocol, not an ABC**: bring your own
  optimizer and it conforms *structurally*, importing/subclassing nothing from `passivelab`
  (`tests/test_archetypes.py::test_algo_developer_benchmark_journey` proves a base-class-free
  optimizer plugs in).

## Invariant

The optimizer only ever receives characterized `Metrics` (via `Candidate`) — it cannot reach around
characterization to score a raw layout (dependency rule; Master PRD §8).

## In scope now (1.2.2)

The `Optimizer` Protocol + `Objective`/`Candidate`/`Score` shapes. No search logic.

## Deferred (not here)

- **A concrete optimizer** reproducing the notebook's CMA-ES inverse design (Optuna `CmaEsSampler`):
  sub-phase **1.7**.
- **The `optimize(objective)` free-function with dispatch** (running the ask-tell loop to a stopping
  criterion over a chosen optimizer) — needs the registry from **1.3**; until then callers drive the
  loop explicitly (as the archetype tests do).
- **End-to-end inverse design** (optimizer + surrogate + circuit): **1.8** (note: inverse design is
  flagged as needed first there).

## See also
- `docs/CORE_INTERFACE_DESIGN.md` · `../GOAL.md` · `docs/NOTEBOOK_ARCHITECTURE_REPORT.md` (Stage 6,
  CMA-ES inverse design).
