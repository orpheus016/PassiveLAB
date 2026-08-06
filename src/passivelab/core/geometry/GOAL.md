# Goal: `src/passivelab/core/geometry/`

The **generate** north star (L1-L3):

```
generate(spec: PassiveSpec) -> Layout
```

Two interfaces:
- `PassiveSpec` (`spec.py`) — the canonical, near-empty input every generator consumes. A passive's
  real parameters live in the *plugin's* spec that satisfies this Protocol; **no device-specific
  fields at the core level**.
- `LayoutGenerator` (`generator.py`) — turns a spec into a `Layout` (geometry handle + metadata +
  parameter manifest).

## Who it serves

- **Analog / IC designer** — states a spec (ultimately a `spec.json`) → gets an implementable layout.
- **Device researcher** — sweeps specs → gets layouts to characterize.

## Invariant

`PassiveSpec` is the **only** entry to generation (no generator bypasses L2). `core/geometry/` is
device- and kit-agnostic: nothing here imports `gdstk` or any `tcoil` code (enforced by
`core/tests/test_no_leakage.py`).

## In scope now (1.2.2)

The two Protocols + their shape tests. No generation logic.

## Deferred (not here)

(nothing currently deferred at this sub-package level — see `../GOAL.md` for the other three
core APIs' own dispatch, still to come in 1.4-1.7)

## Done

- **The plugin registry** (sub-phase 1.3.1) — `registry.py`: `register`/`get`/`generate`, keyed by
  `PassiveSpec.passive_type`. `generate(spec)` resolves `TCoilLayoutGenerator` (or any other
  registered device) at runtime with zero `core/` -> `tcoil/`/`gdstk` coupling (re-confirmed by
  `core/tests/test_no_leakage.py`); the T-coil plugin self-registers on import
  (`geometry/tcoil/__init__.py`). Also exported at the top level as `passivelab.core.generate`.
  Multi-device dispatch (not a one-device special case) is proven by
  `tests/test_plugin_interop.py::test_core_generate_dispatches_tcoil_and_dummy_momcap_through_the_same_registry`.
- **The tcoil retrofit** (sub-phase 1.2.3) — `src/passivelab/geometry/tcoil/{spec.py,plugin.py}`
  wrap the working gdstk generator from 1.1.2 behind `PassiveSpec`/`LayoutGenerator`. `TCoilParams`
  lives in `spec.py` (moved from `generator.py` for a cleaner, params-free generator module);
  generation/validation *logic* in `generator.py`/`rules.py` is unchanged (verified by a
  same-geometry regression, `tcoil/tests/test_plugin.py`).
- **`spec.json` entry + `openPCells` adoption** — a formal spec file/CLI (designer input) and
  whether to adopt openPCells' spec-driven PCell generation are studied in
  `docs/adoption/OPENPCELLS_ADOPTION_STUDY.md` and tracked as board tasks; not built here.

## See also
- `docs/CORE_INTERFACE_DESIGN.md` · `../GOAL.md` (the four-API contract) ·
  `src/passivelab/geometry/GOAL.md` (the device-implementation side this wraps).
