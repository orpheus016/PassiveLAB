# PassiveLAB

Design Platform for Passive Structures in IC — OpenROAD for passives. Turns a declarative
`PassiveSpec` into a generated, characterized, optimized, benchmarked passive device, PDK-agnostic.

**Current milestone**: Phase 1 (v0.0) — reproducing the golden T-coil notebook
(`reference/jupyter/`) through reusable APIs, so the notebook becomes a thin demonstration
frontend that only calls those APIs. See `docs/PRD/Phase 1 — TCoil Platformization.md`.

## Install & test

```bash
pip install -e ".[dev]"
pytest
```

CI (`.github/workflows/ci.yml`) runs the same suite on every push/PR.

## Architecture

Four stable core APIs, each backed by a `typing.Protocol` interface so plugins conform
structurally (no inheritance required):

```
generate(spec)       -> Layout      (L1-L3   geometry)
characterize(layout) -> Metrics     (L4-L7   characterization)
optimize(objective)  -> Candidate   (L8      optimization)
evaluate(candidate)  -> Score        (L9-L10  benchmark)
```

A device (e.g. T-coil) is a **plugin**, not core code: it provides a `PassiveSpec`-conforming
spec and a `LayoutGenerator`-conforming generator, and self-registers into a plugin registry
keyed by `passive_type` when its package is imported (`src/passivelab/geometry/<device>/`). The
core `generate(spec)` dispatcher (`passivelab.core.generate`) resolves the right generator at
runtime purely from `spec.passive_type` — `core/` never imports a device package or a geometry
kit (`gdstk`), enforced by `core/tests/test_no_leakage.py`. See `src/passivelab/core/GOAL.md` and
`src/passivelab/geometry/GOAL.md` for the full contract.

Full docs: `docs/ARCHITECTURE.md`, `docs/VISION.md`, `docs/PRD/`.

## Status (Phase 1)

- **1.0–1.2 done**: notebook reverse-engineered, gdstk backend chosen, core interfaces + T-coil
  plugin (`TCoilSpec`/`TCoilLayoutGenerator`) built and validated against the golden generator.
- **1.3 T-Coil plugin (in progress)**: 1.3.1 added the plugin registry — `generate(spec)` now
  dispatches to `TCoilLayoutGenerator` (or any other registered device) via
  `src/passivelab/core/geometry/registry.py`, with zero `core/` → `tcoil/` coupling. Remaining:
  layer/datatype legality fix (1.3.2), `spec.json` loader/CLI (1.3.3).
- **1.4+**: simulation, dataset, ANN, optimization pipelines — not started.

Plan/board lives in the sibling `../Second Brain` vault; see `CLAUDE.md`.
