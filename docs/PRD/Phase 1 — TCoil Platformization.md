---
title: "PassiveLab Phase 1 — TCoil Platformization"
version: v0.0
role: phase PRD (agent-executable slice)
status: detailed
updated: 2026-07-03
master: "00 Master PRD.md"
derives_from: "../Platformization Detail PRD Phase 1.md"
grounded_in:
  - "[[DOC-tcoil-0001]]"
  - "300 digest/Claims/DOC-tcoil.jsonl"
---

# Phase 1 — TCoil Platformization  ·  v0.0

**Subtitle:** Notebook reproduction and platform extraction.

> **Agent, read this first.** Execute *only* this phase's scope. Your long-term context
> is `00 Master PRD.md` §10 (roadmap) and §11 (invariants) — read those, then act here.
> Anything under "Explicit future extensions" is **out of scope** and belongs to a later
> phase PRD.

---

## 1. Long-term context (why this phase exists)

Phase 1 delivers roadmap **v0.0** (master §10). It is pure **infrastructure**: it proves
that PassiveLab can reproduce the golden tcoil notebook ([[DOC-tcoil-0001]]) *through the
platform's reusable APIs* instead of notebook-specific code. Every later passive (MOMCap
in Phase 2, inductor in Phase 7, …) reuses the interfaces extracted here, so getting the
abstractions right now is worth more than any speed-up.

**Invariants served (master §11):** #1 PassiveSpec is the only entry to generation ·
#2 no optimization without characterization · #3 the four core APIs are stable ·
#4 reuse-first · #5 PDK-agnostic. This phase *establishes* those invariants in code.

**The golden workflow being reproduced** (master Mode B; source [[DOC-tcoil-0001]] `^p-overview`):

```
Parameters → Geometry(gdspy) → GDS → openEMS(EM) → Dataset(Ray) → ANN(MLP) → SPICE(ngspice) → CMA-ES inverse design
```

---

## 2. Goal / Non-goals

**Goal.** Reproduce the T-coil notebook workflow inside PassiveLab **without changing the
underlying methodology**, exposing it through reusable platform interfaces. *Done* =
PassiveLab reproduces the notebook outputs via APIs, and the notebook becomes only a thin
demonstration frontend that *calls* those APIs.

**Non-goals (explicitly NOT this phase).** Improving the workflow. Redesigning geometry.
Generalizing prematurely. New passive types. HV / MOMCap work. Swapping solvers. All of
these are deferred (see §9).

---

## 3. Core principle

```
Do not optimize.  Do not redesign.  Do not generalize prematurely.
First reproduce.  Then abstract.  Then optimize.
```

Governance (master §7): no coding before architecture review; every sub-phase needs a
spec, tests, validation criteria, and docs; **no logic in the notebook** — the notebook
may only call APIs.

---

## 4. Interfaces touched (map to master architecture)

Phase 1 extracts the reusable interfaces. **No passive-specific API is allowed at the
core level** — the T-coil lives only in a plugin. Each interface maps to a master layer
(§6.1) and, where applicable, a stable core API (§6.2).

| Phase-1 interface | Master layer | Core API (§6.2) | Phase-1 responsibility |
|---|---|---|---|
| `PassiveSpec` | L2 | — | Canonical spec; T-coil expressible entirely through it |
| `LayoutGenerator` | L3 | `generate(spec)` | Spec → GDS + metadata + manifest |
| `SimulationBackend` | L4–L5 | `characterize(layout)` | Wrap openEMS → S-parameters |
| `DatasetPipeline` | L6 | — | Sim results → features/labels/metadata (Parquet) |
| `ModelTrainer` | L7 | — | Train the ANN surrogate |
| `Optimizer` | L8 | `optimize(objective)` | Inverse design over surrogate + circuit |
| `ValidationRunner` | L10 | `evaluate(candidate)` | Notebook-vs-platform equivalence checks |

**Validation of the abstraction:** the T-coil must be expressible *entirely* through these
interfaces, with zero T-coil-specific code above the plugin boundary.

---

## 5. Sub-phases (ordered; each has its own validation)

Numbers match the source Phase-1 PRD; each is enriched with the concrete notebook facts
from [[DOC-tcoil-0001]] so the agent knows exactly what "equivalent" means.

### 1.0 — Notebook reverse engineering
Map every notebook cell to a stage; identify external tools, generated artifacts, reusable
components, and notebook-specific hacks. **Deliverable:** workflow diagram with every cell
categorized. **Validation:** every cell categorized.

### 1.1 — Generator investigation
Understand why **gdspy** was used and whether it can be replaced. Build a comparison
matrix — rows `gdspy / gdstk / glayout / OpenFASOC`, columns `T-coil support · PDK
awareness · parametric support · export compatibility · maintainability`.
**Deliverable:** backend recommendation report, decision justified with evidence.
_Context: the notebook uses gdspy (`tcoil_bias.py`: `CreateTCoilTraceVanilla`,
`CreateViaArray`, `CreateGroundPlane`, `CreateOctagonPad`) at 5 nm precision
(source `^p-emsim`); master §6.1-L3 prefers gdstk/glayout — this sub-phase decides._

### 1.2 — Core abstraction extraction
Extract the reusable interfaces from §4 (`PassiveSpec`, `LayoutGenerator`,
`SimulationBackend`, `DatasetPipeline`, `ModelTrainer`, `Optimizer`, `ValidationRunner`).
**Validation:** T-coil expressible entirely through interfaces; no passive-specific API.

### 1.3 — T-Coil plugin
Move notebook geometry into the plugin architecture: implement `TCoilSpec` + `TCoilGenerator`
→ GDS. The 11 geometric parameters are fixed by the golden generator (source `^tbl-params`):
`pad_siz`(50µm fix), `Lext`(5µm fix), `sizX`/`sizY`∈[20,200], `wid`∈[3,12], `gap`∈[6,24],
`total_seg`∈[2,24], `tap_segid`, `tap_ratio`, `end_ratio`, `ratio_firY`. Metal plan:
top-two thick metals for the coil, Metal5 feedline, Metal4 ground shield (IHP SG13G2,
`^p-geometry`). **Validation:** generated geometry matches notebook.

### 1.4 — Simulation pipeline
Wrap **openEMS** (FDTD, used as a Python package) + post-processing behind `SimulationBackend`.
The reference sweep is **0–100 GHz, 1001 points, 3 ports**, reading the GDS + foundry XML
(`SG13G2.xml`) (source `^p-emsim`). **Validation:** same S-parameter outputs.

### 1.5 — Dataset pipeline
`DatasetPipeline` → features / labels / metadata, stored as **Parquet** (master L6). The
golden dataset used **Ray** to distribute thousands of sims across tens of servers
(~5,000 samples in 3–4 days on a 1024-core cluster, source `^p-massivedata`). Phase 1 may
run at reduced scale but must be **statistically equivalent** to the notebook dataset.

### 1.6 — ANN pipeline
Wrap the notebook training behind `ModelTrainer`. Reference model: a **5-layer MLP**,
float32, <10M params; inputs = 9 geometric params normalized to [−1, 1]; output = an
**1818-dim vector** encoding an S3P file (101 freq points, 0–100 GHz, 1 GHz step); golden
**MAE ≈ 0.045** (source `^p-ann`). **Validation:** prediction accuracy within notebook tolerance.

### 1.7 — Optimization pipeline
`Optimizer` reproducing the inverse design. Reference: **CMA-ES**; each iteration proposes
structures, the ANN surrogate replaces costly EM, and ngspice combines passive+active for
the final metric; global cost = **−GBW/GHz + 10·Peaking_max/dB** (source `^p-inverse`).
The SPICE side transcribes S3P into ngspice's `xfer` component (ngspice lacks native
S-parameter support, `^p-spice`). **Validation:** optimization converges similarly to notebook.

### 1.8 — End-to-end verification
Run the full chain and compare against the notebook. **Metrics:** geometry equivalence ·
simulation equivalence · dataset equivalence · model-accuracy equivalence · optimization
equivalence. **Deliverable:** verification report.

---

## 6. Deliverables
1. Notebook architecture report (1.0).
2. Backend recommendation report (1.1).
3. PassiveLab core interfaces (1.2).
4. T-Coil plugin (1.3).
5. Reproduced dataset generation (1.5).
6. Reproduced model training (1.6).
7. Reproduced optimization workflow (1.7).
8. Validation report: notebook vs PassiveLab (1.8).

---

## 7. Definition of Done
PassiveLab reproduces the notebook outputs through
`PassiveSpec → Generator → Simulation → Dataset → ANN → Optimization`
**without notebook-specific code**, and the notebook becomes only a demonstration
frontend. All five §5.1.8 equivalences pass within tolerance.

---

## 8. Agent roles & rules
- **Architecture Reviewer** — detect duplicate abstractions, prevent notebook logic
  leaking into core, review interfaces. *Cannot write production code.*
- **Reverse-Engineering Agent** — analyze notebook structure, extract the workflow graph,
  identify dependencies. Produces architecture reports.
- **Implementation Agent** — build modules against *approved* interfaces. *Cannot create
  new interfaces.*
- **Verification Agent** — compare notebook vs platform outputs (geometry, dataset, model,
  optimization).

**Rules:** no coding before architecture review · every sub-phase = spec + tests +
validation + docs · no feature implemented directly in a notebook · all logic in reusable
modules · notebook only calls APIs.

---

## 9. Explicit future extensions (deferred — do NOT build here)

Deferred out of Phase 1, with the phase that owns them:

| Deferred item | Owned by |
|---|---|
| MOM Capacitor | Phase 2 (v0.1) |
| HV optimization · V_br / E_max estimation | Phase 2 (v0.1) |
| FastCap (electrostatic solver) | Phase 2 (v0.1) |
| FastHenry | Phase 7 (v1.0, inductor) |
| Generalized ngspice integration | Phase 4 (v0.3) |
| CCIA validation | Phase 4 (v0.3) |
| BMS-AFE validation | later (post-v1.0, master §6.3) |

> Phase 1 exists **solely** to establish platform infrastructure. Future passive
> structures must reuse Phase 1 interfaces unchanged.

---

## Related
- `00 Master PRD.md` §6 (architecture), §10 (roadmap), §11 (invariants)
- `Phase 2 — MOMCap & HV Compliance.md` — the phase that consumes these interfaces first
- Golden source: [[DOC-tcoil-0001]] · claims `300 digest/Claims/DOC-tcoil.jsonl`
- Concepts: [[Passive-Active Co-Design Workflow]] · [[T-Coil GDSII Generator]] ·
  [[ANN Surrogate Model]] · [[CMA-ES Inverse Design]] · [[EM Simulation]]
