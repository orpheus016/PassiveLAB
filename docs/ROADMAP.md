# PassiveLab — ROADMAP

> Repo doc. Mirrors **Master PRD §10** (`../00 Master PRD.md`) and the phase index
> (`../01 Phase Index & Roadmap.md`). Phases map to versions; each phase PRD implements one
> row and cites the long-term goal it advances.

## Versions

```
v0.0  TCoil Platformization     — reproduce the golden notebook through reusable APIs
v0.1  MOMCap                    — first new passive on the shared interfaces + HV compliance
v0.2  PassiveCharLib           — the reusable characterized-library asset
v0.3  CCIA Benchmark           — system validation loop + benchmark fairness
v0.4  Bayesian Optimization    — pluggable optimizers on the benchmark harness
v0.5  ANN Surrogate (general)  — surrogate layer generalized beyond tcoil
v1.0  Inductor Plugin          — multi-passive proof; interfaces hold across types
```

Beyond v1.0: **v2.0** multi-PDK · **v3.0** optimization-algorithm benchmarking.

## Phase ↔ version status

| Phase | Version | Focus | PRD | Status |
|---|---|---|---|---|
| 1 | v0.0 | TCoil platformization | `../Phase 1 — TCoil Platformization.md` | detailed · **active** |
| 2 | v0.1 | MOMCap + HV compliance | `../Phase 2 — MOMCap & HV Compliance.md` | detailed |
| 3 | v0.2 | PassiveCharLib | _stub_ | planned |
| 4 | v0.3 | CCIA Benchmark | _stub_ | planned |
| 5 | v0.4 | Bayesian Optimization | _stub_ | planned |
| 6 | v0.5 | ANN Surrogate (general) | _stub_ | planned |
| 7 | v1.0 | Inductor Plugin | _stub_ | planned |

## Success metrics

- **v0** — generate a MOM cap automatically · characterize automatically · optimize
  automatically · demonstrate improvement inside CCIA.
- **v1.0** — support multiple passive types.
- **v2.0** — support multiple PDKs.
- **v3.0** — support benchmarking of optimization algorithms.

## Current milestone

**Phase 1 (v0.0) — TCoil platformization.** Reproduce the tcoil notebook workflow
`Parameters → Geometry → GDS → openEMS → Dataset → ANN → CMA-ES` through PassiveLab's
reusable APIs, with the notebook reduced to a demonstration frontend that only calls APIs.

## See also
- `../01 Phase Index & Roadmap.md` — full phase map + stubs + phase-PRD template
- `../00 Master PRD.md` §10 · `ARCHITECTURE.md` · `AGENTS.md`
