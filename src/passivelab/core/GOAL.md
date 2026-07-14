# Goal: `src/passivelab/core/`

The **stable platform contract**: the four core APIs and the seven interfaces behind them. Agents
extend PassiveLab by writing plugins that satisfy these interfaces — **never by editing them**
(Master PRD §11 invariant 3; `docs/ARCHITECTURE.md`). If an interface seems insufficient, escalate
to an architecture review, don't fork it.

## The four core APIs

```
generate(spec)       -> Layout      (L1-L3   geometry)
characterize(layout) -> Metrics     (L4-L7   characterization)
optimize(objective)  -> Candidate   (L8      optimization)
evaluate(candidate)  -> Score        (L9-L10  benchmark)
```

Dependency rule (never reversed): `optimization → characterization → geometry`. No optimizer ever
sees anything that didn't pass through characterization.

## The seven interfaces (this package)

| Interface | Sub-package | Backs |
|---|---|---|
| `PassiveSpec` | `geometry/spec.py` | input to `generate()` |
| `LayoutGenerator` | `geometry/generator.py` | `generate(spec) -> Layout` |
| `SimulationBackend` | `characterization/backend.py` | underlies `characterize()` |
| `DatasetPipeline` | `characterization/dataset.py` | feeds the surrogate |
| `ModelTrainer` (+ `Model`) | `characterization/surrogate.py` | fast surrogate for `characterize()` |
| `Optimizer` | `optimization/optimizer.py` | `optimize(objective) -> Candidate` |
| `ValidationRunner` | `benchmark/validation.py` | `evaluate(candidate) -> Score` |

Value types (the nouns that flow between them) live in `types.py`: `Layout`, `Metrics`,
`SimulationResult`, `Objective`, `Candidate`, `Score`, `Dataset`.

**Interfaces are `typing.Protocol` (structural), not ABCs.** A plugin or a third party conforms by
*shape*, without importing or subclassing anything from `passivelab` — this is what lets the
algorithm-developer archetype bring their own optimizer/solver.

## Archetype → API map (the anti-drift north star)

Every feature must serve at least one archetype (Master PRD §3 / `docs/VISION.md`). If a change
doesn't move one of these journeys, question it.

| Archetype | Wants | Uses (APIs) |
|---|---|---|
| **Analog / IC designer** | state an objective → get an optimized, implementable passive | `optimize` → `generate` (+ `evaluate`) |
| **Device researcher** | sweep & characterize topologies, build datasets | `generate` → `characterize` → dataset |
| **Algorithm developer** | benchmark an optimizer/algorithm fairly vs baselines | `optimize` + `evaluate` |

The archetype journeys are exercised end-to-end (with fakes) in `tests/test_archetypes.py` — that
suite is the living proof each journey stays expressible through these interfaces.

## In scope now (sub-phase 1.2.2)

Interface **shapes** + value types, unit-tested for shape and for zero device/geometry-kit
references (`core/tests/`). No logic, no backends, no dispatch.

## Deferred (do not build here / not yet)

- **The four named free-functions with dispatch** (`generate(spec)` that finds the right plugin) —
  needs a plugin registry, which needs a *second* caller to design against. Built in **1.3**
  (T-Coil plugin), when tcoil registers as the first real entry. Until then, callers inject the
  concrete implementation explicitly (as the archetype tests do).
- **Concrete backends** — real generators (1.2.3 wraps tcoil), solvers (1.4), dataset/ANN
  (1.5/1.6), optimizers (1.7), end-to-end (1.8).
- **External-tool adoption** — mlflow (tracking) and openPCells (spec/PCell) are studied in
  `docs/adoption/` and tracked as board tasks/ADRs, **not** adopted here.

## See also
- `docs/CORE_INTERFACE_DESIGN.md` — the approved design of record (vault: `DEC-1-2-1-…` /
  `ART-core-interface-design-0005`).
- `docs/ARCHITECTURE.md` · `docs/VISION.md` · `docs/PRD/00 Master PRD.md` §3, §6, §11.
- one `GOAL.md` per sub-package here for the per-API north star.
