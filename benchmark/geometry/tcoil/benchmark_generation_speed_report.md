# T-coil generation in gdstk — benchmark report

> Deliverable for Phase 1 sub-phase **1.1.2** (`docs/PRD/Phase 1 — TCoil Platformization.md`
> §5). Feeds sub-phase **1.1.3**'s ADR-backed backend recommendation. All numbers below are
> from a real run in `../PassiveLAB/.venv` (`gdstk 1.0.0`) on 2026-07-13, not placeholders.

## 1. Valid GDS (literal validation criterion)

`generate_tcoil()` produces a `gdstk.Cell`; written via `gdstk.Library.write_gds()` and read
back via `gdstk.read_gds()` — round-trip confirmed identical polygon count and cell name.
CI-enforced: `src/passivelab/geometry/tcoil/tests/test_generator.py::test_gds_round_trip`.

## 2. All 11 parameters genuinely wired

`TCoilParams` (`wid, gap, sizX, sizY, firY, tapseg, nseg, tapratio, endratio, Lext, pad_siz`) —
every field, perturbed independently from the notebook's own smoke-test vector, measurably
changes the output geometry (full polygon-coordinate fingerprint, not just bounding box —
`tapratio`/`endratio`/`firY`/`tapseg` only shift *interior* coordinates without changing the
bounding box, since the ground plane's fixed extent dominates it). CI-enforced:
`test_generator.py::test_all_eleven_params_wired` (11 parametrized cases, all pass).
`pad_siz` was hardcoded to `50` inside the notebook's own `CreateTCoilTraceVanilla`; promoted
to an explicit field here so it's genuinely one of the 11, not baked in.

## 3. Generation speed

`pytest-benchmark`, `benchmark_generation_speed.py`, real run:

| Case | Min (µs) | Mean (µs) | Max (µs) | StdDev (µs) | Rounds |
|---|---|---|---|---|---|
| `nseg=24` (wid=5, gap=8) | 290.9 | 339.8 | 782.4 | 76.1 | 2557 |
| `nseg=10` (wid=7, gap=12, the notebook's own vector) | 348.6 | 375.4 | 695.9 | 27.3 | 1616 |

(Re-measured after the endratio-segment fix below — one extra polygon per generation,
negligible effect on timing.)

Sub-millisecond generation for a single T-coil either way. The notebook's Stage 3 batches
thousands of samples (`TOOLS_AND_ARTIFACTS.md` Stage 3 row) — at ~0.3–0.4 ms/sample, 5,000
samples is on the order of 2 seconds of pure geometry generation (EM simulation, not geometry,
is the actual bottleneck at that stage — consistent with the notebook needing Ray + a
1024-core cluster specifically for the *simulation* step, not generation).

## 4. Need for hacks/workarounds — confirmed directly

**None found.** Every generation call in this session created its own `gdstk.Library()` /
`gdstk.Cell` — dozens of times across the test suite and benchmark runs, in-process, with no
special handling. This is a structural difference from gdspy's `gdspy.library.
use_current_library = False` workaround (`NOTEBOOK_CELL_MAP.md` cell 10; needed 6× across the
notebook, otherwise a kernel restart is required — a known upstream gdspy bug). gdstk's
explicit, non-global `Library` object design avoids the class of bug entirely.

**Bonus finding, not in the original comparison matrix:** attempted to `pip install gdspy` in
this same environment for a live side-by-side cross-check (not as a project dependency — just
verification). It **failed to build**: gdspy ships no prebuilt Windows wheel and needs to
compile a C extension, which requires Microsoft Visual C++ Build Tools (not installed here).
gdstk installed cleanly with a prebuilt wheel. This directly corroborates what you'd already
found hard to install, and is a second, independent maintainability signal beyond
1.1.1's `gh api` archived-repo finding.

## 5. Output GDS file size

| Case | Polygons | File size |
|---|---|---|
| `nseg=10` (notebook vector) | 312 | 20,736 bytes |
| `nseg=24` | 208 | 14,480 bytes |

Note: polygon/file-size count does **not** scale monotonically with `nseg` alone — it depends
more on via-array density (`wid`/`gap` ratio) than turn count, since `_combine_layer` merges
overlapping same-layer polygons before writing. Not a bug; a real characteristic worth knowing
before assuming "more turns = bigger file" when estimating storage for a full 5,000-sample
batch generation run.

## 6. Visual verification

**Two real bugs found and fixed after review** (caught by comparing a KLayout render of the
committed `.gds` against the golden notebook's own reference diagram, and by inspecting the
octagon preview closely):

- **Missing endratio-controlled segment.** The notebook's own documentation diagram
  ("Seg9 (Blue)", length = `[endratio] * maxlen_Seg9`, `Tap_segid=4` — exactly this report's
  test vector) shows the *last* coil segment (`tid == nseg-1`) should draw a visible trace
  before its perpendicular `Lext` lead-out. Re-checking the ported source
  (`reference/markdown/TCoil_Dataset_Generator_and_Training.md`, the `if tid == nseg - 1:`
  branch) confirmed it computes that segment's path (`tmp_list`) to derive the lead-out
  coordinates but never draws it — unlike the non-last-segment branch just below, which does.
  Ported faithfully from the source at first; the notebook's own diagram confirms it's a real
  completeness gap, not a stylistic omission. **Fixed**: added the missing
  `shape_list.append(gdstk.FlexPath(tmp_list, wid, layer=thick_metals[cur_metal], ...))` in all
  4 directional cases of that branch (`generator.py`). Verified directly: for the baseline
  vector the new polygon is the brown segment at x∈[134.5,141.5], y∈[8.5,63.5] — it now bridges
  what was previously a floating, disconnected orange lead-out bar. Polygon count 311 → 312
  (exactly one new shape, as expected — only one of the 4 cases fires per generation).
- **Octagon ring corners not connected** (bonus/exploratory `octagon_variant.py` only — the
  validated rectangular T-coil was unaffected). The original implementation stroked a
  `gdstk.FlexPath` around the octagon vertices; FlexPath's mitering didn't close cleanly at the
  45°/135° corners, leaving gaps. Looked at
  [dgrujic/pcLab](https://github.com/dgrujic/pcLab)'s `pclab/pclGeom.py::octSegment()` (on
  request) — it confirms the right general approach: octagon rings must be built as **explicit
  closed polygons**, never stroked paths; pcLab hand-derives one 8-point polygon per quadrant
  (with extra ground-contact/bridge details this demo doesn't need). **Fixed** with a simpler
  version of the same idea: each ring is now `gdstk.boolean(outer_octagon, inner_octagon,
  "not", ...)` — the same annulus-via-boolean-difference technique already used successfully in
  `templates.create_ground_plane` — structurally gapless since it's a polygon operation, not a
  stroke.

Both previews re-rendered and re-inspected after the fixes: `previews/tcoil_rect.png` (the
notebook's own `nseg=10` vector — octagon pad, ground-plane cutout, the now-connected
double-layer outer ring — at `nseg=10`, `id_turn` only reaches `0`/`1` since it increments every
*two* full 4-segment turns, so both thick-metal layers legitimately route the same outer loop
before the spiral steps inward, matching "top-two thick metals for the coil" in the PRD, not a
bug) and `previews/tcoil_octagon.png` (now a clean, fully-connected multi-ring octagonal
spiral with a central pad).

## 7. Determinism

`test_generator.py::test_determinism` — identical `TCoilParams` produce byte-for-byte identical
polygon geometry across repeated calls. Feeds the "golden-layout regression" CI philosophy
(Master PRD §9) for whenever that's built out.

## 8. Parameter-range validation

`rules.py::validate()` implements the PRD's range table (`sizX`/`sizY` ∈[20,200], `wid`∈[3,12],
`gap`∈[6,24], `nseg`∈[2,24], `tapratio`∈[30,80]%, `endratio`∈[20,80]%, `0 ≤ tapseg < nseg`).
**Contradiction noted, not silently resolved** (citation rule): the PRD table lists `pad_siz`/
`Lext` as *fixed* (50µm/5µm), but the notebook's own function defaults to `Lext=20` and its own
smoke-test call uses `Lext=30` — neither matches "fixed". `rules.py` validates both as positive
numbers rather than enforcing the PRD's stated fixed values, since the notebook's actual
proven-working usage contradicts them. Worth resolving explicitly in 1.1.3 or 1.3.

## Porting notes (answers 1.1.1's open question: "gdstk T-coil port cost")

Mechanical, not a redesign — confirms the matrix's expectation. API differences hit:

| gdspy | gdstk |
|---|---|
| `gdspy.Rectangle(...)` (class) | `gdstk.rectangle(...)` (lowercase free function) |
| `gdspy.FlexPath(...).to_polygonset()` | `gdstk.FlexPath(...)` added to the cell directly |
| `gdspy.boolean(a, b, op, ...)` (returns one object) | `gdstk.boolean(a, b, op, ...)` (returns a **list**) — every spot the notebook did `shape_list.append(boolean_result)` needed `shape_list += boolean_result` instead |
| `cell.get_polygons((layer, dt))` | `cell.get_polygons(layer=layer, datatype=dt)` |
| `cell.remove_polygons(lambda pts, layer, dt: ...)` | `cell.remove(*polygon_objects)` — predicate replaced with fetch-then-remove |
| `gdspy.library.use_current_library = False` global workaround | not needed — explicit `Library()` objects |

Full port: `src/passivelab/geometry/tcoil/{generator.py,templates.py}`, ~230 lines, one sitting.

## Summary for 1.1.3

gdstk reproduces the golden notebook's T-coil faithfully (same coordinates, same parameters,
valid GDS, sub-millisecond generation), needs no gdspy-style workaround, and the one thing that
made a live gdspy comparison impossible here — its Windows build requirement — is itself
further evidence against gdspy, on top of 1.1.1's archived-repo finding. One completeness bug
was caught in review (§6, the missing endratio segment) and fixed before this report was
finalized — worth noting for 1.1.3 as a reminder that a mechanical port still needs the same
"compare against the reference diagram, not just the source" scrutiny gdspy code itself would.
