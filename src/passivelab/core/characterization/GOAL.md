# Goal: `src/passivelab/core/characterization/`

The **characterize** north star (L4-L7) — and the fast-surrogate path that keeps optimization cheap:

```
characterize(layout: Layout) -> Metrics
```

Three interfaces:
- `SimulationBackend` (`backend.py`) — one per solver; `simulate(layout) -> SimulationResult`.
  Extraction (mesh / netlists / ports / BCs) folds *into* each backend, not a separate L4 interface
  (it's inherently solver-specific).
- `DatasetPipeline` (`dataset.py`) — accumulates `(spec, metrics)` rows.
- `ModelTrainer` + `Model` (`surrogate.py`) — trains a surrogate that predicts `Metrics` fast.

## Who it serves

- **Device researcher** — sweeps → dataset + characterization results (the primary consumer).
- **Analog / IC designer** & **Algorithm developer** — indirectly: the surrogate is *why*
  `optimize()` is fast. Without `DatasetPipeline` + `ModelTrainer`, every optimizer iteration would
  pay for a slow EM/field solve. This is load-bearing, not optional.

## Invariant

An optimizer only ever sees **characterized** metrics — no optimization without characterization
(Master PRD §8).

## In scope now (1.2.2)

The three Protocols + `SimulationResult`/`Metrics`/`Dataset` shapes. No solver, no training.

## Deferred (not here)

- **Real solvers** — FastCap / FastHenry / openEMS backends: sub-phase **1.4**.
- **Real dataset + ANN** — the Parquet-backed pipeline and the notebook's 5-layer MLP, **including
  ingesting the golden notebook's actual dataset-generation and training code** (not a
  reimplementation): sub-phases **1.5 / 1.6** (see those board tasks — the ingestion requirement is
  recorded there).
- **mlflow adoption** — whether to adopt mlflow for experiment/dataset/model tracking (wrap
  `DatasetPipeline` vs replace it) is studied in `docs/adoption/MLFLOW_ADOPTION_STUDY.md` and
  tracked as an ADR-marked board task; **do not add mlflow as a dependency here**.

## See also
- `docs/CORE_INTERFACE_DESIGN.md` · `../GOAL.md` · `docs/adoption/MLFLOW_ADOPTION_STUDY.md`.
