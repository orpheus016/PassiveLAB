"""Parameter sweep validated against the golden notebook's own sampling distribution (sub-phase
1.3.4). Run on demand (excluded from the fast gate, like the rest of `benchmark/`):

    pytest benchmark/geometry/tcoil/test_sweep.py -v -s

See `sweep.py`'s module docstring for why this validates against the notebook's *sampling*
procedure rather than diffing against a live gdspy run (gdspy can't be installed here -- archived,
no Windows wheel, already rejected as a dependency in the 1.1.3 ADR -- and the committed notebook
has no cached reference output to diff against either, checked directly: cell 10's `outputs: []`).

Writes `sweep_out/report.json` (sample count, TAP-exercised rate, rules.py-pass rate) and
GDS+PNG for one illustrative case per distinct (nseg, includepad) combination encountered, for
manual visual inspection -- not all N samples, to keep this fast and the output directory small.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
from collections import Counter

import gdstk
import pytest

from benchmark.geometry.tcoil.sweep import sweep
from passivelab.core import generate
from passivelab.geometry.tcoil.templates import ALL_LAYERS, PORT_START

N_SAMPLES = 200
SEED = 1337
OUT_DIR = pathlib.Path(__file__).parent / "sweep_out"
PDK_LAYER_DATATYPES = {(layer, 0) for layer in ALL_LAYERS}
MAX_RENDERS = 12


def test_sweep_matches_notebook_sampling_fidelity(tmp_path):
    OUT_DIR.mkdir(exist_ok=True)

    try:
        from passivelab.geometry.preview import render_png
    except ImportError:
        render_png = None  # `viz`/`bench` extra not installed; report still gets written

    rendered_combos: set[tuple[int, bool]] = set()
    results = []
    tap_exercised = 0
    rules_pass = 0
    rules_failure_fields: Counter[str] = Counter()

    for i, spec in enumerate(sweep(N_SAMPLES, SEED)):
        entry = {"index": i, "params": dataclasses.asdict(spec)}

        try:
            spec.validate()
            entry["rules_pass"] = True
            rules_pass += 1
        except ValueError as e:
            entry["rules_pass"] = False
            entry["rules_error"] = str(e)
            for field in ("sizX", "sizY", "wid", "gap", "nseg", "tapratio", "endratio",
                          "tapseg", "pad_siz", "Lext"):
                if f"{field}=" in str(e):
                    rules_failure_fields[field] += 1

        # Generate regardless of rules_pass: generate_tcoil()/core.generate() don't call
        # validate() themselves (the established "callers validate before generating"
        # convention) -- the point of this sweep is checking generation against the notebook's
        # *real* distribution, which sometimes falls outside our current rules.py ranges
        # (finding 2 in the 1.3.4 plan); gating on rules_pass would hide exactly that.
        layout = generate(spec)
        polys = layout.cell.get_polygons()
        entry["polygon_count"] = len(polys)
        inventory = {(p.layer, p.datatype) for p in polys}
        entry["layer_legal"] = inventory <= PDK_LAYER_DATATYPES

        ports_cell = layout.metadata["ports_cell"]
        tap_present = any(p.layer == PORT_START + 2 for p in ports_cell.get_polygons())
        entry["tap_exercised"] = tap_present
        if tap_present:
            tap_exercised += 1

        combo = (spec.nseg, spec.includepad)
        if render_png is not None and combo not in rendered_combos and len(rendered_combos) < MAX_RENDERS:
            rendered_combos.add(combo)
            stem = OUT_DIR / f"nseg{spec.nseg}_pad{spec.includepad}"
            lib = gdstk.Library()
            lib.add(layout.cell)
            lib.write_gds(str(stem.with_suffix(".gds")))
            render_png(layout.cell, stem.with_suffix(".png"),
                      title=f"nseg={spec.nseg} includepad={spec.includepad}")
            entry["rendered"] = True
        else:
            entry["rendered"] = False

        gds_path = tmp_path / f"sweep_{i}.gds"
        lib = gdstk.Library()
        lib.add(layout.cell)
        lib.write_gds(str(gds_path))
        read_back = gdstk.read_gds(str(gds_path))
        entry["gds_round_trip_ok"] = len(read_back.top_level()[0].get_polygons()) == len(polys)

        results.append(entry)
        assert entry["layer_legal"], (
            f"sample {i} produced a foreign layer: {inventory - PDK_LAYER_DATATYPES}"
        )
        assert entry["gds_round_trip_ok"], f"sample {i} failed a GDS round trip"

    report = {
        "n_samples": N_SAMPLES,
        "seed": SEED,
        "tap_exercised_rate": tap_exercised / N_SAMPLES,
        "rules_pass_rate": rules_pass / N_SAMPLES,
        "rules_failure_field_counts": dict(rules_failure_fields),
        "cases": results,
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[sweep] {N_SAMPLES} samples: "
          f"tap_exercised_rate={report['tap_exercised_rate']:.1%} "
          f"rules_pass_rate={report['rules_pass_rate']:.1%} "
          f"rules_failure_fields={report['rules_failure_field_counts']}")

    # The notebook-fidelity assertion (finding 1, see sweep.py's docstring): the notebook's own
    # Tapseg Check retries sampling until the tap branch would fire, so every sample here should
    # make our generator exercise it too. A failure here is a real generator/sampler bug, not an
    # expected discrepancy (unlike rules_pass_rate, which is deliberately not asserted on).
    assert report["tap_exercised_rate"] == 1.0, (
        f"expected 100% TAP-exercised (the notebook's Tapseg Check guarantees this); got "
        f"{report['tap_exercised_rate']:.1%} -- see sweep_out/report.json for the failing samples"
    )
