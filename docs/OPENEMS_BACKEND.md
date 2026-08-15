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

## Vendored PDK modules

`vendor/modules/{util_stackup_reader,util_gds_reader,util_utilities,util_simulation_setup,
util_meshlines}.py` + `SG13G2.xml`, copied from a local `IHP-Open-PDK` checkout
(`ihp-sg13g2/libs.tech/openems/openems_ihp_sg13g2/workflow/`, Apache 2.0 — see `vendor/NOTICE`).
Two changes from upstream:

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

**Note on `gdspy`**: `util_gds_reader.py` (and, transitively, `util_meshlines.py`) hard-depends on
`gdspy`, not `gdstk` — the platform's own gdstk-over-gdspy choice
(`DEC-adopt-gdstk-as-the-l3-generator-backend-0002`) was about the L3 *generator* backend; this is
vendored third-party PDK code the solver plugin depends on, confined entirely to the `sim` extra
and never touching `core/` or the gdstk-based generator.

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
  manifest.json               # sample_id, solver, config used, port definitions, solver versions,
                               # wall-clock time, success/failure + error — everything a future
                               # webapp or 1.5.2's DatasetPipeline needs without bespoke parsing
```

`OpenEMSBackend(config, out_dir)` takes `out_dir` at construction (one instance = one output root);
`sample_id` is derived deterministically inside `simulate()` from `layout.parameter_manifest` (a
stable hash), not threaded in as a new argument or a `Layout`/`SimulationBackend` Protocol change.
This gets two properties from one mechanism: concurrent callers processing *different* samples
never collide (each owns its own subfolder — a 1.5.2 Ray-fan-out invariant, unique `sample_id`s),
and re-running the *same* sample naturally reuses its path and gets the vendored hash-based
skip-if-unchanged behavior as real caching across separate runs, not just retries within one.

`SimulationResult.raw` points to the `.s3p`/manifest rather than duplicating the full `(n, n,
numfreq)` S-parameter matrix as JSON — the Touchstone file is the canonical artifact (matches how
the golden reference's own dataset loader reads results back off disk), and embedding the full
matrix in every sample's manifest would bloat it for no reader not already better served by
re-reading the `.s3p` file.

Other scalability constraints upheld (see `plugin.py`'s module docstring): no `os.chdir()` (every
path is absolute), no mutable instance/live-solver state between `simulate()` calls.

## Known limitations / open items

- **`num_cpus` mechanism unconfirmed.** Neither vendored file sets an explicit thread count;
  openEMS's `FDTD.Run()` likely respects `OMP_NUM_THREADS` implicitly (standard for OpenMP-based
  solvers), but this isn't verified against the installed `openEMS` package's actual API (not
  exercised in this environment — the `sim` extra isn't installed here). `OpenEMSConfig.num_cpus`
  is captured but not yet wired to anything; resolve when first run against a real installation.
- **Vendored `write_snp()`'s 1-port code path is untested by this sub-phase.** It indexes
  `Smatrix[0, index]` for a `(1, numfreq)`-shaped input, but this backend always builds `(n, n,
  numfreq)`. T-coil never produces a 1-port sample (PAD/CIR are unconditional; only the tap is
  optional, giving a minimum of 2 ports), so this path is never hit by anything 1.4.1 validates
  against — flagged for whoever adds a genuinely single-port passive behind this backend later.
- **`test_plugin.py` is unexercised in this environment.** `openEMS`/`CSXCAD`/`gdspy` aren't
  installed here (compiled packages, not part of `.[dev]`) — the integration test is written and
  `pytest.importorskip`-guarded, but validating it against a real solver install and comparing
  against the golden notebook's own output for the same geometry (1.4.1's stated validation bar)
  is the next concrete step, ideally alongside first standing up the `sim` extra somewhere with
  openEMS actually installed.

## See also

- `core/characterization/GOAL.md`, `docs/CORE_INTERFACE_DESIGN.md` — the `SimulationBackend`
  interface this implements.
- `docs/NOTEBOOK_ARCHITECTURE_REPORT.md` (cells 9/11/14, the line-312 patch) — the hacks this
  sub-phase removes rather than reproduces.
- `characterization/openems/vendor/NOTICE` — vendoring provenance and local changes.
- Board tasks **1.4.2** (port/reference-plane/de-embedding convention, generalized across passive
  types), **1.4.3** (S-parameter post-processing to `Metrics`), **1.5.2** (Ray-distributed dataset
  generation calling this backend).
