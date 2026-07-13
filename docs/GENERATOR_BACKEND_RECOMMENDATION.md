# Generator Backend Recommendation

> Deliverable for Phase 1 sub-phase **1.1 — Generator investigation**, subtask **1.1.3**
> (`docs/PRD/Phase 1 — TCoil Platformization.md` §5). This is the **decision** that closes 1.1:
> which L3 Generator backend PassiveLab adopts. Written as an MADR-shaped record so it maps
> directly onto the vault ADR (`DEC-generator-choice`) the harvest loop scaffolds from this
> PR. Validation criterion: *decision justified by the matrix evidence, not preference* — every
> claim below traces to [`docs/GENERATOR_COMPARISON_MATRIX.md`](GENERATOR_COMPARISON_MATRIX.md)
> (1.1.1) or [`benchmark/geometry/tcoil/benchmark_generation_speed_report.md`](benchmark/geometry/tcoil/benchmark_generation_speed_report.md)
> (1.1.2).

**Status:** proposed · **Deciders:** James (human, approves the ADR); Claude (drafts the
evidence) · **Date:** 2026-07-13

---

## Context and problem statement

The golden notebook builds all T-coil geometry with **gdspy** (`tcoil_bias.py`;
`NOTEBOOK_CELL_MAP.md` cell 9). PassiveLab's architecture lists `gdstk` / `glayout` / OpenFASOC
/ custom as the L3 Generator backend options and explicitly prefers gdstk/glayout over gdspy
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md), L3; Master PRD §6.1-L3). Sub-phase 1.1 exists to
decide, on evidence, whether to keep gdspy or migrate — before any later sub-phase (1.2 core
extraction, 1.3 T-coil plugin) builds on top of the choice.

Decision needed: **which single geometry backend does the T-coil plugin (and every later
passive) build on?**

## Decision drivers

From the 1.1.1 matrix (five columns) and the 1.1.2 prototype:

1. **T-coil feasibility** — can it actually produce the golden 11-parameter T-coil?
2. **PDK awareness for IHP SG13G2** — our target PDK specifically.
3. **Parametric support** — the 11 parameters drive generation directly.
4. **Export compatibility** — GDSII (and ideally more) for the openEMS/KLayout flow.
5. **Maintainability** — active upstream, installable, license.
6. **Migration cost from the notebook** — how much of `tcoil_bias.py` survives the port.

## Considered options

- **gdspy** — the notebook's current backend.
- **gdstk** — same author, C++-backed successor.
- **glayout** — PDK-aware parametric PCell framework (`ReaLLMASIC/gLayout`).
- **OpenFASOC** — end-to-end spec→GDSII generator framework (`idea-fasoc/OpenFASOC`).

| Option | T-coil | SG13G2 | Parametric | Export | Maintenance | Verdict |
|---|---|---|---|---|---|---|
| gdspy | ✅ proven (notebook) | manual stackup | ✅ | GDSII | ❌ **archived** repo (last push 2024-04-11); won't build on Windows (no wheel, needs MSVC) | reject |
| **gdstk** | ✅ prototype (PR #10) | manual stackup (same as gdspy) | ✅ | GDSII + OASIS | ✅ active (pushed 2026-03); no workaround needed | **adopt** |
| glayout | ❌ no passive/inductor generator | ❌ SKY130/GF180 only | ✅ | GDS + SPICE | ✅ active | reject (2 structural gaps) |
| OpenFASOC | ❌ no passive generator (LC-DCO WIP) | ❌ sky130 only | spec-level | GDS/DEF/LEF/SPICE | ⚠️ maintained, slower | reject (wrong layer + PDK) |

## Decision outcome

**Chosen: gdstk.**

The evidence chain:

- **It works, proven, not assumed.** The 1.1.2 prototype
  (`src/passivelab/geometry/tcoil/`) is a faithful gdstk port of the notebook's
  `CreateTCoilTraceVanilla` + its 4 helpers, emits valid GDS with all 11 parameters wired
  (CI-enforced), and reproduces the notebook's own smoke-test vector. This is the *only*
  non-gdspy option in the matrix with a working T-coil.
- **It removes a class of bug.** gdstk's explicit `Library()` object needs none of gdspy's
  `gdspy.library.use_current_library = False` global-state workaround, which the notebook
  repeats 6× (`NOTEBOOK_CELL_MAP.md` cell 10). One of the flagged notebook hacks disappears for
  free.
- **The port is mechanical, not a redesign.** The gdspy→gdstk API differences
  (`rectangle()` free function, `FlexPath` added directly, `boolean()` returns a list,
  `get_polygons(layer=,datatype=)`, `cell.remove(*objs)`) are a small fixed mapping, fully
  documented in the 1.1.2 report — ~230 lines ported in one sitting.
- **gdspy is a dead end.** Its upstream repo is **archived** on GitHub (1.1.1, `gh api`), and
  it could not even be installed in our environment for a live comparison (no Windows wheel;
  requires MSVC Build Tools) — a second, independent strike beyond the archived status.
- **glayout and OpenFASOC are the wrong shape for now.** Both are PDK-aware but neither supports
  **IHP SG13G2**, and neither ships a passive/inductor generator — adopting either means
  building *both* a new PDK layer and a new T-coil generator from scratch, strictly more work
  than the proven gdstk port. gdstk being PDK-agnostic is acceptable: the notebook already
  proves the "read `SG13G2.xml` + manual stackup" pattern works, and it's independent of which
  geometry kit sits underneath.

## Consequences

**Positive**
- Actively maintained backend; no reliance on an archived project.
- The 6× `use_current_library` hack is eliminated at the source.
- Broader export (GDSII + OASIS) than gdspy's GDSII-only.
- A working, tested generator already exists to hand to sub-phase 1.2.

**Negative / accepted**
- gdstk is **not PDK-aware** — PassiveLab keeps the notebook's manual SG13G2 stackup handling
  (this is unchanged from gdspy, not a regression; and it's the same for any raw-geometry kit).
- A one-time port cost from gdspy's API (already paid in 1.1.2).
- glayout's PCell-based, PDK-aware model is genuinely interesting for later (e.g. Phase 2
  MOMCap, or if an SG13G2 layer ever becomes worthwhile) — deferred, not dismissed
  (`GENERATOR_COMPARISON_MATRIX.md` §3 open questions).

**Explicitly out of scope of this decision:** the `pad_siz`/`Lext` "fixed vs. varying"
contradiction between the PRD table and the notebook (flagged in the 1.1.2 report §8) is a
**parameter-range** question for sub-phase 1.3, orthogonal to the backend choice.

## Confirmation

Feasibility is already demonstrated end-to-end by merged PR #10 (the 1.1.2 prototype): 27
passing tests, valid round-tripped GDS, visually-verified layouts (rectangular T-coil +
octagonal variant), and a benchmark report. No further spike is needed before 1.2 adopts gdstk
behind the `LayoutGenerator` interface.

## Related

- [`docs/GENERATOR_COMPARISON_MATRIX.md`](GENERATOR_COMPARISON_MATRIX.md) — 1.1.1 evidence matrix.
- [`benchmark/geometry/tcoil/benchmark_generation_speed_report.md`](benchmark/geometry/tcoil/benchmark_generation_speed_report.md) — 1.1.2 prototype findings.
- [`src/passivelab/geometry/tcoil/`](src/passivelab/geometry/tcoil/) — the working gdstk generator.
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — the L3 Generator contract this decision fills.
