# Benchmark: `geometry/tcoil`

Mirrors `src/passivelab/geometry/tcoil/` 1:1 — this is the benchmark-ecosystem stub for the
platform's third archetype, the **algorithm developer** (Master PRD §3: "Benchmark optimization
algorithms fairly"; §8 "Benchmark philosophy"). Later sub-phases (1.4 solver backends, 1.7
optimizer backends: Optuna vs. Nevergrad vs. pymoo vs. BoTorch) reuse the same pattern under
`benchmark/geometry/<device>/` or a new top-level `benchmark/<layer>/<what>/` as those layers
land.

## Pattern

- A benchmark script sits directly next to its own `_report.md` (e.g.
  `benchmark_generation_speed.py` + `benchmark_generation_speed_report.md`) — evidence lives
  beside the code that produced it, no separate `results/` indirection.
- Timing uses **[pytest-benchmark](https://pytest-benchmark.readthedocs.io/)** — a pytest
  plugin, not hand-rolled timing code (reuse over new infrastructure). It integrates with the
  existing pytest setup and produces comparable Min/Max/Mean/StdDev tables.
- Deliberately **not** part of the fast CI gate (`pyproject.toml`'s `testpaths` excludes
  `benchmark/`) — timing is noisy on shared runners and isn't a pass/fail signal; run it
  on demand.
- **ASV (airspeed velocity)** is a documented option for later, once there's enough commit
  history to make historical regression tracking worthwhile (Master PRD §9's "golden-layout
  regression" CI philosophy) — not needed yet with one device and one backend.

## Running it

```bash
pip install -e ".[dev,bench]"
pytest benchmark/ --benchmark-only          # timing only
pytest benchmark/geometry/tcoil/benchmark_generation_speed.py -v -s   # + GDS size prints
```

`preview.py` is a small matplotlib-based GDS renderer (no KLayout GUI needed) used to generate
the PNGs in `previews/` for visual sanity-checking generator output.
