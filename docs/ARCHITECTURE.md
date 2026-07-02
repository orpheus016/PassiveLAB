# PassiveLab — ARCHITECTURE

> Repo doc. The full architecture (all 10 layers, per-layer detail) lives in **Master PRD
> §6 and §11** (`../00 Master PRD.md`). This file is the enforceable contract a contributor
> or agent must not break.

## The stable core APIs

Four interfaces are the platform contract. **Extend behind them with plugins; never fork
them.**

```
Geometry:          generate(spec)       -> Layout
Characterization:  characterize(layout) -> Metrics
Optimization:      optimize(objective)  -> Candidate
Benchmark:         evaluate(candidate)  -> Score
```

## The layered pipeline

No layer may bypass the one below it.

```
L1  Intent            type, PDK, constraints, objectives, solver
L2  PassiveSpec       canonical schema — the ONLY entry to generation
L3  Generator         spec -> GDS + metadata + manifest   (gdstk / glayout / OpenFASOC / custom)
L4  Extraction        mesh, netlists, ports, boundary conditions
L5  Solver            FastCap / FastHenry / openEMS / ngspice / Xyce / Elmer   (plugin)
L6  Dataset           geometry+process+result features     (Parquet; no CSV except debugging)
L7  Surrogate         MLP / XGBoost / RF / GP -> (GNN, Transformer)
L8  Optimization      Optuna / Nevergrad / pymoo / BoTorch
L9  Circuit Integration   SPICE -> (Xschem, BAG, OpenVAF)
L10 System Validation     CCIA / BMS-AFE / RF-matching impact
```

## Dependency rule (must hold)

```
Optimization      may call   Characterization
Characterization  may call   Geometry
Geometry          may NOT call Optimization
```

Equivalently: `Generator → Characterizer → Optimizer → Benchmark`, and **no module may
bypass another module**. In particular, **no optimization module may bypass
characterization** — the optimizer only ever sees characterized/simulated metrics.

## Plugin model

- **Passive plugins** — MOMCap, SpiralInductor, Transformer, Resistor. Each provides a
  `PassiveSpec` specialization + a `generate(spec)` implementation. A new passive is a new
  plugin, **not** a core change.
- **Solver plugins** — every backend implements `simulate(job) -> SimulationResult`
  (electrostatic FastCap, magnetic FastHenry, EM openEMS, circuit ngspice/Xyce, field
  Elmer, future DEVSIM).
- **Applications** — CCIA / BMS-AFE / RF-matching benchmarks sit at L10.

## PassiveCharLib — the primary asset

The characterized library, not any single generator, is the durable value. It stores:
geometry parameters · layout metadata · capacitance · area · ESR · frequency response ·
extraction metadata · simulator metadata.

## Operating modes

- **Mode A — Library Generation.** `Target passive → Generate layout → Generate symbol →
  Generate SPICE`. (Builds a new PCell library.)
- **Mode B — Circuit Optimization.** `Import netlist → Identify passives → Link surrogate
  models → Optimize`. (The tcoil / ETH notebook flow.)

## Invariants (never violate)

1. `PassiveSpec` is the only entry to generation (no generator bypasses L2).
2. No optimization without characterization (L8 always goes through L5/L6).
3. The four core APIs are stable — extend via plugins, don't fork.
4. Reuse-first — new code only when unavoidable.
5. PDK-agnostic — no PDK-specific assumption leaks into core.
6. Human-first & AI-friendly — everything specifiable and readable without the tool.

## See also
- `../00 Master PRD.md` §6, §11 · `AGENTS.md` (rules) · `ROADMAP.md`
