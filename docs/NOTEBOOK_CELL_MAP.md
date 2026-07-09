# Notebook Cell → Workflow Stage Map

> Deliverable for Phase 1 sub-phase **1.0 — Notebook reverse engineering**
> (`docs/PRD/Phase 1 — TCoil Platformization.md` §5). Validation criterion: *every cell
> categorized.*

**Source:** `reference/jupyter/TCoil_Dataset_Generator_and_Training (1).ipynb` — 84 cells
(45 markdown, 39 code — see breakdown below), notebook version described in
`reference/markdown/TCoil_Dataset_Generator_and_Training.md`.

**Note on method:** the notebook file is ~5MB (each of its ~27 inline plot outputs is a
single very long base64 line), which exceeds this environment's file-read limits even with
line offsets. Cell boundaries, source snippets, and comments below were extracted with
targeted content search (`cell_type`, `source`, and keyword matches) directly against the
`.ipynb` JSON rather than a full read, then cross-checked against the parsed
`reference/markdown/` companion. Line numbers refer to the `.ipynb` file itself.

**Note on scope:** CLAUDE.md points PKOS state at the sibling `../Second Brain` vault. That
vault is not checked out in this CI environment, so this report lives in-repo
(`docs/NOTEBOOK_CELL_MAP.md`) instead of `300 digest/`. If a `DOC-`-style ID is needed for
the vault's claims pipeline, this file can be copied/linked there by whoever has vault
access.

**Tag legend:** `[ext-tool]` external dependency · `[artifact]` file(s) the cell
reads/produces · `[reusable]` maps to a Phase-1 core interface (PRD §4) · `[hack]`
notebook-specific workaround that platformization must not carry over as-is.

Total: 84 cells across 8 stages (0 preamble, 1–6 the notebook's own overview list, 7 wrap-up).

---

## Stage 0 — Front matter, requirements, environment setup (cells 1–6)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 1 | md | 4 | Title, authors/affiliation, SPDX header | |
| 2 | md | 22 | Introduction: motivation for AI-driven passive-active T-coil co-design | |
| 3 | md | 37 | Notebook Overview: the 6-stage workflow list + workflow diagram image; "Special Hint" that some cells must be copied into standalone scripts | `[hack]` (declares the copy-to-script pattern used in cells 9, 11, 14) |
| 4 | md | 63 | Requirements: IHP SG13G2 PDK, Python 3.12+, ngspice, openEMS, CUDA 12.8/8GB GPU | `[ext-tool]` PDK, ngspice, openEMS, CUDA |
| 5 | md | 78 | Environment Setup: PDK clone/env-var instructions, directory scaffolding (`GDS`, `SPData`, `EMLOG`, …), a required one-line source patch in `modules/util_simulation_setup.py` to disable a GUI preview | `[hack]` manual PDK source patch required to run headless |
| 6 | md | 136 | Full pinned pip package list (environment reproducibility table) | `[artifact]` env spec |

## Stage 1 — Introduction: classic T-coil peaking (cell 7)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 7 | md | 212 | CML wireline driver topology background; derives the T-coil peaking condition (`L`, `C_B`, `k` equations) that motivates the whole design flow | |

## Stage 2 — Parametric design & generator for the T-coil structure (cells 8–10)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 8 | md | 240 | T-coil geometry design narrative + the 11-parameter table (`pad_siz`, `Lext`, `sizX`, `sizY`, `wid`, `gap`, `total_seg`, `tap_segid`, `tap_ratio`, `end_ratio`, `ratio_firY`) | |
| 9 | code | 272 | `tcoil_bias.py` (meant to be saved as a standalone file): `CreateViaArray`, `CombineLayer`, `CreateGroundPlane`, `CreateOctagonPoints`, `CreateOctagonPad`, `CreateTCoilTraceVanilla` — the full GDSII geometry generator | `[ext-tool]` gdspy · `[artifact]` produces GDS polygons · `[reusable]` → `LayoutGenerator.generate(spec)` (PRD §4) · `[hack]` notebook execution is for testing only, real use is via the saved script |
| 10 | code | 573 | In-notebook smoke test of the generator: builds one cell, `LayoutViewer` preview, `write_gds('tcoil_bias_test.gds')` | `[artifact]` `tcoil_bias_test.gds` · `[hack]` `gdspy.library.use_current_library = False` workaround for a known gdspy bug (upstream issue linked in comment), required before every new `GdsLibrary` or a kernel restart is needed |

## Stage 3 — EM simulation & batched/distributed massive data generation (cells 11–16)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 11 | code | 605 | `simulator_openems.py` (standalone script, not run in-notebook): CLI-arg driven single-sample FDTD run — reads GDS + `SG13G2.xml` stackup, sets up 3 ports, 0–100 GHz / 1001-pt sweep, PEC boundaries, writes an `.s3p` Touchstone file | `[ext-tool]` openEMS, CSXCAD · `[artifact]` reads GDS/XML, writes `.s3p` + PNG/log · `[reusable]` → `SimulationBackend.characterize(layout)` |
| 12 | md | 767 | "Massive Data Generation" + "Distributed Simulation Instruction" section intro (Ray-based distribution rationale) | |
| 13 | code | 793 | In-notebook batch driver: samples the 11-D parameter space, threads calls into `tcoil_bias` to emit one GDS per sample (`one_sample`, loop over `end_num`) | `[artifact]` writes many `.gds` files · `[reusable]` parameter-sampling logic feeds `DatasetPipeline` |
| 14 | code | 875 | `emx_sim.py` (standalone script, explicitly *not* to be run in the notebook): Ray-parallel driver (`emx_task`) that shells out to `simulator_openems.py` per sample; noted to take ~3–4 days for 5,000 samples on a 1024-core cluster | `[ext-tool]` Ray · `[artifact]` `.s3p`/log per sample · `[hack]` external-cluster-only execution, referenced but not runnable inline |
| 15 | md | 912 | Short transition into dataset visual QA | |
| 16 | code | 920 | Displays a handful of generated preview images (`IPython.display.Image`) for sanity-checking the batch | `[artifact]` reads generated PNGs |

## Stage 4 — ANN-based surrogate model (cells 17–34)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 17 | md | 992 | "ANN Design and Training for EM Prediction" section header | |
| 18 | code | 1006 | Imports: `skrf`, `torch`, `torch.nn`/`optim`, `Dataset`/`DataLoader`, `ast` | `[ext-tool]` PyTorch, scikit-rf |
| 19 | code | 1025 | Device selection (CUDA if available) + dataset path setup | |
| 20 | code | 1045 | Resolves sample count / file listing ahead of the load loop | |
| 21 | code | 1074 | Utility defs: `load_geometry`, `load_sparameters`, `normalize_array_columnwise` | `[reusable]` → `DatasetPipeline` |
| 22 | code | 1142 | Loop over all `n_data` samples reading `SPData/{i}.s3p` (+ geometry) into raw arrays | `[artifact]` reads `.s3p` corpus |
| 23 | code | 1181 | Normalizes the raw geometry/S-parameter arrays (calls `normalize_array_columnwise`) | `[artifact]` produces the normalization stats later saved in cell 34 |
| 24 | code | 1204 | `NumpyMultiTargetDataset(Dataset)` + `get_dataloaders(...)` (train/val/test split + `DataLoader`s) | `[reusable]` → `DatasetPipeline` |
| 25 | code | 1248 | `DeeperMLP(nn.Module)` — the 5-layer MLP surrogate architecture | `[reusable]` → `ModelTrainer` model definition |
| 26 | code | 1305 | Hyperparameters (`NUM_EPOCHS = 2000`, etc.), model instantiated and moved to device | |
| 27 | code | 1320 | Loss (`L1Loss`/MAE) and optimizer (`AdamW`) definitions | |
| 28 | code | 1342 | **Training loop** (`for epoch in range(NUM_EPOCHS)`) — source is short but the cell's stored per-epoch `print` output (up to 2000 lines) accounts for most of this cell's size in the file | `[reusable]` → `ModelTrainer.train()` |
| 29 | code | 3403 | Plots train/val MAE loss curves (log scale) | `[artifact]` inline plot |
| 30 | code | 3433 | Evaluates on the held-out test set, reports final test MAE (golden ≈ 0.045 per PRD) | `[reusable]` → `ModelTrainer` validation metric |
| 31 | code | 3470 | Inference/prediction utilities: `run_inference`, `GenerateBatchedPredictedRawS3P`, `GenerateSinglePredictedRawS3P`, `ProcessRawS3P`, `GetPredictedNetwork` | `[reusable]` these become the trained surrogate's public predict API, reused again in Stage 6 |
| 32 | code | 3571 | Picks a test sample id and generates its predicted network | |
| 33 | code | 3593 | Visualizes predicted vs. ground-truth S-parameters for that one sample (`rf.Network` from the true `.s3p`) | `[artifact]` inline plot |
| 34 | code | 3629 | Persists the trained model (`torch.save(..., 'model_n_normalize/deeper_mlp_model.pt')`) and normalization arrays | `[artifact]` `deeper_mlp_model.pt`, `sparam_min/max.npy`, `geo_min/max.npy` — consumed again in Stage 6 |

## Stage 5 — SPICE netlist generation, active+passive co-simulation (cells 35–42)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 35 | md | 3650 | "Structure of the Tested Structure" — names the example geometry used from here on | |
| 36 | md | 3668 | Transition into SPICE co-simulation approach | |
| 37 | md | 3680 | "SPICE Netlist Generation" + "Running Instructions" (`ngspice $1` wrapper script) | `[ext-tool]` ngspice |
| 38 | code | 3696 | `Write_Libs(fi)` — netlist library/include header writer | `[reusable]` |
| 39 | code | 3712 | `Write_SPfile_Subckt(fi, s3p_filename, subckt_name)` — wraps a predicted `.s3p` as an ngspice subcircuit; per PRD, ngspice has no native S-parameter element so this is the `xfer`-based workaround | `[hack]` S3P→SPICE transcription is a modeling workaround, not a first-class ngspice feature |
| 40 | code | 3747 | Small netlist-writer helpers: `Write_Port_Definitions`, `Write_Connections`, `WriteLine`, `Write_ExportSimSP`, `Write_DCVoltage`, `Write_mDCCurrent` | `[reusable]` |
| 41 | code | 3783 | `Create_Test_Circuit_Original(...)` — builds the **baseline** circuit (no T-coil) for comparison | `[artifact]` `.cir` file |
| 42 | code | 3857 | `Create_Test_Circuit(indi, indo, raw_file, cir_name)` — builds the T-coil-augmented circuit (active CML + predicted passive network) | `[artifact]` `.cir` file · `[reusable]` → circuit-integration piece feeding the Stage 6 optimizer's objective |

## Stage 6 — Algorithm-based inverse design (cells 43–81)

Two worked examples, each: imports → baseline (no-T-coil) ngspice run → performance-metric
functions → CMA-ES-driven batched search (via Optuna's `CmaEsSampler`, 50 iterations ×
16-trial batches, `multiprocessing.Pool` fan-out per batch) → results parsing/plots →
regenerate optimized GDS layout → **true EM+SPICE verification** of the optimized design
(not just the ANN-predicted response) → comparison plots (S21, S11/S22, group delay) →
structure image figure.

### Example 1 (cells 43–64)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 43 | md | 3941 | Transition into "Inverse Design" | |
| 44 | md | 3958 | "Inverse Design Example 1" header | |
| 45 | code | 3970 | Imports: `skrf`, `spicelib.RawRead`, `torch`, `optuna`, `multiprocessing.Pool` | `[ext-tool]` Optuna, spicelib |
| 46 | code | 3994 | `ngspice_prefix` shell wrapper var; loads trained model | `[hack]` shells out to ngspice via `os.system`/subprocess prefix string |
| 47 | code | 4010 | Loads saved normalization arrays (`sparam_min/max.npy`, `geo_min/max.npy`) from Stage 4 cell 34 | `[artifact]` consumes Stage 4 outputs |
| 48 | code | 4035 | `PerfCalcS21`, `PerfCalcRef` — performance metrics (GBW, peaking, reflection) used by the objective | `[reusable]` → `Optimizer` objective terms (PRD: `−GBW/GHz + 10·Peaking_max/dB`) |
| 49 | code | 4060 | Runs the **baseline** (no T-coil) circuit through ngspice for reference `s21_org` | `[ext-tool]` ngspice (banner captured in cell output) |
| 50 | code | 4120 | Re-defines predictor utilities (`run_inference`, `Generate*PredictedRawS3P`, `ProcessRawS3P`, `GetPredictedNetwork`) plus `CheckValidity` (11-param constraint check), `GenerateBatchCir`, `GetOneCir` | `[reusable]` geometry validity check → `PassiveSpec` constraint validation |
| 51 | code | 4289 | `one_sample`/`wrap_one_sample` — per-candidate worker (ANN predict → SPICE netlist → ngspice run → metric) for `multiprocessing.Pool` | `[reusable]` → `Optimizer` candidate-evaluation worker |
| 52 | code | 4317 | `batched_objective(params)`; creates the Optuna study with `CmaEsSampler()`; starts outer `for i in range(50)` loop | `[reusable]` → `Optimizer.optimize(objective)` |
| 53 | code | 4360 | **Main optimization loop body**: batches of 16 trials suggested, evaluated in parallel, told back to the study — large cell due to per-iteration logging | `[reusable]` core of `Optimizer` |
| 54 | code | 4750 | Parses the run's logged progress into a `current_value` series | |
| 55 | code | 4789 | Plots best-candidate predicted S21/S11/S22 | `[artifact]` inline plot |
| 56 | code | 4855 | Extracts best geometry from `study.best_trial` | |
| 57 | code | 4877 | Regenerates the optimized geometry via `tcoil_bias`/gdspy | `[reusable]` reuses Stage 2 generator |
| 58 | code | 4895 | Builds/previews the regenerated layout (`LayoutViewer`) | `[hack]` repeats the `use_current_library` gdspy workaround |
| 59 | code | 4925 | Second layout build/preview (input/output sub-structures) | `[hack]` same gdspy workaround |
| 60 | code | 4955 | **True verification**: runs the *real* EM+ngspice simulation of the optimized design (not the ANN surrogate) and plots S21 comparison (True/Predicted/Original) | `[reusable]` → `ValidationRunner.evaluate(candidate)` |
| 61 | code | 5074 | S11/S22 comparison plot | `[artifact]` inline plot |
| 62 | code | 5115 | Group-delay comparison plot | `[artifact]` inline plot |
| 63 | md | 5145 | Transition into final layout figure | |
| 64 | code | 5155 | Final side-by-side input/output structure image figure (`cairosvg`, `PIL`, `matplotlib.figimage`) | `[artifact]` inline figure |

### Example 2 (cells 65–81)

Structurally identical to Example 1, re-run for a second target structure — the same code
is duplicated rather than parametrized into a function.

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 65 | md | 5206 | "Inverse Design Example 2" header | |
| 66 | code | 5218 | Imports + `Create_Test_Circuit_Original` for example 2 | |
| 67 | code | 5283 | `Create_Test_Circuit` for example 2 | `[hack]` duplicated from cell 42 rather than reused |
| 68 | code | 5358 | Baseline ngspice run → `s21_org` for example 2 | `[ext-tool]` ngspice |
| 69 | code | 5418 | Performance-metric functions + predictor/validity/objective setup (condensed vs. Example 1's split) | |
| 70 | code | 5461 | **Main optimization loop** (mirrors cell 53) | `[hack]` near-duplicate of cell 53 |
| 71 | code | 5909 | Best-candidate predicted S21/S11/S22 plot | `[artifact]` inline plot |
| 72 | code | 5969 | Optimization progress plot | `[artifact]` inline plot |
| 73 | code | 6008 | Extracts best geometry | |
| 74 | code | 6030 | Regenerates optimized geometry via `tcoil_bias`/gdspy | `[hack]` gdspy workaround repeated |
| 75 | code | 6048 | Layout build/preview 1 | `[hack]` gdspy workaround repeated |
| 76 | code | 6078 | Layout build/preview 2 | `[hack]` gdspy workaround repeated |
| 77 | code | 6108 | True EM+ngspice verification run + S21 comparison plot | `[reusable]` → `ValidationRunner` |
| 78 | code | 6220 | S11/S22 comparison plot | `[artifact]` inline plot |
| 79 | code | 6261 | Group-delay comparison plot | `[artifact]` inline plot |
| 80 | md | 6291 | Transition into final layout figure | |
| 81 | code | 6301 | Final structure image figure for example 2 | `[artifact]` inline figure |

## Stage 7 — Reference, conclusion, future work (cells 82–84)

| # | Type | Line | Summary | Tags |
|---|---|---|---|---|
| 82 | md | 6347 | "Reference" — citation(s) for the T-coil peaking derivation | |
| 83 | md | 6359 | "Conclusion" | |
| 84 | md | 6369 | "To Do / Possible Future Improvements" (last cell, end of file) | |

---

## Cross-cutting findings for later sub-phases

**External tools identified:** gdspy (+`cairosvg`, `PIL` for preview rendering), openEMS /
CSXCAD, the IHP SG13G2 PDK + its `SG13G2.xml` stackup, Ray, ngspice (invoked via shell,
parsed with `spicelib.RawRead`), PyTorch, scikit-rf (`skrf`), Optuna's `CmaEsSampler`
(CMA-ES), Python `multiprocessing.Pool`.

**Generated artifacts:** per-sample `.gds`, `.s3p`/Touchstone files, EM logs and PNG
previews (under `GDS/`, `SPData/`, `EMLOG/`, `PNG/`), the trained model checkpoint
(`deeper_mlp_model.pt`) and its normalization arrays (`*.npy`), generated `.cir` SPICE
netlists, and inline optimization-progress / S-parameter comparison plots.

**Reusable components (candidates for the Phase-1 interfaces in PRD §4):**
`tcoil_bias.py`'s generator functions → `LayoutGenerator`; `simulator_openems.py` →
`SimulationBackend`; the data-loading/normalization/`Dataset`/`DataLoader` code →
`DatasetPipeline`; `DeeperMLP` + its training loop → `ModelTrainer`; the SPICE
netlist-writer functions → the circuit-integration side of `Optimizer`; the Optuna
`CmaEsSampler` loop + `PerfCalc*` objective → `Optimizer`; the "true EM+SPICE verification"
cells (60, 77) → `ValidationRunner`.

**Notebook-specific hacks to not carry over as-is:**
1. Three cells (9, 11, 14) are annotated "save as a separate script" and cannot run inside
   the notebook at all (distributed/cluster or non-interactive requirements) — the platform
   should make these first-class callable functions, not copy/paste instructions.
2. `gdspy.library.use_current_library = False` is repeated **6 times** across the notebook
   as a workaround for a known upstream gdspy bug; a platform `LayoutGenerator` should
   encapsulate this once, not rely on callers remembering it.
3. A one-line manual source patch to the vendored PDK module
   (`modules/util_simulation_setup.py:312`) is required before simulations can run headless
   — this needs to become a documented/automated part of `SimulationBackend` setup, not a
   manual step.
4. Hardcoded local paths (`data_path`, `sim_path`) require per-user editing.
5. Inverse Design "Example 1" and "Example 2" (37 cells combined) duplicate almost the
   entire optimization pipeline with only the target structure changed — no shared function
   or parametrization. This is the clearest signal for why `Optimizer`/`ValidationRunner`
   need to be extracted as reusable APIs (sub-phases 1.2/1.7/1.8) rather than copy-pasted
   per design point.
6. Several cells contain commented-out dead plotting code (e.g. lines 5061–5062, 6207–6208).
