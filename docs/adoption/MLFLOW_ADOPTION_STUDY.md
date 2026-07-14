# Adoption study: MLflow for experiment / dataset / model tracking

> **Status: study only — not adopted.** Decision input for a future ADR (tracked as the board task
> *Adopt mlflow for experiment/benchmark tracking*). Written during sub-phase 1.2.2 while the core
> interfaces were fixed, so the mapping is against real interface shapes, not a guess. MLflow is
> **not** a dependency of PassiveLab and must not be added by this study.

## Why it comes up

Two archetypes lean on tracking:
- **Device researcher** — runs parameter sweeps, needs the resulting datasets + characterization
  runs to be logged, queryable, and reproducible.
- **Algorithm developer** — benchmarks optimizers/algorithms, needs runs compared fairly against
  baselines, with params/metrics/artifacts recorded.

MLflow ([mlflow/mlflow](https://github.com/mlflow/mlflow)) offers four components that map onto this:
Tracking (params/metrics/artifacts per run), Model Registry, Projects (reproducible runs), and
Model packaging.

## Where it would touch our interfaces

| MLflow concept | PassiveLab seam | Fit |
|---|---|---|
| Tracking run (params + metrics) | one `characterize()` / `evaluate()` call | good — a run per candidate/spec |
| Artifacts | `Layout` (GDS), `SimulationResult`, `Dataset` files | good — attach GDS/Parquet as artifacts |
| Metrics history | `DatasetPipeline.append(spec, metrics)` | overlaps — both accumulate (spec, metrics) |
| Model Registry | `ModelTrainer.train() -> Model` | overlaps — both version/serve a trained surrogate |
| Projects (repro) | our sweep/benchmark drivers | good — orthogonal, additive |

The overlap is the crux: **`DatasetPipeline` + `ModelTrainer` cover part of what MLflow's Tracking +
Registry already do.**

## Options

1. **Wrap (adapter).** Keep our `DatasetPipeline` / `ModelTrainer` Protocols; add an *optional*
   MLflow-backed implementation (`MlflowDatasetPipeline`, an MLflow logging `ValidationRunner`
   decorator). Core stays MLflow-free; MLflow is an opt-in extra (`pip install passivelab[mlflow]`).
   - Pro: preserves the PDK-/dep-agnostic core and the approved 1.2.1 design; MLflow is one backend
     among possible others; researchers who don't want it pay nothing.
   - Con: a thin duplication (our Protocol *and* MLflow's model).
2. **Replace.** Drop `DatasetPipeline`/`ModelTrainer` as our own abstractions; make MLflow the
   dataset/experiment layer directly.
   - Pro: less code; a mature, familiar tool.
   - Con: heavy hard dependency in the core; contradicts "files/specs over apps" and the approved
     1.2.1 design (our thin Parquet-backed ABC); couples the platform contract to one vendor.
3. **Learn-from, don't adopt.** Keep our thin Parquet + a tiny JSON run-log; borrow MLflow's *ideas*
   (run = params+metrics+artifacts) without the dependency.
   - Pro: lightest; matches "zero-hassle setup, one library."
   - Con: reinvents a slice of MLflow; no ready-made UI.

## Recommendation (for the ADR to decide)

Lean **Option 1 (wrap, optional extra)**: it keeps the core interfaces authoritative and
dependency-free (respecting 1.2.1) while giving researchers/algo-devs real MLflow tracking when they
opt in. Revisit vs Option 3 once 1.5/1.6 show how heavy the real dataset/training actually is.

## Open questions for the ADR

- Does MLflow's storage model fit a **sweep of thousands of EM sims** (the golden dataset was ~5,000
  samples) without becoming the bottleneck it's meant to observe?
- Is the Model Registry worth it for a single 5-layer MLP, or overkill until multi-model?
- Reproducibility: MLflow Projects vs our existing CI + Git provenance (issue→PR→harvest→artifact).

## References
- Interfaces this maps onto: `src/passivelab/core/characterization/` (`dataset.py`, `surrogate.py`),
  `src/passivelab/core/benchmark/validation.py`.
- `docs/CORE_INTERFACE_DESIGN.md`; sub-phase board tasks 1.5 (dataset) / 1.6 (ANN).
