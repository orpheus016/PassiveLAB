# PassiveLab — AGENTS.md

> **The file every coding agent reads first** (PassiveLab repo). This is *not* the vault's
> PKOS `AGENTS.md` — it governs work inside the **passivelab** codebase.
> Full spec: `../00 Master PRD.md`. Rules of structure: `ARCHITECTURE.md`.

## Mission

Build **PassiveLab** — OpenROAD for passive structures. Turn a `PassiveSpec` into a
generated, characterized, optimized, benchmarked passive, PDK-agnostic.

## Current milestone

**Phase 1 (v0.0) — TCoil platformization** (`../Phase 1 — TCoil Platformization.md`).
Reproduce the golden tcoil notebook through reusable APIs; the notebook becomes a
demonstration frontend that only calls APIs. Next: Phase 2 (v0.1) MOMCap.

## Architecture (the pipeline you build within)

```
Generator → Characterizer → Optimizer → Benchmark
```

**No module may bypass another module.** Dependency rule:

```
Optimization      may call   Characterization
Characterization  may call   Geometry
Geometry          may NOT call Optimization
```

The four stable core APIs — `generate(spec)`, `characterize(layout)`,
`optimize(objective)`, `evaluate(candidate)` — are a contract. See `ARCHITECTURE.md`.

## Do NOT

- Add new frameworks (reuse-first: OSS → wrap API → adapter → new code only if unavoidable).
- Create duplicate functions or abstractions.
- Change public interfaces / fork a core API. (If an interface seems insufficient, escalate
  to architecture review — do not fork.)
- Put logic in a notebook. Notebooks may **only call APIs**.
- Let a passive-specific detail leak into core — passives live in plugins.
- Let optimization see anything that didn't go through characterization.

## ALWAYS

- Write tests. Keep golden data current (e.g. `golden_data/*_reference.json`).
- Update docs (`VISION.md` / `ARCHITECTURE.md` / `ROADMAP.md` and the relevant phase PRD).
- Reuse existing modules.
- No coding before architecture review. Every sub-phase needs: specification · tests ·
  validation criteria · documentation.
- Cite sources for physical/characterization claims; record disagreements, never
  auto-resolve them.

## Workflow (per phase)

1. Read `../01 Phase Index & Roadmap.md` → find the **active phase**.
2. Read **Master PRD §10–§11** (roadmap + invariants) for long-term context.
3. Read the active **phase PRD**; execute **only** its scope. Deferred items stay deferred
   until a later phase's PRD claims them.
4. Architecture review → spec → tests → implement against approved interfaces → validate →
   docs.

## Agent roles

- **Architecture Reviewer** — detect duplicate abstractions, prevent notebook/plugin logic
  leaking into core, review interfaces, own phase gates. *Cannot write production code.*
- **Reverse-Engineering Agent** — analyze existing notebooks/tools, extract workflow graphs,
  identify dependencies. Produces reports.
- **Implementation Agent** — build modules against approved interfaces. *Cannot create new
  interfaces.*
- **Verification Agent** — compare outputs (geometry, dataset, model, optimization) against
  the reference; validate DRC/LVS cleanliness and equivalence.

## CI (every PR runs)

```
lint · unit tests · example notebook · golden-layout regression
```

## See also
- `VISION.md` · `ARCHITECTURE.md` · `ROADMAP.md`
- `../00 Master PRD.md` · `../01 Phase Index & Roadmap.md`
