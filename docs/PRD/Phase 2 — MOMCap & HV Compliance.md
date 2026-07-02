---
title: "PassiveLab Phase 2 — MOMCap & HV Compliance"
version: v0.1
role: phase PRD (agent-executable slice)
status: detailed
updated: 2026-07-03
master: "00 Master PRD.md"
depends_on: "Phase 1 — TCoil Platformization.md"
---

# Phase 2 — MOMCap & HV Compliance  ·  v0.1

**Subtitle:** First new passive on the shared interfaces + high-voltage compliance.

> **Agent, read this first.** This phase is only unlocked once **Phase 1's interfaces are
> stable and frozen**. Your job is to prove the abstraction by adding a *new* passive
> **through the existing interfaces** — not by touching core. Long-term context:
> `00 Master PRD.md` §10 (roadmap v0.1) and §11 (invariants).

---

## 1. Long-term context (why this phase exists)

Phase 2 delivers roadmap **v0.1** (master §10). Where Phase 1 proved the platform can
*reproduce* one notebook, Phase 2 proves the platform can *extend* to a **new passive
type it was never built for** — the MOM capacitor — **without changing the core APIs**.
This is the first real test of master invariant #3 (stable core APIs) and #5 (PDK-agnostic).

It also introduces the platform's first **domain-value goal beyond reproduction**:
**high-voltage compliance** for MOM caps — estimating **E_max** and **V_br** so the
optimizer can maximize an **HV score** (master §4.3, §6.1-L8). This is the seed for the
BMS-AFE / CCIA research thread that PassiveLab ultimately serves (master priorities).

**Success-metric alignment.** Phase 2 is what the master's **v0** success metric names
directly: *generate a MOM cap automatically → characterize automatically → optimize
automatically → demonstrate improvement inside CCIA*. Phase 2 delivers the first three;
the CCIA demonstration is scoped minimally here and matured in Phase 4.

---

## 2. Goal / Non-goals

**Goal.** Add a **MOMCap plugin** and an **electrostatic characterization path** so that a
user can state a MOM-cap spec and PassiveLab generates → characterizes → optimizes it,
including **HV metrics (E_max, V_br, HV score)** — all through the **Phase-1 interfaces,
unchanged**.

**Non-goals.**
- **No core-interface changes.** If a Phase-1 interface feels insufficient, that is a
  finding to escalate to the Architecture Reviewer — not a license to fork the API.
- No new PDK (multi-PDK is v2.0). Demonstrate on one PDK (GF180MCU is the motivating case
  — it ships no inductor and is the master's example gap).
- No full CCIA benchmark harness (that is Phase 4); Phase 2 does only a **minimal** L10
  sanity demonstration.
- No transformer/inductor plugins.

---

## 3. Core principle

```
Extend, don't rebuild.  New passive = new plugin + new solver plugin, nothing more.
Reuse-first (master §7): OSS tool → wrap API → adapter → new code (only if unavoidable).
Prove HV physics against a reference before trusting the surrogate.
```

---

## 4. Interfaces touched (all via master §6.2 — no forks)

| What Phase 2 adds | Master layer | Mechanism | Rule |
|---|---|---|---|
| `MOMCapSpec` | L2 | a `PassiveSpec` specialization | must round-trip through the same canonical schema |
| `MOMCapGenerator` | L3 | new plugin, implements `generate(spec)` | interdigitated-fingers geometry; GDS + metadata + manifest |
| **FastCap** backend | L5 (electrostatic) | new solver plugin, implements `simulate(job)` | first electrostatic solver; validates against it |
| HV metrics | L6/L8 | extend metric set, not the API | add `E_max`, `V_br`, `HV_score` as objectives |
| MOMCap surrogate | L7 | reuse Phase-1 `ModelTrainer` | no bespoke trainer |
| MOMCap optimizer task | L8 | reuse Phase-1 `Optimizer` | objectives: capacitance density, area, HV score |
| Minimal CCIA check | L10 | reuse `ValidationRunner` | single sanity metric, not full benchmark |

**Invariant check (master §11):** generation still enters only via `PassiveSpec` (#1);
optimization still runs through characterization (#2); the four core APIs are untouched (#3).

---

## 5. Sub-phases (ordered)

### 2.0 — Interface-fit review (gate)
Before any code: the Architecture Reviewer confirms MOMCap fits the Phase-1 interfaces.
Produce a short **fit report** listing exactly which interfaces MOMCap uses and proving no
new core API is required. **Validation:** MOMCap expressible through Phase-1 interfaces; if
not, escalate rather than fork. _No coding before this gate passes._

### 2.1 — MOMCap geometry plugin
Implement `MOMCapSpec` + `MOMCapGenerator` (interdigitated MOM fingers: finger width,
spacing, length, count, metal layers, PDK design rules). Output GDS + metadata + manifest.
**Validation:** generated layout is **DRC-clean** on the target PDK and parametrically
sweeps as specified.

### 2.2 — Electrostatic solver (FastCap)
Wrap **FastCap** as an L5 `SimulationBackend` plugin (extraction L4 → capacitance matrix).
**Validation:** capacitance estimate agrees with a reference (openEMS or analytic) within a
declared tolerance on a known geometry.

### 2.3 — HV characterization (E_max, V_br)
Add high-voltage estimation: extract peak field **E_max** from the field solution and
estimate breakdown voltage **V_br** / an **HV_score** from the dielectric stack. Document
the physical model and its assumptions (per master citation rules — every claim sourced;
disagreements recorded, not auto-resolved). **Validation:** E_max/V_br monotonic and sane
vs. spacing/voltage sweeps; matches reference where one exists.

### 2.4 — Dataset + surrogate (reuse Phase 1)
Run `DatasetPipeline` (Parquet) over MOMCap sweeps; train the MOMCap surrogate with the
**existing** `ModelTrainer`. **Validation:** surrogate predicts C and HV metrics within
tolerance; no new trainer code beyond a config/plugin.

### 2.5 — Optimization (reuse Phase 1)
Drive the **existing** `Optimizer` on MOMCap objectives: **maximize capacitance density,
maximize HV score, subject to area ≤ constraint** (master §6.1-L1 intent example).
**Validation:** optimizer improves the objective vs. a hand-picked baseline; no core change.

### 2.6 — Minimal CCIA sanity demonstration
Insert an optimized MOM cap into a **CCIA** context via `ValidationRunner` and show a
single top-level metric moves the right way (e.g. input-cap or gain sanity). This is a
**demonstration, not the benchmark** — the full CCIA harness is Phase 4.
**Validation:** end-to-end runs; metric direction is correct and reproducible.

---

## 6. Deliverables
1. Interface-fit report (2.0).
2. MOMCap plugin — `MOMCapSpec` + `MOMCapGenerator`, DRC-clean GDS (2.1).
3. FastCap `SimulationBackend` plugin (2.2).
4. HV characterization module (E_max, V_br, HV_score) + documented model (2.3).
5. MOMCap dataset (Parquet) + trained surrogate via existing trainer (2.4).
6. MOMCap optimization results vs. baseline (2.5).
7. Minimal CCIA demonstration report (2.6).

---

## 7. Definition of Done
A user states a MOMCap spec and PassiveLab, **through unchanged Phase-1 core APIs**,
produces a DRC-clean generated cap, characterizes it (C + E_max + V_br), optimizes it for
capacitance-density and HV score under an area constraint, and demonstrates the result
inside a minimal CCIA context. **Zero core-interface changes** — MOMCap lives entirely in
plugins.

---

## 8. Agent roles & rules
- **Architecture Reviewer** — owns the §2.0 gate; blocks any core-API fork; ensures MOMCap
  is plugin-only.
- **Implementation Agent** — builds the MOMCap + FastCap plugins against frozen interfaces.
- **Verification Agent** — validates DRC cleanliness, solver agreement, HV sanity, and the
  CCIA sanity metric.

**Rules (master §7 governance):** reuse-first; write tests + golden data
(`golden_data/momcap_reference.json`, master §9 CI); update docs; do not add frameworks;
do not change public interfaces.

---

## 9. Explicit future extensions (deferred)

| Deferred item | Owned by |
|---|---|
| Full CCIA benchmark harness + fairness scoring | Phase 4 (v0.3) |
| PassiveCharLib canonical schema for MOMCap data | Phase 3 (v0.2) |
| Bayesian / advanced optimizers on MOMCap | Phase 5 (v0.4) |
| Multi-PDK MOMCap | v2.0 |
| BMS-AFE system validation | later (master §6.3, post-v1.0) |

---

## Related
- `00 Master PRD.md` §4.3 (HV target), §6 (architecture), §10 (v0.1)
- `Phase 1 — TCoil Platformization.md` — interfaces this phase reuses unchanged
- `01 Phase Index & Roadmap.md` — Phase 3 (CharLib) & Phase 4 (CCIA) pick up the deferrals
- Concepts: [[PCELL]] · [[LVS]] · [[MOM Benchmark]]
