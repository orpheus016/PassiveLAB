"""Cross-device layout validity + timing, with a brief structured JSON report (sub-phase 1.3.3).

Parametrized generically over every device's registered benchmark cases
(`benchmark.geometry.registry.all_cases()`) -- device-agnostic on purpose, so a second passive
(MoM Cap, Phase 2) only needs its own `cases.py`, not a change here. Only imports T-coil's cases
module for its registration side effect; nothing here names "tcoil" beyond that one import.

Validity checks here are deliberately generic (spec validates, generation succeeds, GDS round-
trips) -- PDK layer-legality is device-specific and already covered where it belongs
(`geometry/tcoil/tests/test_layers.py`).

Uses the `benchmark` fixture (pytest-benchmark) so `--benchmark-only` includes this test, matching
the existing benchmark commands -- but computes its own min/mean/max/stddev via a plain timing
loop rather than reading pytest-benchmark's internal stats object, so the JSON schema here doesn't
depend on that plugin's version internals.
"""
from __future__ import annotations

import statistics
import time

import gdstk
import pytest

import benchmark.geometry.tcoil.cases  # noqa: F401 -- self-registers "tcoil"'s benchmark cases
from benchmark.geometry.registry import all_cases
from passivelab.core import generate

_TIMING_REPS = 20


def _flattened_cases():
    for passive_type, cases in all_cases().items():
        for case in cases:
            yield passive_type, case.id, case.spec


def _ids(case_tuple):
    passive_type, case_id, _spec = case_tuple
    return f"{passive_type}-{case_id}"


_CASES = list(_flattened_cases())


@pytest.mark.parametrize("passive_type,case_id,spec", _CASES, ids=[_ids(c) for c in _CASES])
def test_generation_is_valid_and_reports_performance(benchmark, passive_type, case_id, spec,
                                                      report_collector, tmp_path):
    spec.validate()  # must not raise for a benchmark vector

    layout = benchmark(generate, spec)  # times it once; also makes --benchmark-only include this
    polys = layout.cell.get_polygons()
    valid = len(polys) > 0

    lib = gdstk.Library()
    lib.add(layout.cell)
    gds_path = tmp_path / f"{passive_type}_{case_id}.gds"
    lib.write_gds(str(gds_path))
    gds_bytes = gds_path.stat().st_size
    read_back = gdstk.read_gds(str(gds_path))
    assert len(read_back.top_level()) == 1
    assert len(read_back.top_level()[0].get_polygons()) == len(polys)

    timings_s = []
    for _ in range(_TIMING_REPS):
        start = time.perf_counter()
        generate(spec)
        timings_s.append(time.perf_counter() - start)
    timing_us = {
        "min": round(min(timings_s) * 1e6, 1),
        "mean": round(statistics.mean(timings_s) * 1e6, 1),
        "max": round(max(timings_s) * 1e6, 1),
        "stddev": round(statistics.stdev(timings_s) * 1e6, 1) if len(timings_s) > 1 else 0.0,
        "rounds": len(timings_s),
    }

    report_collector.append({
        "passive_type": passive_type,
        "case_id": case_id,
        "valid": valid,
        "polygon_count": len(polys),
        "bounding_box": layout.cell.bounding_box(),
        "gds_bytes": gds_bytes,
        "timing_us": timing_us,
    })

    assert valid
