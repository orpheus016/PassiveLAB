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

- **The tcoil retrofit** — `src/passivelab/geometry/tcoil/` (the working gdstk generator from 1.1.2)
  is wrapped behind `LayoutGenerator` in **sub-phase 1.2.3**. That wrap returns a `Layout` around
  the `gdstk.Cell` it already produces; it does **not** change geometry.
- **The plugin registry** — how `generate(spec)` finds `TCoilGenerator` without `core/` importing
  `tcoil/` — is **1.3**, once there is a real plugin to register.
- **`spec.json` entry + `openPCells` adoption** — a formal spec file/CLI (designer input) and
  whether to adopt openPCells' spec-driven PCell generation are studied in
  `docs/adoption/OPENPCELLS_ADOPTION_STUDY.md` and tracked as board tasks; not built here.

## See also
- `docs/CORE_INTERFACE_DESIGN.md` · `../GOAL.md` (the four-API contract) ·
  `src/passivelab/geometry/GOAL.md` (the device-implementation side this wraps).
