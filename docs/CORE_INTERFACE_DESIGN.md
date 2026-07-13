# Core Interface Design

> Deliverable for Phase 1 sub-phase **1.2 — Core abstraction extraction**, subtask **1.2.1**
> (`docs/PRD/Phase 1 — TCoil Platformization.md` §Phase 1.2). This is the architecture-review
> gate the PRD requires before any interface code is written ("No coding before architecture
> review") — written MADR-adjacent, like `docs/GENERATOR_BACKEND_RECOMMENDATION.md` (1.1.3), so
> it drops into the vault ADR (`DEC-core-interface-design`) the harvest loop scaffolds from this
> PR. Validation criterion (PRD): *T-Coil expressible entirely through these interfaces, with
> zero T-coil-specific code above the plugin boundary.*

**Status:** proposed · **Deciders:** James (human, approves the ADR); Claude (drafts the design)
· **Date:** 2026-07-14

---

## Context and problem statement

`docs/ARCHITECTURE.md` and `docs/AGENTS.md` already fix the platform's outer contract: the 4
stable core APIs (`generate/characterize/optimize/evaluate`), the L1–L10 layered pipeline, and
the dependency rule (`Optimization → Characterization → Geometry`, never reversed). What's still
missing is the layer *between* those two things: the 7 named interfaces the Phase 1 PRD calls out
(`PassiveSpec, LayoutGenerator, SimulationBackend, DatasetPipeline, ModelTrainer, Optimizer,
ValidationRunner`) as concrete Python contracts, plus the value types that flow between them
(neither ARCHITECTURE.md nor the PRD names these, but the 4 core APIs' own signatures reference
them as return types).

This can't be designed in the abstract: `src/passivelab/geometry/tcoil/` (1.1.2, gdstk chosen in
1.1.3's ADR) is already real, working code — `TCoilParams` (11 named fields) and
`generate_tcoil(params, ...) -> gdstk.Cell`. Sub-phase 1.2.3 retrofits this exact code behind
`PassiveSpec`/`LayoutGenerator` without changing its geometry logic, so the interfaces below are
checked against it directly, not designed on paper alone.

**Decision needed:** what are the 7 interfaces' shapes, what value types sit between them, and
what package layout do they live in — before 1.2.2 writes any code?

## Decision drivers

1. **No passive-specific API at the core level** (PRD, hard constraint) — nothing in `core/` may
   reference `tcoil`/`TCoilParams`/gdstk directly.
2. **The four core APIs are stable, don't fork them** (Master PRD §11 invariant 3) — the 7
   interfaces must compose *into* `generate/characterize/optimize/evaluate`, not replace them.
3. **Fits the target repo layout** (Master PRD §9): `core/{geometry, characterization,
   optimization, benchmark}/`.
4. **First reproduce, then abstract** (PRD core principle) — don't design further than what
   1.1.2's T-coil prototype and the golden notebook's own workflow already prove is needed.
5. **T-coil must be fully expressible through the result** — the PRD's explicit validation bar
   for 1.2, concretely checked against `TCoilParams`/`generate_tcoil()`.

## The 4 core APIs (fixed — not part of this decision)

```
generate(spec: PassiveSpec)       -> Layout
characterize(layout: Layout)      -> Metrics
optimize(objective: Objective)    -> Candidate
evaluate(candidate: Candidate)    -> Score
```

## Design: the 7 interfaces

| Interface | Layer | Backs | Shape |
|---|---|---|---|
| `PassiveSpec` | L1→L2 | input to `generate()` | Thin ABC/dataclass base: a `passive_type` discriminator + `validate() -> None`. Deliberately near-empty — `TCoilParams`'s 11 fields are entirely T-coil-specific, so the base must not guess shared fields from a sample of one (the same restraint `geometry/GOAL.md` already applied to defer `geometry/common/`). |
| `LayoutGenerator` | L3 | `generate(spec) -> Layout` | `generate(spec: PassiveSpec) -> Layout`. `Layout` wraps `{cell/GDS, metadata, parameter manifest}` — `generate_tcoil()` today returns a bare `gdstk.Cell`, so 1.2.3 *wraps* the existing function, it doesn't rewrite it. |
| `SimulationBackend` | L4–L5 | underlies `characterize()` | `simulate(layout: Layout) -> SimulationResult`. Extraction (mesh/netlists/ports/BCs) folds *into* each backend's `simulate()` rather than a separate L4 interface — extraction is inherently solver-specific (FastCap prep ≠ openEMS prep), so a universal `Extractor` would be a fake abstraction this early. |
| `DatasetPipeline` | L6 | feeds `ModelTrainer` | `append(spec, metrics) -> None`, `load() -> Dataset` (Parquet-backed, Master PRD §6.1). Not a nice-to-have: this is *why* `optimize()` can run fast — without it, every optimizer iteration pays for a slow EM/field-solver run (L5). Signature-only here; see [Deferred scope](#deferred-scope-flagged-not-silently-dropped). |
| `ModelTrainer` | L7 | supports `optimize()`'s surrogate | `train(dataset) -> Model`; `Model.predict(spec) -> Metrics`. Together with `DatasetPipeline` this is the surrogate that lets `Optimizer` iterate against a fast approximate `characterize()` instead of a slow EM solve each time (Master PRD L7: "replace expensive sims"). Signature-only here. |
| `Optimizer` | L8 | `optimize(objective) -> Candidate` | Ask-tell shape (matches Optuna/Nevergrad/pymoo/BoTorch, all ask-tell libraries): `ask() -> PassiveSpec`, `tell(candidate, score) -> None`. |
| `ValidationRunner` | L9–L10 | `evaluate(candidate) -> Score` | `evaluate(candidate: Candidate) -> Score`, internally must call `characterize()` first — never skip straight to a score (Master PRD §8). This is the **inverse-design evaluation interface**, paired with `Optimizer`: Master PRD §6.5 Mode B ("Import netlist → Identify passives → Link surrogate models → Optimize") *is* the golden notebook's own flow, and reproducing it is a named Phase 1 deliverable ("Reproduced optimization workflow"). The near-term concrete backend is the notebook's own circuit-level validation (1.7/1.8); CCIA/BMS-AFE are named **applications** built on the same interface *later* — the PRD's "Explicit Future Extensions" excludes those specific benchmarks, not the interface itself. |

### Shared value types (not named by the PRD, added here)

The PRD names the 7 verbs but not the nouns that flow between them, and the 4 core APIs'
own signatures already reference them as return types — without pinning these now, 1.2.2 would
invent them ad hoc and 1.2.3's retrofit would have nothing concrete to conform to:

```
Layout      -- {cell_or_gds, metadata: dict, parameter_manifest: dict}
Metrics     -- characterization results (capacitance, ESR, Q, S-params, ...)
Objective   -- what optimize() is asked to hit (target value, constraints)
Candidate   -- a PassiveSpec + its Metrics, as proposed by an Optimizer
Score       -- ValidationRunner's output for a Candidate
SimulationResult -- raw SimulationBackend output, reduced to Metrics by characterize()
```

### Plugin-dispatch seam (flagged, not built here)

Top-level `generate(spec)` must find `TCoilGenerator` without `core/` importing `tcoil/`
(importing it would violate "no passive-specific API at the core level"). The seam is a
registry — `passive_type str -> LayoutGenerator instance` — but it is **not built in 1.2.1**;
there's only one caller (`tcoil`) so far, and a registry designed against a sample of one risks
guessing wrong. 1.3 (T-Coil Plugin) builds the registry once T-coil registers into it as the
first real entry.

## Package layout

Fits Master PRD §9's `core/{geometry, characterization, optimization, benchmark}/` literally —
no 5th top-level folder:

```
src/passivelab/core/
  types.py              # Layout, Metrics, Candidate, Score, Objective, SimulationResult
  geometry/
    spec.py             # PassiveSpec (ABC)
    generator.py        # LayoutGenerator (ABC)
  characterization/
    backend.py          # SimulationBackend (ABC)
    dataset.py           # DatasetPipeline (stub)
    surrogate.py          # ModelTrainer (stub)
  optimization/
    optimizer.py          # Optimizer (ABC, ask-tell)
  benchmark/
    validation.py          # ValidationRunner (ABC)
```

`DatasetPipeline`/`ModelTrainer` sit under `characterization/` rather than a new `core/surrogate/`
folder: both exist to answer "how expensive is this candidate," the same question
`SimulationBackend` answers directly — a surrogate is just a fast approximation of
characterization, not a separate concern.

## Deferred scope (flagged, not silently dropped)

- **`DatasetPipeline`/`ModelTrainer`** get signatures only in 1.2.1/1.2.2, no logic, no
  in-memory fake — the notebook's dataset-generation and training cells haven't been
  reverse-engineered yet (that's Phase 1.5/1.6). Because these two interfaces are the reason
  `optimize()` avoids paying for a slow EM solve every iteration, this isn't an optional
  extra to quietly skip: a body note is added to the vault's **1.5 Dataset pipeline** and
  **1.6 ANN pipeline** board tasks recording "ingestion of the notebook's real dataset/training
  code" as required scope for those phases.
- **`ValidationRunner`'s named benchmark applications** (CCIA, BMS-AFE — the PRD's "Explicit
  Future Extensions") are deferred; the interface is not. 1.2.4's validation report should
  confirm T-coil is expressible through `ValidationRunner`'s interface and, once 1.7/1.8 land,
  through the notebook-equivalent optimization flow — not through CCIA/BMS-AFE, which stay out
  of Phase 1.
- **No 8th "Extractor" interface** for L4 — folded into each `SimulationBackend` (see table).
- **No concrete plugin registry** — flagged above, built in 1.3.

## Consequences

**Positive**
- Every one of the PRD's 7 named interfaces has a concrete Python shape, a layer, and a core-API
  mapping — 1.2.2 has nothing left to guess.
- `PassiveSpec`/`LayoutGenerator` are checked directly against `TCoilParams`/`generate_tcoil()`,
  so 1.2.3's retrofit is a wrap, not a redesign — no risk of accidentally changing T-coil
  geometry while fitting it to the interface.
- The fast-surrogate rationale for `DatasetPipeline`/`ModelTrainer` is recorded on the 1.5/1.6
  board tasks now, before the reasoning has a chance to be lost.

**Negative / accepted**
- `DatasetPipeline`, `ModelTrainer`, `SimulationBackend`, and `ValidationRunner` ship as
  interface shape only in this phase — no working backend exists until 1.4–1.8 land. `core/`
  is therefore not runnably complete after 1.2 alone; 1.2.4's validation report scopes its claim
  to "expressible through the interfaces," not "fully operational end-to-end."
- The plugin-dispatch registry is explicitly not designed here — 1.3 must budget time for it.

## Confirmation

- Every one of the 7 PRD-named interfaces appears above with a layer + core-API mapping; none
  dropped, none silently renamed.
- No interface signature references a T-coil-specific type (`TCoilParams`, `TCoilSpec`, etc.) —
  those stay in 1.3.
- Cross-read against `docs/ARCHITECTURE.md`, `docs/AGENTS.md`, and Master PRD §6/§9/§11: no
  contradictions found.
- `TCoilParams` (11 fields) and `generate_tcoil()`'s actual signature fit the `PassiveSpec`/
  `LayoutGenerator` shapes above — 1.2.3 can retrofit without changing T-coil geometry logic.

## Related

- `docs/ARCHITECTURE.md` — the 4-API / L1-L10 contract this design fills in.
- `docs/AGENTS.md` — architecture-review-before-code rule this doc satisfies.
- `docs/GENERATOR_BACKEND_RECOMMENDATION.md` — 1.1.3's decision this design builds on (gdstk).
- `src/passivelab/geometry/tcoil/` — the working code this design is checked against.
- `../00 Master PRD.md` §6 (architecture), §9 (repo structure), §11 (invariants).
- `docs/PRD/Phase 1 — TCoil Platformization.md` — Phase 1.2's scope and validation bar.
