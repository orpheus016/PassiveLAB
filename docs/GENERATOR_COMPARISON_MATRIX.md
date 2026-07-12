# Generator Comparison Matrix

> Deliverable for Phase 1 sub-phase **1.1 — Generator investigation**, subtask **1.1.1**
> (`docs/PRD/Phase 1 — TCoil Platformization.md` §5). This is the **evidence matrix only** —
> it does not conclude a recommendation. Subtask 1.1.2 prototypes a candidate backend against
> this evidence; subtask 1.1.3 writes the actual backend recommendation report (1.1's overall
> deliverable). Validation criterion: *every cell filled with a cited basis (docs / repo /
> notebook)*.

**Why this investigation:** the golden notebook uses **gdspy** for all geometry
(`tcoil_bias.py`: `CreateTCoilTraceVanilla`, `CreateViaArray`, `CreateGroundPlane`,
`CreateOctagonPad` — `NOTEBOOK_CELL_MAP.md` cell 9). PassiveLab's own architecture doc lists
`gdstk` / `glayout` / OpenFASOC / custom as the L3 Generator backend options and explicitly
prefers gdstk/glayout over gdspy (`docs/ARCHITECTURE.md` §"The layered pipeline", L3; master
PRD §6.1). This sub-phase decides whether to keep gdspy or migrate.

**"T-coil support" means, concretely:** can the tool reproduce the golden generator's
11-parameter octagon-spiral T-coil with ground plane and via array
(`docs/PRD/Phase 1 — TCoil Platformization.md` §5, sub-phase 1.3's parameter list) — either
out of the box, or as straightforward custom code on top of the library's primitives.

---

## 1. The matrix

| | **gdspy** | **gdstk** | **glayout** | **OpenFASOC** |
|---|---|---|---|---|
| **T-coil support** | **Proven** — the golden notebook's full T-coil generator runs on gdspy today: octagon pad/trace, via array, ground plane combination (source: `NOTEBOOK_CELL_MAP.md` cell 9, `reference/jupyter/TCoil_Dataset_Generator_and_Training (1).ipynb`). | **Unverified but expected feasible** — same author/API family as gdspy (paths, boolean ops, cell references, "parametric cell design patterns"), positioned as gdspy's direct successor ([heitzmann.github.io/gdstk](https://heitzmann.github.io/gdstk/)). No T-coil has actually been built on it; this is exactly what 1.1.2 tests. | **Not shipped** — glayout's own generators are transistors (NMOS/PMOS), via-stacks, and guard rings only; no inductor/passive/T-coil PCell exists ([github.com/ReaLLMASIC/gLayout](https://github.com/ReaLLMASIC/gLayout) README). Would require building a new T-coil PCell from glayout's primitives. | **Not shipped** — OpenFASOC's generators are Temperature Sensor, LDO, DC-DC (WIP), Cryo (WIP), LC-DCO (WIP), SCPA (WIP) (source: `200 raw/.../OpenFaSoc Docs/Welcome to the OpenFASoC documentation!.md`). None is a passive/inductor generator; LC-DCO (closest, since LC oscillators use spiral inductors) is still work-in-progress with no available implementation docs. |
| **PDK awareness (IHP SG13G2)** | **None built-in** (raw geometry kit) — but the golden notebook already proves gdspy works *with* SG13G2 by reading the foundry stackup directly (`SG13G2.xml`) and applying a manual PDK source patch outside gdspy itself (source: `NOTEBOOK_CELL_MAP.md` cells 4–5, 9). | **None built-in**, same profile as gdspy — no PDK-integration features documented ([heitzmann.github.io/gdstk](https://heitzmann.github.io/gdstk/)); would need the same manual stackup-handling pattern the notebook already uses. | **PDK-aware, but not for our PDK** — ships parametric PCells against **SkyWater SKY130 and GlobalFoundries GF180MCU only**; IHP SG13G2 is not mentioned anywhere in the project ([github.com/ReaLLMASIC/gLayout](https://github.com/ReaLLMASIC/gLayout) README). Adopting glayout would mean building an SG13G2 PDK layer from scratch. | **PDK-aware, but sky130-only** — every generator flow targets "Supported Technology: Sky130A" (source: `200 raw/.../OpenFaSoc Docs/Github/Getting Started.md`, the `make sky130hd_temp` flow banner). No IHP SG13G2 support. |
| **Parametric support** | **Proven** — the 11-parameter geometry table (`pad_siz`, `Lext`, `sizX`/`sizY`, `wid`, `gap`, `total_seg`, `tap_segid`, `tap_ratio`, `end_ratio`, `ratio_firY`) drives the generator directly (source: `NOTEBOOK_CELL_MAP.md` cell 8–9). | **Yes, by design** — the docs describe explicit "parametric cell design patterns" alongside cell hierarchy / references / arrays ([heitzmann.github.io/gdstk](https://heitzmann.github.io/gdstk/)). | **Yes, demonstrated** — component generators take keyword parameters directly, e.g. `nmos(sky130, width=1.0, length=0.15, fingers=2)` ([github.com/ReaLLMASIC/gLayout](https://github.com/ReaLLMASIC/gLayout) README). | **Yes, at the spec level** — user parameters (e.g. `VREG`, `Iload` for the LDO generator) flow through a JSON spec file into Verilog/Mako templates that size the design (source: `200 raw/.../2121 Codes/markdown/LDO_notebook.md`). This is circuit/verilog parametrization, not direct passive-geometry parametrization like the other three. |
| **Export compatibility** | **GDSII only** — `write_gds(...)` is the notebook's only geometry output path (source: `NOTEBOOK_CELL_MAP.md` cell 10). | **GDSII + OASIS** — explicitly documented dual-format export ([heitzmann.github.io/gdstk](https://heitzmann.github.io/gdstk/), [github.com/heitzmann/gdstk README](https://github.com/heitzmann/gdstk/blob/main/README.md)). | **GDS + SPICE netlist** — `.write_gds()` methods plus hierarchical SPICE netlist generation per component ([github.com/ReaLLMASIC/gLayout](https://github.com/ReaLLMASIC/gLayout) README). | **GDS/DEF/LEF/SPICE/Verilog** — the full OpenROAD-flow output set per generator run (source: `200 raw/.../OpenFaSoc Docs/Github/Getting Started.md`: "creates the lef/def/gds/spice netlist files"). |
| **Maintainability** | **Unmaintained** — the upstream repo is **archived** on GitHub, last pushed **2024-04-11** (over 2 years stale as of this report), BSL-1.0, 385★/15 open issues (`gh api repos/heitzmann/gdspy`, checked 2026-07-12). The README itself states v1.6 was gdspy's last major release, bugfix-only since. | **Actively maintained** — not archived, last pushed **2026-03-13** (~4 months ago), BSL-1.0, 484★/54 open issues, largest star count of the four (`gh api repos/heitzmann/gdstk`, checked 2026-07-12). Same author as gdspy, explicitly positioned as its successor. | **Actively maintained, youngest project** — not archived, last pushed **2026-05-29** (~6 weeks ago, most recent of the four), MIT, 35★/23 open issues (`gh api repos/ReaLLMASIC/gLayout`, checked 2026-07-12). Smallest community of the four. | **Maintained, slower cadence** — not archived, last pushed **2025-10-22** (~9 months ago), Apache-2.0, 340★/41 open issues (`gh api repos/idea-fasoc/OpenFASOC`, checked 2026-07-12). |

## 2. Per-tool narrative

### gdspy
What the golden notebook uses today, and the only tool in this matrix with **proven** T-coil
support — the full generator (`tcoil_bias.py`) already produces the correct geometry
(`NOTEBOOK_CELL_MAP.md` cell 9). Its weakness is entirely maintenance: the upstream repository
is **archived** on GitHub with its last commit from April 2024, and the README itself
describes it as bugfix-only since v1.6. It has no PDK awareness, but neither do gdstk/OpenFASOC's
underlying geometry layers for our PDK — the notebook's pattern of reading `SG13G2.xml` directly
and patching the PDK module works regardless of which raw geometry kit sits underneath.

### gdstk
Same author (Lucas Heitzmann Gabrielli) as gdspy, explicitly built as its C++-backed successor.
Actively maintained (pushed 4 months ago vs. gdspy's 2+ years), broader export support (GDSII +
OASIS vs. gdspy's GDSII-only), and the largest community of the four tools by star count. No
T-coil has been built on it yet and its API is not 100% compatible with gdspy's — porting
`tcoil_bias.py` is unverified work, which is exactly 1.1.2's job. PDK-agnostic in the same way
gdspy is, so it inherits the notebook's proven SG13G2-via-manual-stackup pattern without change.

### glayout
A genuinely PDK-*aware* parametric PCell framework — a meaningfully different model from
gdspy/gdstk's raw-geometry approach (`nmos(sky130, width=..., fingers=...)`-style calls instead
of hand-coded polygon math). Youngest, most actively-pushed repo of the four. Its two blockers
for this project are structural, not maintenance: it only knows SkyWater SKY130 and GF180MCU
(no IHP SG13G2), and it ships no inductor/passive generator at all — transistors, via stacks,
and guard rings only. Adopting it means building both a new PDK layer and a new T-coil PCell
from scratch, a materially larger lift than porting to gdstk.

### OpenFASOC
An end-to-end spec→GDSII *framework* (drives OpenROAD/Magic/Netgen/KLayout around its
generators), not itself a geometry library — a different category from the other three. Its
generator catalog is digital/mixed-signal (temp sensor, digital LDO) rather than analog-passive;
the one generator that could plausibly involve inductor layout, LC-DCO, is still work-in-progress
with no available implementation to evaluate. Sky130-only across every shipped generator, same
PDK gap as glayout. Adopting OpenFASOC's framework would be the largest-scope option of the
four — pulling in its whole flow machinery for a piece (passive geometry) it doesn't yet
generate.

## 3. Open questions for 1.1.2 / 1.1.3

- **gdstk T-coil port cost** — how much of `tcoil_bias.py` ports directly vs. needs rewriting
  for gdstk's API differences? (1.1.2's prototype answers this directly.)
- **OpenFASOC LC-DCO status** — does it, or will it soon, include a spiral inductor generator?
  Worth a direct check of the `idea-fasoc/OpenFASOC` `lc-dco-gen` source tree (not just docs)
  before ruling it out entirely.
- **glayout SG13G2 cost** — roughly how much work is a minimal IHP SG13G2 PDK layer for
  glayout, if its PCell-based parametrization is judged valuable enough later (e.g. for Phase 2
  MOMCap, which also needs HV-compliant geometry)?
- **Bonus finding (out of the requested 4, flagging only):** a web search surfaced
  [milanofthe/rapidpassives](https://github.com/milanofthe/rapidpassives), an open-source RFIC
  inductor/transformer layout generator — not evaluated here since it's outside this task's
  scope (rows are fixed to gdspy/gdstk/glayout/OpenFASOC per the task goal), but worth a look
  in 1.1.3 if none of the four fully satisfies T-coil + maintainability.

## Related

- [`docs/NOTEBOOK_CELL_MAP.md`](NOTEBOOK_CELL_MAP.md) — gdspy's proven T-coil usage (cells 9–10, 57–59, 74–76).
- [`docs/NOTEBOOK_ARCHITECTURE_REPORT.md`](NOTEBOOK_ARCHITECTURE_REPORT.md) — cell 9/10's `[hack]` flags (the `use_current_library` workaround) that any replacement should not carry over.
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — L3 Generator backend options this sub-phase is deciding between.
- [`docs/PRD/Phase 1 — TCoil Platformization.md`](PRD/Phase%201%20—%20TCoil%20Platformization.md) §5, sub-phase 1.1 — the task this matrix serves.
