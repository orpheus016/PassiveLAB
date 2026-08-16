# openEMS `SimulationBackend` (sub-phase 1.4.1)

> Deliverable for Phase 1 sub-phase **1.4.1** (`docs/PRD/Phase 1 — TCoil Platformization.md` §1.4).
> Wraps the golden reference's `simulator_openems.py`
> (`reference/python/TCoil_Dataset_Generator_and_Training.py:534-687`) behind
> `SimulationBackend.simulate(layout) -> SimulationResult`
> (`src/passivelab/core/characterization/backend.py`).

## What this is

`src/passivelab/characterization/openems/` — a solver plugin, living outside `core/` exactly like
`geometry/tcoil/` lives outside `core/geometry/` (enforced by `core/tests/test_no_leakage.py`,
extended in this sub-phase to also guard `openEMS`/`CSXCAD`/`gdspy`/`passivelab.characterization`
leaking into `core/`).

```
core/characterization/
  backend.py     # SimulationBackend Protocol — unchanged, still solver-agnostic
  registry.py    # NEW: solver-dispatch registry (holds classes, not instances — see below)
characterization/openems/
  __init__.py    # self-registers "openems" -> OpenEMSBackend
  plugin.py      # OpenEMSBackend.simulate(layout) -> SimulationResult
  config.py      # OpenEMSConfig + load_openems_config()
  ports.py       # port re-embedding + port-definition derivation (pure gdstk, no openEMS import)
  vendor/        # vendored IHP-Open-PDK openEMS workflow modules + SG13G2.xml (Apache 2.0)
  tests/         # config/ports/registration tests (real CI) + test_plugin.py (importorskip-guarded)
```

## Registry holds classes, not instances

`core/geometry/registry.py` has two registries: an instance registry (`LayoutGenerator`s, no-arg
constructible) and a class registry (`PassiveSpec` classes, constructed per `spec.json`). A
`SimulationBackend` needs per-run arguments a plugin-import-time registry can't supply (solver
config, an output directory), so `core/characterization/registry.py` mirrors the *class* half:
`register("openems", OpenEMSBackend)` / `get("openems") -> Type[SimulationBackend]`; a caller
constructs it themselves: `get("openems")(config, out_dir)`.

## Port re-embedding (why `ports.py` exists)

`geometry/tcoil/generator.py`'s `split_ports()` (sub-phase 1.3.2) strips the openEMS-only port
markers (GDS layers 201-203, `PORT_START=200`) out of the PDK-facing `Layout.cell` into
`Layout.metadata["ports_cell"]`, so the GDS handed to real PDK tools never carries non-PDK layer
numbers. Correct for that purpose — but it means `layout.cell` alone has **zero** port markers.
The vendored `util_simulation_setup.addPorts_to_CSX()` finds ports by scanning whatever the GDS
reader actually saw; if a port's layer is absent from the GDS, no `FDTD.AddLumpedPort()` call
happens for it and no exception is raised — silent zero-excitation, not a loud failure.

`ports.merge_layout_for_solver(layout)` re-unions `layout.cell` + `layout.metadata["ports_cell"]`
into the GDS actually written for the solver. `test_ports.py` regression-tests this against the
real `TCoilLayoutGenerator` (not a stub), and separately proves the merge doesn't mutate the input
`Layout`.

**Port numbering is renumbered contiguously by presence, not by `layernum - PORT_START`.** The tap
port (layer 202) is conditional on the sampled geometry (`generator.py`'s `flag_add_tap`) — not
every T-coil has one. The vendored `all_simulation_ports.get_port_by_number(n)` indexes its
internal list as `self.ports[n-1]`, assuming contiguous portnumbers from 1; if PAD/CIR kept their
"natural" numbers 1/3 with port 2 missing, `get_port_by_number(3)` would read the wrong port or
index out of range. `derive_port_definitions()` numbers whatever's present 1..N in layer order
instead — a standard reduced-port-set measurement, not a change in what's physically probed.

**The port-to-metal convention (`from_layername`/`to_layername` per port layer) is T-coil-specific
and copied verbatim from the golden reference** — generalizing a port/reference-plane/de-embedding
convention across passive types is board task **1.4.2**'s scope, not this one (matches 1.4.1's own
validation bar: "a known T-coil geometry").

**Reference plane / de-embedding (1.4.2, see `docs/PORT_CONVENTION.md`).** The reference plane is
the port box itself (`PORT_LENGTH` = 4 microns from the via), and no feedline/pad de-embedding is
applied — the vendored solver has no calibration/subtraction step. `PortDef` carries this as data
(`reference_plane_offset`, `de_embedded`), and `SimulationResult.raw["port_convention"]` stamps a
top-level summary on every run so a dataset row is self-describing.

## Vendored PDK modules

`vendor/modules/{util_stackup_reader,util_gds_reader,util_utilities,util_simulation_setup,
util_meshlines}.py` + `SG13G2.xml`, copied from a local `IHP-Open-PDK` checkout
(`ihp-sg13g2/libs.tech/openems/openems_ihp_sg13g2/workflow/`, Apache 2.0 — see `vendor/NOTICE`).
Changes from upstream (1.4.1):

1. Intra-package `import util_x` statements converted to relative imports (`from . import util_x`)
   so they work as a proper package instead of relying on `sys.path` manipulation.
2. `util_simulation_setup.runSimulation()` gained an explicit `interactive_preview: bool = False`
   parameter gating the `AppCSXCAD` GUI-preview launch (previously an implicit
   `if 1 in excite_portnumbers:` condition that would block on a GUI window and `sys.exit(1)` on a
   nonzero exit code — fatal for any headless run). The golden notebook worked around the same
   issue with a manual one-line source edit (`if False and 1 in excite_portnumbers:`); this is the
   same effect as an explicit, tested parameter instead of a dead branch.

`runSimulation()` also has an existing hash-based skip-if-unchanged mechanism (SHA-256 of the
written CSX XML vs. a `simulation_model.hash` left from a prior run) — kept, not bypassed, since it
becomes real content-addressed caching given the output-folder design below.

**`util_gds_reader.py` ported from `gdspy` to `gdstk` (1.4.6).** Upstream hard-depended on
`gdspy`, not `gdstk` — reintroducing exactly the install friction (no Windows wheel, unmaintained
upstream) `DEC-adopt-gdstk-as-the-l3-generator-backend-0002` already replaced it for elsewhere,
just confined to the `sim` extra instead of the whole package. Every gdspy call had a confirmed
gdstk equivalent (verified by introspecting the installed `gdstk` package plus existing precedent
already in this repo — `gdstk.read_gds()` in `scripts/sweep.py`, `gdstk.boolean()` in
`geometry/tcoil/generator.py`); the `gds_polygon`/`all_polygons_list` output contract is unchanged,
so `util_meshlines.py` (which only ever consumed those plain classes, never gdspy's API) needed no
changes. `gdspy` is no longer a dependency anywhere in this repo. See
`characterization/openems/tests/test_gds_reader.py` for regression coverage — including a direct
area-conservation check on the T-coil ground plane's `fracture()` call, the one path most at risk
of a subtle port bug (the preprocessing step that splits self-intersecting/hole-encoded polygons).

## Config

`OpenEMSConfig` (`config.py`) mirrors `scripts/sweep.py`'s `SweepSpec`/`load_sweep_spec()` pattern:
flat JSON with a `solver` discriminator, every default matching the golden reference's own
hardcoded constants (0-100 GHz / 1001 points / PEC×6 boundaries / margin=200 /
refined_cellsize=1.0 / cells_per_wavelength=20 / energy_limit=-50 dB / merge_polygon_size=1.5 /
preprocess_gds=True) — see `examples/openems.config.json`. Deliberately **no `gpu` field**: openEMS
has no supported GPU/CUDA path; a future GPU-capable solver would carry its own `gpu` field on its
own config schema (configs are per-solver, not shared).

Kept separate from `SweepSpec` (layout generation), not merged — composing the two is sub-phase
1.5.2's dataset-orchestration job, not this one.

## Output folder — designed for concurrency safety and future webapp browsing

Golden reference: hardcoded `/tmp/ray_cache/{index}_sim`, artifacts scattered across three
unrelated top-level dirs keyed by a bare integer index (`SPData/`, `EMLOG/`, `PNG/`). Redesigned:

```
<out_dir>/<sample_id>/
  <sample_id>.gds          # merged solver-facing GDS (port markers re-embedded)
  <sample_id>.xml           # CSX (per excitation, via the vendored setupSimulation)
  sub-1/, sub-2/, ...       # raw FDTD data per port excitation (vendored get_excitation_path layout)
  <sample_id>.s{n}p          # Touchstone S-parameters (n = number of ports actually present)
  report.json                 # sample_id, solver, config used, port definitions, solver versions,
                               # wall-clock time, success/failure + error, post-processed Metrics
                               # summary (1.4.4) — everything a future webapp or 1.5.2's
                               # DatasetPipeline needs without bespoke parsing. Renamed from
                               # manifest.json (1.4.4) — the only per-sample output file here.
```

`OpenEMSBackend(config, out_dir)` takes `out_dir` at construction (one instance = one output root);
`sample_id` is derived deterministically inside `simulate()` from `layout.parameter_manifest` (a
stable hash), not threaded in as a new argument or a `Layout`/`SimulationBackend` Protocol change.
This gets two properties from one mechanism: concurrent callers processing *different* samples
never collide (each owns its own subfolder — a 1.5.2 Ray-fan-out invariant, unique `sample_id`s),
and re-running the *same* sample naturally reuses its path and gets the vendored hash-based
skip-if-unchanged behavior as real caching across separate runs, not just retries within one.

`SimulationResult.raw` points to the `.s3p`/`report.json` rather than duplicating the full `(n, n,
numfreq)` S-parameter matrix as JSON — the Touchstone file is the canonical artifact (matches how
the golden reference's own dataset loader reads results back off disk), and embedding the full
matrix in every sample's report would bloat it for no reader not already better served by
re-reading the `.s3p` file. `report.json` does carry a much smaller post-processed summary (1.4.4,
see below) — real derived output, not just a pointer.

Other scalability constraints upheld (see `plugin.py`'s module docstring): no `os.chdir()` (every
path is absolute), no mutable instance/live-solver state between `simulate()` calls.

## Live validation (2026-08-15/16)

First real end-to-end run against an actual openEMS/CSXCAD install (not `test_plugin.py` itself —
a throwaway diagnostic script, since three gaps below made the committed path unusable as-is):
baseline spec `examples/tcoil.spec.json`, full 3-port sweep. Result: a real, well-formed 3-port
`.s3p`, checked against real physics rather than just "it didn't crash" — **reciprocity** (S_ij vs
S_ji) within 0.013 max deviation (worst at 100 GHz, the top of the band, where FDTD discretization
error is naturally largest), and **passivity** (max eigenvalue of SᴴS) clean across all 1001
frequency points, max 0.998, zero violations. Total wall-clock ~72 minutes (port 1: 2063.5s, port
2: 615.9s, port 3: 1662.8s) — openEMS itself flagged why: a femtosecond-scale CFL timestep forced
by one small mesh cell (`Smallest timestep... found at position: 2:126;52;27`), not a threading
problem (openEMS auto-benchmarked 1-4 threads and picked 3 as fastest on its own).

Three real gaps found — the first three are now fixed (board task **1.4.3**, see the section
below); the fourth is still open:

- ~~No install-path handling~~ — fixed: `OpenEMSConfig.install_path` (1.4.3).
- ~~`num_cpus` still not wired~~ — fixed: forwarded to `FDTD.Run(numThreads=...)` (1.4.3).
- ~~Runs silently by default~~ — fixed: `verbose`/`dump_statistics` config fields, plus a captured
  `openems_run.log` per excitation (1.4.3).
- The femtosecond-timestep root cause itself (real geometry constraint vs. a mesh-config artifact)
  is unexplored — → board task **1.4.7**.

## Install path, num_cpus, non-silent execution (sub-phase 1.4.3)

`OpenEMSConfig` gained three fields, all JSON-config-driven (`examples/openems.config.json`), not
environment variables:

- **`install_path: str | None`** — the openEMS install directory (contains `CSXCAD_MSVC.dll` etc.).
  `plugin.py`'s `_simulate()` calls `os.add_dll_directory(config.install_path)` before *any*
  deferred import (not just the later `from openEMS import openEMS` — `util_simulation_setup`
  imports `CSXCAD` at its own module level, so the DLL resolution failure actually happens there
  first). `None` (the default) skips the call — non-Windows, or DLLs already resolvable via `PATH`.
  Machine-specific, so it's intentionally **not** set in the checked-in example config; a caller on
  Windows needs to point it at their own install (e.g. `C:\opt\openEMS\openEMS`). On import failure
  with `install_path` unset, the error message now names the field instead of surfacing the raw
  opaque `DLL load failed`.
- **`num_cpus`** now actually reaches the solver: forwarded through `runSimulation()`'s new
  `num_threads` parameter to `FDTD.Run(numThreads=config.num_cpus, ...)`.
- **`verbose: int` (0-3, default 3)** and **`dump_statistics: bool` (default True)** are forwarded
  the same way. `verbose` makes openEMS's compiled core actually print progress; `dump_statistics`
  makes it write `openEMS_run_stats.txt` (time-series: time/timestep/speed/energy) and
  `openEMS_stats.txt` (final summary) directly into the excitation folder.
- **The console text itself is captured**, not just enabled: `FDTD.Run()` is a compiled extension
  writing straight to the process's real stdout/stderr file descriptors, so a Python-level
  `sys.stdout` reassignment wouldn't see it. `plugin.py`'s `_redirect_to_log()` duplicates fds 1/2
  to `<sim_dir>/sub-N/openems_run.log` for the duration of each port's `runSimulation()` call —
  mirroring the golden reference's own `os.system(f"... > {index}.log")` shell redirect, scoped per
  port excitation (this backend runs in-process, one Python process per sample, not one
  subprocess-per-sample like the reference).
- `SimulationResult.raw["logs"]` echoes all three paths per port (`log`/`run_stats`/`stats`), so a
  caller checking "is this simulation working properly or producing wrong results" reads a file
  instead of re-deriving the `sub-N/` folder convention or re-running with verbosity turned on
  after the fact.

**The vendored `runSimulation()`'s "DO NOT SPECIFY COMMAND LINE OPTIONS" warning.** The upstream
comment above `FDTD.Run(excitation_path)` warns against exactly this kind of kwarg-passing. Read as
guarding against arbitrary/ad-hoc CLI flags rather than the narrow, openEMS-documented
`numThreads`/`verbose`/`dump_statistics` kwargs added here — and this backend's caller (`plugin.py`'s
per-port loop) already builds a brand-new `FDTD` instance per excitation via `setupSimulation()`, so
there's no cross-call state for these options to corrupt. Confirmed by a live multi-port smoke run
(below), not dismissed on reasoning alone. See `vendor/NOTICE` for the recorded deviation.

**Live smoke verification (2026-08-16)**: ran end-to-end against the real local openEMS install
(`C:\opt\openEMS\openEMS`) with a deliberately coarse/fast config (`num_cpus=2`, `numfreq=11`,
`cells_per_wavelength=5`, `energy_limit_db=-15` — a mechanism check, not an accuracy run; that's
1.4.7/1.4.8's job) on the baseline T-coil (131k mesh cells, 3 ports). Result: `success=True`,
end-to-end in ~52 seconds. DLL resolved via `install_path` with no manual workaround. All three
ports' `openems_run.log` were non-empty (~17 KB each) and contained
`Multithreaded engine using 2 threads. Utilization: (31;31)` — matching `config.num_cpus=2` exactly.
`openEMS_run_stats.txt`/`openEMS_stats.txt` existed for every port. All three ports' `Run()` calls
completed with no error — directly exercising, and clearing, the vendored warning's
multi-excitation concern.

`write_snp()`'s 1-port code path (indexes `Smatrix[0, index]` for a `(1, numfreq)`-shaped input,
never exercised since T-coil's PAD/CIR ports are unconditional — a minimum of 2 ports always)
remains untested, flagged for whoever adds a genuinely single-port passive later.

## S-parameter post-processing to Metrics (sub-phase 1.4.4)

`characterization/openems/sparams.py` turns the `.s3p` `write_snp()` already writes into a
`core.types.Metrics` — via `skrf.Network`, the same library the golden reference itself uses for
every S3P read (`load_sparameters()`, `GetPredictedNetwork()`, 1.7's ngspice transcription). New
base dependency: `scikit-rf` (pure Python + numpy, no compiled solver — not gated behind `sim`).

- `sparams_to_metrics(s3p_path, port_defs) -> Metrics` reads the file, asserts the port count
  matches `port_defs` (raising `ValueError` on mismatch — "port ordering explicit and asserted, not
  incidental"), and returns the full raw `(numfreq, n, n)` S-matrix plus a **training-target
  vector**: a byte-for-byte replica of the golden reference's `load_sparameters()` decimation
  (`range(0, 1001, 10)` → 101 points, 0-100 GHz at 1 GHz step) and flatten (`s[k].flatten()` →
  `concatenate(real, imag)` per frequency, concatenated across frequencies) — 1818-dim for the
  3-port case, matching the reference exactly.
- **Port-ordering convention (tested, not assumed)**: `skrf.Network(...).s[k]`'s row axis turns out
  to be the *excitation* (source) port and column axis the *response* port for this repo's
  `write_snp()` (vendored, column-grouped-by-source Touchstone writer) + `skrf` reader combination —
  the reverse of what "S_ij = response i / source j" notation alone would suggest. Confirmed
  empirically with asymmetric synthetic S-values (a real reciprocal T-coil's S-matrix is nearly
  symmetric, which would hide a row/column mixup) — see `test_sparams.py`'s convention-regression
  test. **Not "corrected" here**: the golden reference's own `load_sparameters()` consumes `ntwk.s`
  the same un-transposed way, so normalizing it in this repo would make our S-parameters diverge
  from what the notebook itself produces, breaking 1.4.5/1.4.8's bit-for-bit equivalence checks.
- `metrics_summary_for_report(metrics) -> dict` is the lightweight, JSON-serializable subset that
  rides into `report.json` automatically (see `plugin.py`'s `_simulate()`): `s3p_path`,
  `port_numbers`, the convention note, and the small decimated `training_vector`/
  `training_frequency_hz` — deliberately **excluding** the full raw matrix, for the same
  no-duplication reasoning `s3p_path` already gets. `scripts/simulate.py`'s separate, one-level-up
  `report.json` (per CLI invocation) also picks up this summary via `result.raw.get("metrics")`.
- No derived physical quantities (L/Q/R) are computed — the golden reference's own dataset/training
  pipeline never computes any either; the only thing 1.6 trains against is the decimated S-parameter
  vector itself.
- Out of scope: the generic `core.characterize(layout) -> Metrics` entry point from `GOAL.md`
  (single backend exists — same "don't build shared abstraction until a second real example proves
  it's shared" principle applied elsewhere in this codebase, e.g. 1.4.10/1.4.11).

**Live verification (2026-08-16)**: ran end-to-end against the real local openEMS install with a
reduced/fast config (`numfreq=101` — the smallest value that evenly decimates to the golden
reference's own training grid). Result: `report.json` (42.7 KB) is the *only* per-sample output
file — `manifest.json` no longer exists anywhere. Its `metrics` key carries exactly
`port_numbers`/`s3p_path`/`s_parameters_convention`/`training_frequency_hz`/`training_vector`, with
`training_vector` length **1818** and `training_frequency_hz` length **101** — matching the golden
reference's own numbers exactly — and no `s_parameters`/`frequency_hz` (the full matrix stays out).

## `simulate --plot`: full Metrics + interactive S-parameter plot

`scripts/simulate.py`'s `simulate_command(..., plot=True)` (CLI: `passivelab simulate spec.json
solver-config.json --out-dir out --plot`) is deliberately **not** a new command — re-running
`simulate` on an unchanged spec/config is already cheap (the vendored solver's own hash-based
skip-if-unchanged caching), so "post-process what's already there" and "solve, then post-process"
collapse into the same code path here.

- `_write_characterize_output()` reconstructs `PortDef`s from `result.raw["ports"]`, calls
  `sparams_to_metrics()` for the **full** `Metrics` (the complete `(numfreq, n, n)` matrix — not
  `metrics_summary_for_report()`'s lightweight subset already embedded in `simulate`'s own
  `report.json`), and writes two files under
  `<out-dir>/characterize/<passive_type>/<solver>/<sample_id>/`:
  - `report.json` — `sparams.metrics_to_full_json()`: the complete `Metrics`, JSON-serialized
    (complex `s_parameters`/`frequency_hz` split into `{"real": [...], "imag": [...]}`). This *is*
    the on-demand deep-dive artifact (one sample at a time, not the per-dataset-row path 1.5.2 will
    run at scale), so the bloat `metrics_summary_for_report()` deliberately avoids is an accepted
    tradeoff here, not an oversight.
  - `sparams.html` — `characterization/openems/viz.py`'s `plot_sparams_interactive()`: a
    self-contained (plotly embedded inline, opens offline, no server) interactive plot of every
    `S_ij` magnitude (dB) and phase (deg) vs. frequency, zoomable/hoverable. New dependency:
    `plotly`, added to the existing `viz` extra alongside `matplotlib` — deferred-imported (like
    `utils/preview.py`'s matplotlib import) so importing `viz.py` never requires it.
- `simulate_command()`'s own `report.json` gains one field when `--plot` is used:
  `characterize_report_path`, pointing at the file above.

**Bug found and fixed alongside this (live-testing discovery)**: `simulate_command()` used to keep
`out_dir` as whatever string/relative path the caller passed. openEMS's compiled `Run()` leaves the
process's working directory inside the *last* excitation's `sub-N/` folder afterward (confirmed
live — a relative `--out-dir out` run's final `report.json` landed nested at
`out/simulate/.../sub-3/out/simulate/.../report.json` instead of the intended path). Fixed by
resolving `out_dir` to absolute at the top of `simulate_command()`, matching how
`OpenEMSBackend.simulate()` already handles its own `sim_dir` internally. Regression-tested with a
stub backend + `monkeypatch.chdir()` (`tests/test_simulate_cli.py`) since reproducing the real cwd
change needs an actual openEMS install.

**Live verification (2026-08-16)**: ran `simulate --plot` end-to-end against the real local
openEMS install (reduced/fast config). Both `out/characterize/tcoil/openems/<sample_id>/
report.json` and `sparams.html` landed at the correct, non-nested path (confirming the cwd-bug fix
above actually works, not just in the stub regression test). `report.json`: `port_numbers ==
[1, 2, 3]`, `s_parameters` real/imag each `(101, 3, 3)`, `training_vector` length 1818 — the full
matrix this time, unlike `simulate`'s own lightweight summary. `sparams.html`: 4.9 MB
(plotly embedded inline, no CDN/server needed), contains all nine `S11`..`S33` trace labels and a
real `Plotly.newPlot(...)` call. The CLI-level `report.json` one directory up carries `characterize_report_path` pointing at the
exact file above. This was a fresh `out-dir` (no prior hash-cached data to skip), so this run did
a genuine solve; `--plot`'s own contribution is reading the `.s3p` that same `simulate` call just
produced -- no second solve, no separate command.

## CLI: `passivelab simulate` (sub-phase 1.4.9)

`scripts/simulate.py`'s `simulate_command()` (+ `passivelab simulate spec.json solver-config.json
--out-dir out`, see the README) runs the whole pipeline in one call — generate → merge → solve →
report.json — the same "one command, one artifact" shape as `generate`/`sweep`, resolving the
solver via `core/characterization/registry.py` from the config's own `"solver"` field rather than
importing `OpenEMSBackend` directly, so a second solver plugin needs no CLI changes. `OpenEMSBackend
.load_config` (a `staticmethod` pointing at `load_openems_config`) is what lets the CLI resolve the
right config loader generically through the registry lookup. Single-spec only for v1; auto-detecting
a sweep-spec from the input JSON's shape is a documented future enhancement (the task body), not
built here.

## See also

- `core/characterization/GOAL.md`, `docs/CORE_INTERFACE_DESIGN.md` — the `SimulationBackend`
  interface this implements.
- `docs/NOTEBOOK_ARCHITECTURE_REPORT.md` (cells 9/11/14, the line-312 patch) — the hacks this
  sub-phase removes rather than reproduces.
- `characterization/openems/vendor/NOTICE` — vendoring provenance and local changes.
- Board tasks **1.4.2** (port/reference-plane/de-embedding convention, generalized across passive
  types), **1.4.4** (S-parameter post-processing to `Metrics`), **1.4.3** (install path/num_cpus/
  non-silent execution fixes), **1.4.7** (femtosecond-timestep root cause), **1.4.10** (CLI/API
  parity survey across `generate`/`characterize`/`optimize`/`evaluate`), **1.5.2** (Ray-distributed
  dataset generation calling this backend).
