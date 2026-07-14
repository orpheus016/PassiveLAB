# Core Abstraction Validation Report

> **The Phase 1 sub-phase 1.2.4 deliverable** (`docs/PRD/Phase 1 — TCoil Platformization.md` /
> the 1.2 parent task's own words): confirm and document that *"the T-coil is expressible
> entirely through the core interfaces, with zero T-coil-specific code above the plugin
> boundary."* This closes out **1.2 Core abstraction extraction** and is the gate for starting
> **1.3 T-Coil plugin**.
>
> This report synthesizes evidence already built across 1.2.1–1.2.3; no new code or analysis was
> performed to produce it (same discipline as the 1.0.3 precedent,
> [`NOTEBOOK_ARCHITECTURE_REPORT.md`](NOTEBOOK_ARCHITECTURE_REPORT.md)). Every claim below traces
> to a real file, line, or test name — per the citation rule, an unsourced claim would be marked
> as needing verification rather than asserted.
>
> **Source of truth:** [`docs/CORE_INTERFACE_DESIGN.md`](CORE_INTERFACE_DESIGN.md) (1.2.1's
> approved design; vault `DEC-1-2-1-design-the-core-interface-specification`), implemented in PR
> [#16](https://github.com/orpheus016/PassiveLAB/pull/16) (1.2.2) and retrofitted onto T-coil in
> PR [#18](https://github.com/orpheus016/PassiveLAB/pull/18) (1.2.3), both merged.

---

## 1. Per-interface walkthrough

All 7 interfaces from the 1.2.1 design exist in `passivelab.core`. T-coil has a **concrete**
implementation for the 2 interfaces sub-phase 1.2.3 scoped it for; for the other 5, T-coil's real
generated geometry is proven to flow correctly through their *shape* (via fakes — concrete
backends are 1.4–1.8, not a 1.2 gap).

| Interface | Defined in | T-coil implementation | Status |
|---|---|---|---|
| `PassiveSpec` | `core/geometry/spec.py` | `TCoilSpec` (`geometry/tcoil/spec.py`) | **Concrete** |
| `LayoutGenerator` | `core/geometry/generator.py` | `TCoilLayoutGenerator` (`geometry/tcoil/plugin.py`) | **Concrete** |
| `SimulationBackend` | `core/characterization/backend.py` | fake `FakeBackend`, real `.cell` polygon count (`tests/test_tcoil_core_integration.py`) | Shape-proven; real backend = **1.4** |
| `DatasetPipeline` | `core/characterization/dataset.py` | fake `InMemoryDatasetPipeline`, accumulates real `TCoilSpec`/`Metrics` rows (same test) | Shape-proven; real pipeline = **1.5** |
| `ModelTrainer` | `core/characterization/surrogate.py` | no T-coil usage yet (no dataset to train on) | Deferred to **1.6** (needs 1.5 first) |
| `Optimizer` | `core/optimization/optimizer.py` | fake `GridOptimizer`/`ForeignOptimizer` drive real `TCoilSpec`/`TCoilLayoutGenerator` (`tests/test_archetypes.py`) | Shape-proven; real optimizer = **1.7** |
| `ValidationRunner` | `core/benchmark/validation.py` | fake `TargetRunner` scores real T-coil candidates (same test) | Shape-proven; real backend = **1.7/1.8** |

`ModelTrainer` is the one interface with no T-coil exercise at all yet — honest gap, not hidden:
it needs a `Dataset` to train against, and no dataset exists until 1.5 lands. This does not block
1.2's own validation bar (the bar is about the *generate* path being interface-driven, and
`ModelTrainer` was never part of 1.2.3's scope).

## 2. No-leakage confirmation

`core/` must have zero references to `tcoil`/`gdstk` — enforced, not just claimed, by
[`core/tests/test_no_leakage.py`](../src/passivelab/core/tests/test_no_leakage.py) (2 tests,
`test_core_imports_no_device_or_geometry_kit` + `test_core_covers_every_core_source_file`), which
scans the actual `import`/`from` statements of every `core/` source file — passing.

The reverse direction — no code *outside* the tcoil plugin calling `generate_tcoil`/`TCoilParams`
directly — was checked by grepping every `.py` file in the repo for those two names, excluding
`src/passivelab/geometry/tcoil/` itself. **5 files matched; 3 are prose, not imports:**

| File | Match | Real import? |
|---|---|---|
| `core/geometry/generator.py` | docstring sentence explaining the wrap | No |
| `tests/test_plugin_interop.py` | a code comment (`# not a TCoilParams subclass`) | No |
| `tests/test_tcoil_core_integration.py` | docstring + a string literal inside its own guard test | No — and this file's `test_file_only_imports_plugin_surface` enforces this on its own source |
| `benchmark/geometry/tcoil/octagon_variant.py` | real import, `from passivelab.geometry.tcoil.spec import TCoilParams` | **Yes — deliberate exception** |
| `benchmark/geometry/tcoil/benchmark_generation_speed.py` | real import (via package `__init__.py`) | **Yes — deliberate exception** |

The 2 real exceptions are both `benchmark/` scripts, explicitly outside the core-interface
pipeline: `octagon_variant.py`'s own docstring calls it a "bonus/exploratory... NOT from the
golden notebook" shape demo, and `benchmark_generation_speed.py` is raw generation-speed
benchmarking, not a platform consumer. Neither claims to go through `PassiveSpec`/
`LayoutGenerator`, so neither is a leak of the *interface* boundary — they're standalone
geometry-kit experiments that predate and sit alongside the plugin, not above it.

`geometry/tcoil/plugin.py`'s own `passivelab.core` import surface is minimal: only
`from passivelab.core.types import Layout` — nothing else pulled from `core/`.

## 3. Same-geometry regression ("wrap, not rewrite")

The load-bearing proof that wrapping T-coil changed nothing about its output:
[`tcoil/tests/test_plugin.py::test_plugin_path_produces_identical_geometry_to_direct_call`](../src/passivelab/geometry/tcoil/tests/test_plugin.py)
fingerprints (polygon count + bounding box + rounded vertex coordinates) the plugin path
(`TCoilLayoutGenerator().generate(TCoilSpec(...)).cell`) against a direct
`generate_tcoil(TCoilParams(...))` call for the same parameters and asserts equality — passing.

Corroborating facts:
- PR #18's initial commit (`c78c7ea`) had an **empty** `git diff --stat` on `generator.py`/
  `rules.py`/`templates.py` — literally zero edits for the retrofit itself.
- A follow-up commit on the same PR (`f5ed1ea`) relocated the `TCoilParams` dataclass from
  `generator.py` into `spec.py` (so `generator.py` stays pure generation logic — the convention
  now documented in `geometry/GOAL.md`). That commit *did* touch `generator.py` and `rules.py`,
  but only by one import line each (a real import → a `TYPE_CHECKING`-guarded one); no generation
  or validation logic changed, which the same regression test — still green after that commit —
  reconfirms.

## 4. Multi-device generalization

To guard against the interfaces being an accidental fit to tcoil alone,
[`tests/test_plugin_interop.py`](../tests/test_plugin_interop.py) drives the real T-coil plugin
and a **test-only** dummy MoM Cap stub (explicitly *not* the real Phase 2 plugin) through the
*same* generic caller code, with no `isinstance`/type-branching, and confirms both conform to
`PassiveSpec`/`LayoutGenerator` with no shared base class between them (3 tests, passing) — direct
evidence for the Master PRD's "a new passive is a new plugin, not a core change" invariant.

## 5. Explicitly out of scope (not gaps)

- Concrete `SimulationBackend`/`ModelTrainer` (1.4/1.6), `DatasetPipeline` (1.5), `Optimizer`
  (1.7), `ValidationRunner` (1.7/1.8) backends — see §1.
- **DRC checking** (design-rule checking against a real PDK deck, via OpenROAD Flow Scripts /
  KLayout) — layout-level, distinct from `PassiveSpec.validate()`'s parameter-range checks;
  tracked as its own board task, out of 1.2's scope by design (see `tcoil/spec.py`'s docstring).
- **The plugin registry** (how `generate(spec)` finds `TCoilGenerator` without `core/` importing
  `tcoil/`) — deferred to **1.3**, since a registry needs a real second caller to design against
  (only tcoil exists so far); see §6.

## 6. Test evidence (fresh run, this report)

```
47 passed in 0.92s
```
Breakdown: 3 `test_archetypes.py` (fake-only journeys) · 3 `test_plugin_interop.py` (real tcoil +
dummy stub) · 1 `test_smoke.py` · 2 `test_tcoil_core_integration.py` (real tcoil through core
Protocols) · 3 `core/tests/test_interfaces_shape.py` · 2 `core/tests/test_no_leakage.py` · 15
`tcoil/tests/test_generator.py` (unchanged since 1.1.2) · 7 `tcoil/tests/test_plugin.py` · 11
`tcoil/tests/test_rules.py` (unchanged since 1.1.2).

## 7. Conclusion

**PASS.** The T-coil is expressible entirely through the core interfaces — concretely for
`PassiveSpec`/`LayoutGenerator`, shape-proven with real geometry for the remaining 5 (excepting
`ModelTrainer`, honestly noted as untested pending 1.5) — with zero T-coil-specific code above the
plugin boundary (2 deliberate, documented, out-of-pipeline benchmark-script exceptions; `core/`
itself is provably clean). Sub-phase 1.2 is closed; 1.3 (T-Coil plugin) is unblocked.

## 8. Forward note on 1.3

`1.3-t-coil-plugin.md`'s task body (written 2026-07-09, before 1.2.1 pinned exact interface
names) describes building "`TCoilSpec` + `TCoilGenerator`" and testing "with fake MOM Cap present
... to test whether multiple geometry works" as **1.3's own deliverable**. Both already exist —
`TCoilSpec`/`TCoilLayoutGenerator` (1.2.3) and the dummy MoM Cap interop test (§4, 1.2.3). 1.3's
real remaining scope is the **plugin registry** (§5) and `spec.json` wiring, not rebuilding the
spec/generator classes — annotated directly on that task's body to avoid duplicate work.

## See also
- `docs/CORE_INTERFACE_DESIGN.md` — the design this validates.
- `docs/ARCHITECTURE.md` / `docs/VISION.md` / `docs/PRD/00 Master PRD.md` §3, §6, §11.
- `src/passivelab/geometry/GOAL.md`, `src/passivelab/core/GOAL.md` (+ per-package `GOAL.md`).
