# Benchmark: `geometry/`

```
geometry/<device>/     # per-device benchmark scripts + cases.py (see geometry/tcoil/README.md)
geometry/registry.py   # benchmark-case registry, keyed by passive_type (mirrors core's plugin
                       # registry one level down) -- each device's cases.py self-registers here
geometry/tests/        # cross-device validity + timing, generic over every registered device
```

## `geometry/tests/` — cross-device validity + performance (sub-phase 1.3.3)

`test_layout_validity_and_performance.py` iterates `registry.all_cases()` — every device that has
imported and registered its `cases.py` — and for each case: validates the spec, generates through
the real platform path (`passivelab.core.generate`, registry dispatch included), round-trips a
GDS write/read, and times it. Deliberately generic: no device-specific legality checks here (those
belong in that device's own `tests/`, e.g. `src/passivelab/geometry/tcoil/tests/test_layers.py`).

Uses the `pytest-benchmark` `benchmark` fixture (so `--benchmark-only` includes it, matching the
commands below) but computes its own min/mean/max/stddev via a plain timing loop, so the JSON
report's shape doesn't depend on that plugin's internal stats API.

**Output**: a brief structured `report.json` next to the test file (gitignored, regenerated every
run) — `{"generated_at", "cases": [{"passive_type", "case_id", "valid", "polygon_count",
"bounding_box", "gds_bytes", "timing_us": {"min","mean","max","stddev","rounds"}}]}`. This is the
quick "is the layout still valid, and how fast" signal after changing geometry code — no new
command to remember, it's a side effect of the same commands used for per-device timing:

```bash
pip install -e ".[dev,bench]"
pytest benchmark/ --benchmark-only
cat benchmark/geometry/tests/report.json
```

Adding a second device (MoM Cap, Phase 2) means adding `geometry/momcap/cases.py` that registers
its own vectors — no change to this test.
