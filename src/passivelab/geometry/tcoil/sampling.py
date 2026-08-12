"""Faithful port of the golden notebook's own T-coil parameter-sampling procedure (sub-phase
1.3.4, relocated from `benchmark/geometry/tcoil/sweep.py` in the sweep-as-a-feature refactor --
this is tcoil-domain math, same as `generator.py`'s polygon assembly, not `scripts/`'s business).
`one_sample()`, `reference/markdown/TCoil_Dataset_Generator_and_Training.md:724-751`. Pure Python
(no gdspy), so it's the strongest notebook-fidelity check achievable in an environment where
gdspy can't be installed (archived upstream, no Windows wheel -- see
docs/GENERATOR_COMPARISON_MATRIX.md, and the 1.1.3 ADR that rejected it as a dependency): instead
of diffing generated geometry against a live gdspy run, this replicates the notebook's *real*
parameter distribution and checks our generator holds up against it -- a stronger fidelity signal
than an arbitrary independent-range grid, since several notebook params are *derived* rather than
independently sampled.

The "Tapseg Check" retry loop below (`while True: ... continue`) is provably the same condition
as `generator.py`'s `flag_add_tap` union-of-cases under `if tid == tapseg:` -- the notebook
retries until it draws a `tapseg` that would fire that branch, so every sample this function
produces should make our generator emit a TAP port marker. See
`benchmark/geometry/tcoil/test_sweep.py` for the notebook-fidelity regression that asserts this.

sizX/sizY: the derivation formula lives in `rules.size_bounds()`, not duplicated here -- `rules.py`'s
own `validate()` needs the identical formula, so it's the shared home for both callers.

`includepad`/`pad_siz` are the two fields the notebook's `one_sample()` always hardcodes
(`True`/`50`); exposed here as keyword args (same defaults) so `scripts/sweep.py`'s spec.json-driven
feature can pin them without touching the notebook-faithful distribution of every other field.
"""
from __future__ import annotations

import random
from collections.abc import Iterator

from passivelab.geometry.tcoil.rules import size_bounds
from passivelab.geometry.tcoil.spec import TCoilSpec


def sample_tcoil_spec(rng: random.Random, *, includepad: bool = True,
                       pad_siz: float = 50) -> TCoilSpec:
    """One notebook-faithful random T-coil sample. Field-by-field citations to the notebook's
    `one_sample()` (line numbers in `reference/markdown/...md`):

    - wid/gap (728-729): gap is wid + jitter, not independently drawn.
    - nseg (730): only 6 discrete values -- {2, 6, 10, 14, 18, 22} -- not a continuous range.
    - tapseg (731) + the Tapseg Check (734-737): retried until the tap branch would fire.
    - sizX/sizY (739-740): derived from nturn/gap/wid + jitter (`rules.size_bounds()`), not an
      independent [20,200] range.
    - tapratio/endratio (741-742): independently uniform, matches rules.py's ranges.
    - firY (743-744): a *ratio* of sizY, not an independent absolute coordinate.
    - Lext (745): gap + 5, not independently positive.
    - includepad/pad_siz: hardcoded by the notebook (`True`/`50`) -- pinnable here, not randomized.
    """
    while True:
        wid = rng.randint(3, 12)
        gap = wid + rng.randint(3, 12)
        nseg = rng.randint(0, 5) * 4 + 2
        tapseg = rng.randint(0, nseg // 4) * 4

        cur_metal = ((tapseg // 4) + 1) % 2
        id_turn = tapseg // 8
        tapseg_ok = (
            cur_metal == 0
            or cur_metal == 1
            and (id_turn == (nseg - 1) // 8 and nseg - 1 - tapseg < 4
                 or id_turn == 0
                 or id_turn == (nseg - 1) // 8)
        )
        if not tapseg_ok:
            continue

        size_lo, _ = size_bounds(wid, gap, nseg)
        sizX = size_lo + rng.randint(0, 100)
        sizY = size_lo + rng.randint(0, 100)
        tapratio = rng.uniform(0.3, 0.8)
        endratio = rng.uniform(0.2, 0.8)
        firY = int(sizY * rng.uniform(0.1, 0.9))
        Lext = gap + 5
        break

    return TCoilSpec(wid=wid, gap=gap, sizX=sizX, sizY=sizY, firY=firY, tapseg=tapseg, nseg=nseg,
                     tapratio=tapratio, endratio=endratio, Lext=Lext, pad_siz=pad_siz,
                     includepad=includepad)


def sweep(n: int, seed: int, *, includepad: bool = True, pad_siz: float = 50) -> Iterator[TCoilSpec]:
    """`n` notebook-faithful samples from a seeded RNG -- reproducible from a single command."""
    rng = random.Random(seed)
    for _ in range(n):
        yield sample_tcoil_spec(rng, includepad=includepad, pad_siz=pad_siz)
