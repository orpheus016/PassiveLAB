---
title: "PassiveLab — Phase Index & Roadmap"
role: navigation / phase↔version map
status: living
updated: 2026-07-03
master: "00 Master PRD.md"
---

# PassiveLab — Phase Index & Roadmap

> **How to use this file.** This is the map between the **Master PRD** (`00 Master PRD.md`,
> the complete long-term source of truth) and the **per-phase PRDs** (what an AI agent
> consumes to execute one slice). Each phase PRD is self-contained *for execution* but
> **inherits its long-term goals from the master** — a phase is never allowed to redefine
> the vision, only to deliver a slice of it.

## Reading order for an agent
1. Read this index → find the **active phase**.
2. Read the **master §10–§11** (roadmap + invariants) for the long-term context.
3. Read the **active phase PRD** and execute only its scope.
4. Anything the phase defers → it stays deferred until a later phase's PRD claims it.

## Phase ↔ version map

| Phase | Version | Focus | PRD file | Status | Master goal advanced |
|---|---|---|---|---|---|
| **1** | v0.0 | TCoil platformization (reproduce golden notebook via reusable APIs) | `Phase 1 — TCoil Platformization.md` | **detailed** | Infrastructure / prove the platform |
| **2** | v0.1 | MOMCap + HV compliance (E_max, V_br) on the shared interfaces | `Phase 2 — MOMCap & HV Compliance.md` | **detailed** | First new passive; HV goal |
| 3 | v0.2 | PassiveCharLib — the reusable characterized-library asset | _stub_ | planned | Durable asset (master §6.4) |
| 4 | v0.3 | CCIA Benchmark — system validation + benchmark fairness | _stub_ | planned | L10 + §8 fairness |
| 5 | v0.4 | Bayesian Optimization — pluggable optimizers on the harness | _stub_ | planned | Optimizer plugins (L8) |
| 6 | v0.5 | ANN Surrogate (general) — surrogate layer beyond tcoil | _stub_ | planned | Generalize L7 |
| 7 | v1.0 | Inductor Plugin — multi-passive proof; interfaces hold | _stub_ | planned | Multi-passive; success metric v1.0 |

_Later: **v2.0** multi-PDK, **v3.0** optimization-algorithm benchmarking (master §10)._

## Future-phase stubs (not yet detailed — do **not** implement ahead of their PRD)

- **Phase 3 · PassiveCharLib (v0.2).** Promote the ad-hoc Phase-1/2 datasets into the
  canonical `PassiveCharLib` schema (master §6.4): geometry params · layout metadata ·
  C · area · ESR · frequency response · extraction + simulator metadata. Parquet-backed,
  queryable, the primary project asset. Precondition: Phase 1 `DatasetPipeline` stable.
- **Phase 4 · CCIA Benchmark (v0.3).** Stand up the first Layer-10 system-validation loop
  and the benchmark-fairness harness (master §8): a MOM cap flows into a CCIA and its
  gain/noise/BW/stability/power impact is scored. Precondition: Phase 2 MOMCap + metrics.
- **Phase 5 · Bayesian Optimization (v0.4).** Add BoTorch/Optuna optimizers behind the
  stable `optimize(objective)` API and score them on the Phase-4 benchmark. No interface
  change — optimizer is a plugin.
- **Phase 6 · ANN Surrogate, generalized (v0.5).** Lift the tcoil-specific MLP into a
  general `ModelTrainer`/surrogate layer usable by any passive (master L7).
- **Phase 7 · Inductor Plugin (v1.0).** Second passive family through the *unchanged*
  interfaces — the proof that the abstraction holds. Hits success metric v1.0.

## Phase PRD authoring template (for the stubs above)

Every phase PRD, when detailed, MUST contain these sections (Phases 1–2 are the worked
examples):

1. **Long-term context** — which master §10 row(s) and §11 invariants this phase serves;
   one paragraph tying the slice to the vision.
2. **Goal / Non-goals** — what "done" means; what is explicitly *out*.
3. **Core principle** — the discipline for this phase (e.g. reproduce→abstract→optimize).
4. **Interfaces touched** — which of the stable core APIs (master §6.2) + layers (§6.1)
   are extended; declare any new plugin surface. **No interface fork.**
5. **Sub-phases / tasks** — ordered, each with its own validation.
6. **Deliverables.**
7. **Validation / Definition of Done** — verifiable equivalence or acceptance criteria.
8. **Agent roles & rules** — which agents act; the do/don't for this phase.
9. **Explicit future extensions** — what this phase defers to which later phase.

## Related
- `00 Master PRD.md` — complete long-term source of truth
- `Phase 1 — TCoil Platformization.md`
- `Phase 2 — MOMCap & HV Compliance.md`
