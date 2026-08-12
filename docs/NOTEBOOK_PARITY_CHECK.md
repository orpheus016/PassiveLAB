# Notebook-Sample Parity Check: `sweep_out` previews vs. `one_sample()`'s own output

> Deliverable for the pre-1.4 review/refactor pass (James's request, alongside the sibling
> `sizX/sizY` rules fix). James compared `benchmark/geometry/tcoil/sweep_out/*.png` against the
> golden notebook's own dataset-sample images and the shapes looked a bit off. This doc records
> the investigation and its conclusion: **no generator/template code change** -- see "Root cause"
> below. Per this repo's citation rule, disagreements are recorded, not silently resolved; this
> is that record.

## What was compared

Not the exploratory octagon variant (`benchmark/geometry/tcoil/octagon_variant.py`, explicitly
out of scope, confirmed with James) -- the real comparison is between:

- **`benchmark/geometry/tcoil/sweep_out/*.png`** — previews rendered from
  `benchmark/geometry/tcoil/sweep.py`'s notebook-faithful parameter sampler (sub-phase 1.3.4),
  driven through the real `passivelab.core.generate` -> `TCoilLayoutGenerator` -> `generate_tcoil`
  path.
- **The golden notebook's own dataset-sample images**, `PNG/10.png`..`PNG/14.png`, as displayed by
  the notebook's own cell 15 (`from IPython.display import Image, display`, sourced from
  `one_sample()`'s dataset-generation batch,
  `reference/python/TCoil_Dataset_Generator_and_Training.py:730-786`). These are real embedded
  outputs saved inside the committed `.ipynb` (`display_data` cells with `image/png`), extracted
  here for the first time and checked into
  [`notebook_samples/`](../benchmark/geometry/tcoil/notebook_samples/) as
  `one_sample_10.png`..`one_sample_14.png`.

## Method

1. **Code-level check first.** Traced `generate_tcoil()`
   (`src/passivelab/geometry/tcoil/generator.py`) against the notebook's real
   `CreateTCoilTraceVanilla` (`reference/python/TCoil_Dataset_Generator_and_Training.py:318-499`)
   case-by-case: the `if tid == nseg-1: ... else: ...` main-loop branches (last-segment ports, the
   three `tapseg`-branch `elif`s, the shared trailing trace). Semantically equivalent -- the only
   structural difference is *where* the trailing `FlexPath(tmp_list, ...)` append sits (inlined
   per-`case` here vs. once after the whole `if/else` in the notebook, source line 499), which is
   provably identical output since only one `case` executes per iteration either way. Also
   compared `templates.py`'s `create_octagon_points`/`create_via_array`/`create_ground_plane`
   against the notebook's `CreateOctagonPoints`/`CreateViaArray`/`CreateGroundPlane`: formulas are
   copied verbatim.
2. **Then a real image comparison**, since a line-by-line code read can't catch a renderer-level
   discrepancy (e.g. gdstk vs. gdspy `FlexPath` corner/cap-style defaults). `gdspy` itself can't be
   installed here for a live side-by-side run -- no Windows wheel, already rejected as a
   dependency in the 1.1.3 ADR (`docs/GENERATOR_BACKEND_RECOMMENDATION.md`) -- so this compares
   our renderer's output against the notebook's *own* already-rendered output instead.

## What the images show

| | Image | Topology |
|---|---|---|
| Our generator | [`previews/tcoil_rect.png`](../benchmark/geometry/tcoil/previews/tcoil_rect.png) (`wid=7,gap=12,sizX=150,sizY=120,firY=10,tapseg=4,nseg=10,...,includepad=True` -- the notebook's own smoke-test vector) | octagon pad -> bent feed connector -> ~2-turn rectangular trace -> ground-plane cutout window, port ticks, tap via square |
| Notebook, `PNG/10.png`..`14.png` | [`notebook_samples/`](../benchmark/geometry/tcoil/notebook_samples/) | octagon pad -> bent feed connector -> 1-3 turn rectangular trace (turn count varies per sample) -> ground-plane cutout window, port ticks, tap via square |

Same topology in both: octagon bond pad, an L-shaped feed connector into the coil, a rectangular
concentric-turn spiral trace, a rectangular ground-plane cutout, small port-marker ticks at the
trace ends, and a via-array square at the tap. No structural divergence found.

**Limitation, recorded rather than worked around:** `one_sample()`'s RNG is never seeded (checked
directly -- the only `random.seed()`/`torch.manual_seed()` call in the whole reference script is
`torch.manual_seed(42)` for the later ML training, not the geometry sampler), so indices 10-14's
*exact* parameters aren't recoverable from the code. This comparison is topology-level, not a
pixel/coordinate diff against known params.

## Root cause of "looks a bit off"

Not a generator bug. `sweep_out/report.json` (pre-fix) showed a **21% rules-fail rate**
(`rules_pass_rate: 0.79`, every failure on `sizX`/`sizY`) -- a chunk of the sweep's own
notebook-faithful samples produced `sizX`/`sizY` well above what `rules.py` allowed at the time
(up to 327 vs. an independent `[20, 200]`). Those large/disproportionate cases are legitimate
notebook-distribution output, but next to the compact real dataset samples above and the small
hand-picked smoke-test case, a handful of the rendered `sweep_out` previews are unusually
large/sparse relative to their coil -- which is what read as "off". Root cause: `rules.py`
validated `sizX`/`sizY` against an independent flat range that was never the notebook's actual
generative constraint, not a flaw in `generate_tcoil()` itself.

Fixed in the sibling task: `rules.py` now derives the `sizX`/`sizY` bound from
`3*(nturn*gap)+wid+jitter[0,100]` (the notebook's real formula, via `rules.size_bounds()`), and
the 200-sample sweep's `rules_pass_rate` went from 79.0% to **100.0%** after the fix.

## Flagged, not actioned (out of this task's scope)

- **`nseg` is only ever `{2, 6, 10, 14, 18, 22}`** in the real sampler
  (`nseg = randint(0,5)*4 + 2`), never any value in `rules.py`'s flat `TOTAL_SEG_RANGE=(2,24)`.
  Same category of rules-vs-generation gap as the `sizX`/`sizY` fix, but James's ask this pass was
  specifically `sizX`/`sizY` -- noted here as a lead if a tighter `nseg` check is wanted later.
- **`gap` is derived from `wid`** (`gap = wid + randint(3,12)`), not drawn independently -- but
  this happens to already fall inside `rules.py`'s existing `GAP_RANGE=(6,24)` for every possible
  `wid`, so no discrepancy to act on.

## Conclusion

`generate_tcoil()`/`templates.py` are a faithful port; no generator/template change made. The
apparent divergence traced to the `sizX`/`sizY` rules-vs-generation gap, already fixed in the
sibling task, verified by the sweep's `rules_pass_rate` going to 100%.

## Related

- [`GENERATOR_COMPARISON_MATRIX.md`](GENERATOR_COMPARISON_MATRIX.md) / 
  [`GENERATOR_BACKEND_RECOMMENDATION.md`](GENERATOR_BACKEND_RECOMMENDATION.md) — the gdstk
  adoption decision and why a live `gdspy` comparison isn't possible in this environment.
- [`CORE_ABSTRACTION_VALIDATION.md`](CORE_ABSTRACTION_VALIDATION.md) — same "record the
  comparison, don't just assert the conclusion" pattern, one layer up.
- `benchmark/geometry/tcoil/sweep.py` / `sweep_out/report.json` — the notebook-faithful sampler
  and its regenerated pass-rate report.
