# External Tools + Generated Artifacts Inventory

> Deliverable for Phase 1 sub-phase **1.0 — Notebook reverse engineering**, subtask **1.0.2**
> (`docs/PRD/Phase 1 — TCoil Platformization.md` §5). Validation criterion: *each stage's
> inputs/outputs and tools are enumerated.*

**Source:** derived from [`docs/NOTEBOOK_CELL_MAP.md`](NOTEBOOK_CELL_MAP.md) (1.0.1's
deliverable — the per-cell `[ext-tool]`/`[artifact]` tags and its "Cross-cutting findings"
section). No new notebook analysis was needed; this restructures that map into a dedicated,
validated tools+artifacts inventory. Every row below cites the `NOTEBOOK_CELL_MAP.md` cell
number(s) it is drawn from.

**Note on scope:** as with `NOTEBOOK_CELL_MAP.md`, this report lives in-repo
(`docs/TOOLS_AND_ARTIFACTS.md`) rather than the vault's `300 digest/`, since the vault
(`../Second Brain`) is not checked out in this CI environment. The vault's harvest loop copies
it into `300 digest/Project/PassiveLAB/` as an artifact entity once this PR merges.

---

## 1. Per-stage inputs / tools / outputs

The literal validation criterion: every stage's inputs, the tools it invokes, and the outputs
it produces, matching the 8-stage breakdown in `NOTEBOOK_CELL_MAP.md`.

| Stage | Inputs | Tools used | Outputs produced |
|---|---|---|---|
| **0** — Front matter, requirements, environment setup (cells 1–6) | none (environment bootstrap) | IHP SG13G2 PDK (clone + env vars), Python 3.12+, ngspice, openEMS, CUDA 12.8 (8GB GPU) — declared but not yet invoked | Directory scaffold (`GDS/`, `SPData/`, `EMLOG/`, …), a patched `modules/util_simulation_setup.py` (headless GUI-preview disable), pinned pip package list (cell 6) |
| **1** — Introduction: classic T-coil peaking (cell 7) | none (derivation only) | — | T-coil peaking condition equations (`L`, `C_B`, `k`) that parametrize later stages |
| **2** — Parametric design & generator (cells 8–10) | 11-parameter geometry table (cell 8) | **gdspy** (geometry construction), `cairosvg`/`PIL` (preview rendering, used later at cell 64/81) | GDS polygons in-memory (cell 9); `tcoil_bias_test.gds` smoke-test file (cell 10) |
| **3** — EM simulation & batched/distributed data generation (cells 11–16) | GDS (from Stage 2), `SG13G2.xml` foundry stackup | **openEMS** + **CSXCAD** (FDTD solver, cell 11), **Ray** (distributed fan-out, cell 14) | Per-sample `.s3p` Touchstone file + log + PNG (cell 11); many `.gds` files, one per sampled point (cell 13); batch of `.s3p`/log per sample from the cluster run (cell 14); QA preview images displayed (cell 16) |
| **4** — ANN-based surrogate model (cells 17–34) | `.s3p` + geometry corpus from `SPData/` (Stage 3 output) | **PyTorch**, **scikit-rf** (`skrf`) | Normalization stats (cell 23); trained model checkpoint `deeper_mlp_model.pt` + `sparam_min/max.npy`, `geo_min/max.npy` (cell 34); train/val loss + prediction-vs-truth plots (cells 29, 33) |
| **5** — SPICE netlist generation, active+passive co-simulation (cells 35–42) | Predicted `.s3p` (from Stage 4's inference utilities, cell 31) | **ngspice** (invoked via shell wrapper) | Baseline `.cir` netlist, no T-coil (cell 41); T-coil-augmented `.cir` netlist (cell 42) |
| **6** — Algorithm-based inverse design (cells 43–81, ×2 worked examples) | Trained model + normalization arrays (Stage 4 output), circuit-writer functions (Stage 5 output) | **Optuna** (`CmaEsSampler`), **spicelib** (`RawRead`), Python **`multiprocessing.Pool**`, ngspice, gdspy (regeneration) | Optimization progress + best-candidate S-parameter plots (cells 55, 71–72); optimized `.gds` layout (cells 57, 74); true EM+SPICE verification run + comparison plots (S21/S11/S22/group delay, cells 60–62, 77–79); final structure figures (cells 64, 81) |
| **7** — Reference, conclusion, future work (cells 82–84) | none | — | none (narrative only) |

## 2. External tools inventory

| Tool | Role | Used in stage(s) / cell(s) | Notes | Maps to Phase-1 interface (`docs/ARCHITECTURE.md` / PRD §4) |
|---|---|---|---|---|
| **gdspy** | GDSII geometry construction (vias, ground plane, octagon pad, T-coil trace) | Stage 2 (cells 9, 10), regenerated in Stage 6 (cells 57–59, 74–76) | Requires `gdspy.library.use_current_library = False` workaround for a known upstream bug, repeated 6× across the notebook (`NOTEBOOK_CELL_MAP.md` cross-cutting finding #2); candidate for replacement — see sub-phase 1.1 generator investigation | `LayoutGenerator.generate(spec)` (L3) |
| **cairosvg / PIL** | Renders GDS preview images into the final side-by-side structure figures | Stage 2 preview tooling, cells 64, 81 | — | supporting `LayoutGenerator` |
| **openEMS** | FDTD electromagnetic solver, 0–100 GHz / 1001-pt sweep, 3 ports, PEC boundaries | Stage 3, cell 11 (`simulator_openems.py`, standalone script) | Cell 11 is explicitly "save as separate script" — cannot run inline in the notebook | `SimulationBackend.characterize(layout)` (L4–L5) |
| **CSXCAD** | Companion geometry/mesh setup library for openEMS | Stage 3, cell 11 | Imported alongside openEMS | supporting `SimulationBackend` |
| **IHP SG13G2 PDK** (+ `SG13G2.xml` stackup) | Process/stackup definition consumed by the EM solver; requires a one-line manual source patch to run headless | Stage 0 setup (cells 4–5), consumed throughout Stage 3 | `modules/util_simulation_setup.py:312` manual patch (`NOTEBOOK_CELL_MAP.md` cross-cutting finding #3) — should become automated `SimulationBackend` setup | PDK layer (L1/L3, PDK-agnostic invariant #5 in `ARCHITECTURE.md`) |
| **Ray** | Distributes thousands of EM simulations across a cluster (~5,000 samples / 3–4 days on 1024 cores) | Stage 3, cell 14 (`emx_sim.py`, standalone script, cluster-only) | Not runnable inline; referenced only | `DatasetPipeline` distribution layer (L6) |
| **PyTorch** | Defines/trains the `DeeperMLP` surrogate (5-layer MLP) | Stage 4, cells 18, 25–28 | CUDA 12.8 / 8GB GPU declared in Stage 0 requirements (cell 4) | `ModelTrainer` (L7) |
| **scikit-rf (`skrf`)** | Loads/represents S-parameter networks (`rf.Network`) for comparison plots | Stage 4 (cell 18), Stage 6 verification plots (cells 60, 77) | — | supporting `ModelTrainer` / `ValidationRunner` |
| **ngspice** | Circuit simulator for baseline + T-coil-augmented netlists, invoked via shell wrapper | Stage 0 requirement (cell 4), Stage 5 (cell 37), Stage 6 baseline + verification runs (cells 46, 49, 60, 68, 77) | Has no native S-parameter element — netlists wrap `.s3p` as an `xfer` subcircuit (`NOTEBOOK_CELL_MAP.md` cell 39 hack) | circuit-integration side of `Optimizer` (L9) |
| **Optuna (`CmaEsSampler`)** | CMA-ES-driven batched search over the 11-D geometry space | Stage 6, cells 45, 52, 69 | 50 iterations × 16-trial batches per example | `Optimizer.optimize(objective)` (L8) |
| **spicelib (`RawRead`)** | Parses ngspice raw output files | Stage 6, cell 45 | — | supporting `Optimizer` |
| **Python `multiprocessing.Pool`** | Parallel fan-out of per-candidate evaluation (ANN predict → SPICE netlist → ngspice run → metric) | Stage 6, cells 45, 51, 53, 70 | — | `Optimizer` candidate-evaluation worker |

## 3. Generated artifacts inventory

| Artifact | Format | Directory | Produced by (stage/cell) | Consumed by (stage/cell) |
|---|---|---|---|---|
| Per-sample GDS layout | `.gds` | `GDS/` | Stage 2 generator (cell 9), batch-sampled in Stage 3 (cell 13); regenerated for optimized candidates in Stage 6 (cells 57, 74) | Stage 3 EM solver input (cell 11); Stage 6 layout preview/verification (cells 58–60, 75–77) |
| S-parameter response | `.s3p` (Touchstone) | `SPData/` | Stage 3 EM solver (cell 11, batched via cell 14) | Stage 4 dataset load (cell 22); Stage 4 inference utilities predict new `.s3p` (cell 31), consumed by Stage 5 netlist writer (cell 39) and Stage 6 verification (cells 60, 77) |
| EM simulation log + PNG preview | log / `.png` | `EMLOG/`, `PNG/` | Stage 3 (cell 11, batched via cell 14) | Stage 3 visual QA (cell 16) |
| Normalization stats | `.npy` (`sparam_min/max.npy`, `geo_min/max.npy`) | `model_n_normalize/` | Stage 4 (cells 23, 34) | Stage 6 inference setup (cell 47) |
| Trained surrogate model checkpoint | `.pt` (`deeper_mlp_model.pt`) | `model_n_normalize/` | Stage 4 training loop (cells 28, 34) | Stage 6 inference (cells 46, 50, 69) |
| Train/val loss curve, prediction-vs-truth plots | inline (matplotlib) | — (notebook cell output) | Stage 4 (cells 29, 33) | — (visual QA only) |
| SPICE netlist | `.cir` | (working directory, path per `Create_Test_Circuit*`) | Stage 5 (cells 41–42, duplicated for example 2 at cells 66–67) | Stage 6 baseline + per-candidate ngspice runs (cells 49, 51, 60, 68, 70, 77) |
| Optimization progress / best-candidate S-parameter plots | inline (matplotlib) | — | Stage 6 (cells 55, 71–72) | — (visual QA only) |
| True-vs-predicted verification plots (S21, S11/S22, group delay) | inline (matplotlib) | — | Stage 6 (cells 60–62, 77–79) | — (visual QA / equivalence check, feeds sub-phase 1.8) |
| Final structure figure | inline (matplotlib + `cairosvg`/`PIL` composite) | — | Stage 6 (cells 64, 81) | — (report figure) |

---

## Related

- [`docs/NOTEBOOK_CELL_MAP.md`](NOTEBOOK_CELL_MAP.md) — the per-cell source this inventory is derived from.
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — the layered pipeline / stable core APIs each tool maps to.
- [`docs/PRD/Phase 1 — TCoil Platformization.md`](PRD/Phase%201%20—%20TCoil%20Platformization.md) §4–5 — the interface table and sub-phase definitions referenced above.
