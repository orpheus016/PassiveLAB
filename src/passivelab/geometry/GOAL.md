# Goal: `src/passivelab/geometry/`

Each passive device type gets its own folder here:

```
geometry/<device>/
  spec.py            # ALL of this device's parameters: the params dataclass (e.g. TCoilParams)
                     # plus the PassiveSpec-conforming wrap (dataclass inheritance) that adds
                     # `passive_type` + `validate()` (delegates to rules.validate, unmodified).
                     # Keeping params here — not in generator.py — is what keeps generator.py
                     # pure generation logic (see tcoil/spec.py for the pattern).
  generator.py        # ONLY the orchestrating generate_<device>(params) function — pure
                     # generation logic, no data definitions. Type-hints against the params
                     # dataclass via a TYPE_CHECKING-guarded import from spec.py (avoids a
                     # runtime import cycle: spec.py needs rules.py at runtime for validate()).
  templates.py         # reusable geometry primitives specific to this device (via arrays, pads,
                       # ground planes, ...) — the building blocks generator.py assembles
  rules.py              # parameter validation (PRD-specified range checks on the spec's numbers,
                        # NOT design-rule/DRC checking against a PDK deck — that's a separate,
                        # layout-level concern, deferred; see the PassiveLAB board's DRC task);
                        # validate(params) raises on out-of-spec values. Type-hints against the
                        # params dataclass the same TYPE_CHECKING way as generator.py, for the
                        # same reason.
  plugin.py              # the LayoutGenerator-conforming wrap; calls the device's own
                        # generate_<device>() unmodified, wraps the result in a core.types.Layout
  tests/                 # functional/correctness tests for this device, co-located
```

Dependency direction within a device folder: `generator.py` → `spec.py` → `rules.py` (one-way).
`spec.py` needs `rules.validate` as a *real* runtime import (to implement `TCoilSpec.validate()`);
`generator.py` and `rules.py` only need the params dataclass for a type hint, so those go under
`if TYPE_CHECKING:` — real imports there would create a cycle (`spec → rules → spec`).

Each device is independent — MOMCap's `rules.py` has nothing to do with T-coil's, and neither
should need to touch the other's `templates.py`. That's the point: parallel development across
device types (MOMCap, spiral inductor, transformer, resistor, ...) without one device's code
blocking another's.

**TODO — do not build this yet:** once a *second* device lands (MOMCap, Phase 2) and shows what
generation logic is genuinely shared across devices (e.g. layer/polygon helpers, coordinate
transforms, PDK-stackup reading), extract it into `geometry/common/`. Not built now — with only
one device (`tcoil/`) there's nothing proven to be shared yet, and guessing the shared surface
from a single example risks getting it wrong (Phase 1 PRD §3: "do not generalize prematurely").

`passivelab/__init__.py` stays deliberately empty (no public API guessed ahead of sub-phase
1.2's architecture review) — the per-device folders here are real, working code, wrapped behind
the approved `LayoutGenerator`/`PassiveSpec` interfaces, not throwaway code.

**tcoil is done** (sub-phase 1.2.3): `tcoil/spec.py` + `tcoil/plugin.py` are the wrap, verified by
a same-geometry regression against `generate_tcoil()` (`tcoil/tests/test_plugin.py`) and driven
end-to-end through `passivelab.core` in `tests/test_tcoil_core_integration.py`. `TCoilParams` was
later relocated from `generator.py` into `spec.py` (this folder-shape doc's own recommendation) —
`generator.py`/`rules.py` only changed by an import line each (real → `TYPE_CHECKING`-guarded); no
generation or validation *logic* changed, re-confirmed by the same regression test staying green.
This is the pattern the next device (MOMCap, Phase 2) repeats from the start.
