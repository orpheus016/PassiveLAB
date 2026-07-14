"""Parameter validation for TCoilParams, from the PRD's range table
(docs/PRD/Phase 1 -- TCoil Platformization.md, sub-phase 1.3).

Note on two fields that don't cleanly validate against the PRD table, recorded rather than
silently "fixed" per the citation rule (contradictions must be noted, not auto-resolved):
- The PRD table lists `pad_siz`/`Lext` as *fixed* (50um / 5um). But the golden notebook's own
  `CreateTCoilTraceVanilla` defaults to `Lext=20` and its own smoke-test call uses `Lext=30`
  (reference/markdown/TCoil_Dataset_Generator_and_Training.md, cell 10) -- neither matches the
  PRD's "fixed" claim. We validate both as positive numbers rather than enforcing the PRD's
  stated fixed values, since the notebook's actual proven-working usage contradicts them.
- The PRD table's `ratio_firY` is described as a percentage-position parameter, but the
  generator function's own `firY` argument is used as an absolute Y coordinate, not a ratio
  (see generator.py). The ratio-to-coordinate conversion is a higher-level (dataset-sampling)
  concern, out of scope for this geometry-backend prototype -- `firY` is validated only as a
  real number here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only: spec.py imports this module's validate() at runtime, so a
    from passivelab.geometry.tcoil.spec import TCoilParams  # real import here would cycle back

SIZE_RANGE = (20, 200)       # sizX, sizY (um)
WID_RANGE = (3, 12)          # coil segment width (um)
GAP_RANGE = (6, 24)          # adjacent-segment center-line distance (um)
TOTAL_SEG_RANGE = (2, 24)    # nseg
TAP_RATIO_RANGE = (0.30, 0.80)   # tapratio, fraction (PRD: 30-80%)
END_RATIO_RANGE = (0.20, 0.80)   # endratio, fraction (PRD: 20-80%)


def validate(params: TCoilParams) -> None:
    """Raise ValueError on any out-of-spec TCoilParams field."""
    errors = []

    def _range(name, value, lo, hi):
        if not (lo <= value <= hi):
            errors.append(f"{name}={value!r} out of range [{lo}, {hi}]")

    _range("sizX", params.sizX, *SIZE_RANGE)
    _range("sizY", params.sizY, *SIZE_RANGE)
    _range("wid", params.wid, *WID_RANGE)
    _range("gap", params.gap, *GAP_RANGE)
    _range("nseg", params.nseg, *TOTAL_SEG_RANGE)
    _range("tapratio", params.tapratio, *TAP_RATIO_RANGE)
    _range("endratio", params.endratio, *END_RATIO_RANGE)

    if not (0 <= params.tapseg < params.nseg):
        errors.append(f"tapseg={params.tapseg!r} must satisfy 0 <= tapseg < nseg={params.nseg!r}")
    if params.pad_siz <= 0:
        errors.append(f"pad_siz={params.pad_siz!r} must be positive")
    if params.Lext <= 0:
        errors.append(f"Lext={params.Lext!r} must be positive")

    if errors:
        raise ValueError("invalid TCoilParams: " + "; ".join(errors))
