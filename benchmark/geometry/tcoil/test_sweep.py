"""Parameter sweep validated against the golden notebook's own sampling distribution (sub-phase
1.3.4). Run on demand (excluded from the fast gate, like the rest of `benchmark/`):

    pytest benchmark/geometry/tcoil/test_sweep.py -v -s

See `geometry/tcoil/sampling.py`'s module docstring for why this validates against the notebook's
*sampling* procedure rather than diffing against a live gdspy run (gdspy can't be installed here --
archived, no Windows wheel, already rejected as a dependency in the 1.1.3 ADR -- and the committed
notebook has no cached reference output to diff against either, checked directly: cell 10's
`outputs: []`).

The validate/generate/render/report loop itself now lives in `scripts/sweep.py::run_sweep()` (the
sweep-as-a-feature refactor promoted it out of this test into a real, reusable feature) -- this
test just calls it with the notebook-faithful sampler's output, keeping the identity that's
actually specific to this file: it's the notebook-fidelity regression, not the report-writing
mechanism. Writes `sweep_out/report.json` (sample count, TAP-exercised rate, rules.py-pass rate)
and GDS+PNG for one illustrative case per distinct (nseg, includepad) combination encountered, for
manual visual inspection -- not all N samples, to keep this fast and the output directory small.
"""
from __future__ import annotations

import pathlib

from passivelab.geometry.tcoil.sampling import sweep
from passivelab.scripts.sweep import run_sweep

N_SAMPLES = 200
SEED = 1337
OUT_DIR = pathlib.Path(__file__).parent / "sweep_out"
MAX_RENDERS = 12


def test_sweep_matches_notebook_sampling_fidelity():
    report = run_sweep(list(sweep(N_SAMPLES, SEED)), OUT_DIR, seed=SEED, max_renders=MAX_RENDERS)

    print(f"\n[sweep] {N_SAMPLES} samples: "
          f"tap_exercised_rate={report['tap_exercised_rate']:.1%} "
          f"rules_pass_rate={report['rules_pass_rate']:.1%} "
          f"rules_failure_fields={report['rules_failure_field_counts']}")

    # The notebook-fidelity assertion (finding 1, see sampling.py's docstring): the notebook's own
    # Tapseg Check retries sampling until the tap branch would fire, so every sample here should
    # make our generator exercise it too. A failure here is a real generator/sampler bug, not an
    # expected discrepancy (unlike rules_pass_rate, which is deliberately not asserted on).
    assert report["tap_exercised_rate"] == 1.0, (
        f"expected 100% TAP-exercised (the notebook's Tapseg Check guarantees this); got "
        f"{report['tap_exercised_rate']:.1%} -- see sweep_out/report.json for the failing samples"
    )
