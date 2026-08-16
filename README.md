# PassiveLAB

Design Platform for Passive Structures in IC — OpenROAD for passives. Turns a declarative
`PassiveSpec` into a generated, characterized, optimized, benchmarked passive device, PDK-agnostic.

**Current milestone**: Phase 1 (v0.0) — reproducing the golden T-coil notebook
(`reference/jupyter/`) through reusable APIs, so the notebook becomes a thin demonstration
frontend that only calls those APIs. See `docs/PRD/Phase 1 — TCoil Platformization.md`.

## Quickstart

```bash
pip install -e ".[dev,viz]"
passivelab generate examples/tcoil.spec.json --out-dir out
# python -m passivelab.cli generate examples/tcoil.spec.json
# -> out/tcoil/tcoil.gds + out/tcoil/tcoil.png
```

Open the `.gds` in KLayout, or just look at the `.png`. State your own device by copying
`examples/tcoil.spec.json` and editing the numbers — see "Generating a layout" below.

```bash
pytest                                                 # fast gate
pytest benchmark/geometry/tcoil/test_sweep.py -v -s    # parameter sweep, see "Sweeping" below
```

## Repository layout

```
src/passivelab/
  core/                # the stable platform contract (Protocols + registries), PDK/device-agnostic
  core/geometry/        # generate(spec) -> Layout: PassiveSpec, LayoutGenerator, registry, spec.json loader
  geometry/<device>/     # plugins -- e.g. geometry/tcoil/ (spec, generator, rules, plugin, preview)
  cli.py                # spec.json -> generate(spec) -> GDS (+ PNG) entry point
examples/               # spec.json starting points
tests/                   # cross-cutting integration tests (archetype journeys, multi-plugin interop)
docs/                    # architecture, vision, roadmap, design + adoption studies, PRD/
reference/               # the golden notebook + its markdown/python exports (read-only source of truth)
benchmark/               # on-demand tooling, excluded from the fast gate:
  geometry/registry.py     # benchmark-case registry, keyed by passive_type
  geometry/<device>/        # per-device timing benchmarks + cases.py + (T-coil) sweep.py
  geometry/tests/            # cross-device validity + timing, one JSON report
.github/workflows/       # CI (pytest) + claude-code-action automation
```

A device (T-coil, and later others) is a **plugin**, not core code: it provides a
`PassiveSpec`-conforming spec and a `LayoutGenerator`-conforming generator, and self-registers into
`core/geometry/registry.py` (keyed by `passive_type`) when its package is imported — `core/` never
imports a device or a geometry kit (`gdstk`), enforced by `core/tests/test_no_leakage.py`. The four
stable core APIs:

```
generate(spec)       -> Layout      (L1-L3   geometry -- built)
characterize(layout) -> Metrics     (L4-L7   characterization -- 1.4+)
optimize(objective)  -> Candidate   (L8      optimization -- 1.7+)
evaluate(candidate)  -> Score        (L9-L10  benchmark -- 1.7+)
```

Full docs: `docs/ARCHITECTURE.md`, `docs/VISION.md`, `docs/PRD/`, one `GOAL.md` per `src/` folder.

## Generating a layout

`spec.json` is flat: `passive_type` plus that device's own field names verbatim (see
`examples/tcoil.spec.json`) — no wrapper, no translation. The CLI:

```bash
passivelab generate examples/tcoil.spec.json --out-dir out
```

loads the spec, calls `spec.validate()` (parameter-range checks only — DRC is separate,
out of scope), dispatches to the right plugin via `generate(spec)`, and writes
`<out-dir>/<cell_name>/<cell_name>.gds` (+ `.png` unless `--no-png`). The written GDS's layers are
checked against the plugin's real PDK layer set before it ever reaches you — a malformed spec or
an unknown `passive_type` fails with one line (`error: ...`), not a traceback.

## Sweeping parameters

```bash
passivelab sweep examples/tcoil.sweep.json --out-dir out
```

Generates an N-sample sweep from a sweep-spec.json (`n`/`seed` + the two fields the notebook's
sampler otherwise hardcodes, `includepad`/`pad_siz`) — every randomized geometry field is sampled
the same way the golden notebook itself samples them, not an arbitrary grid (see
`src/passivelab/geometry/tcoil/sampling.py`). Writes `out/report.json` plus a GDS+PNG per distinct
`(nseg, includepad)` case for a quick look.

The same mechanism backs a notebook-fidelity regression test, run on demand:

```bash
pytest benchmark/geometry/tcoil/test_sweep.py -v -s
```

which writes `benchmark/geometry/tcoil/sweep_out/report.json` instead.
`src/passivelab/geometry/tcoil/rules.py`'s docstring records what that sweep found about where
this repo's current parameter rules and the notebook's own usage disagree.

## Simulating (characterizing) a layout

```bash
passivelab simulate examples/tcoil.spec.json examples/openems.config.json --out-dir out
```

Same "state it declaratively" shape as `generate`/`sweep`, one layer up: `spec.json` describes the
device, `openems.config.json` (or any other registered solver's own config — the `"solver"` field
picks the backend, the command itself never hardcodes one) describes the solver run. Generates the
`Layout`, runs it through the named `SimulationBackend`, and writes `<out-dir>/simulate/
<passive_type>/<solver>/report.json` pointing at the backend's own per-sample `manifest.json`/
`.s3p` (see `docs/OPENEMS_BACKEND.md`'s output-folder design) — the report doesn't duplicate that
data, just links to it.

Needs the solver's own extra installed to actually run (e.g. `pip install -e ".[sim]"` for
openems, plus a real openEMS/CSXCAD install — see `characterization/openems/vendor/NOTICE`);
without it, `simulate` fails with a clear `error: ...` naming the missing extra, the same as
`generate --no-png`'s matplotlib check.

Single `spec.json` only for now — a `sweep-spec.json` (many samples through the same solver run)
is a documented future enhancement, not built here (board task 1.4.9).
