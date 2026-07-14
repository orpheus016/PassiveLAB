# Goal: `src/passivelab/geometry/`

Each passive device type gets its own folder here:

```
geometry/<device>/
  generator.py    # the params dataclass + the orchestrating generate_<device>(params) function
  templates.py     # reusable geometry primitives specific to this device (via arrays, pads,
                    # ground planes, ...) — the building blocks generator.py assembles
  rules.py          # parameter validation (PRD-specified range checks on the spec's numbers,
                     # NOT design-rule/DRC checking against a PDK deck — that's a separate,
                     # layout-level concern, deferred; see the PassiveLAB board's DRC task);
                     # validate(params) raises on out-of-spec values
  spec.py            # the PassiveSpec-conforming wrap (dataclass inheritance from the device's
                     # own params — see tcoil/spec.py for the pattern); adds `passive_type` +
                     # `validate()` (delegates to rules.validate, unmodified)
  plugin.py           # the LayoutGenerator-conforming wrap; calls the device's own
                     # generate_<device>() unmodified, wraps the result in a core.types.Layout
  tests/             # functional/correctness tests for this device, co-located
```

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
a same-geometry regression against the unmodified `generate_tcoil()` (`tcoil/tests/test_plugin.py`)
and driven end-to-end through `passivelab.core` in `tests/test_tcoil_core_integration.py`. Zero
edits to `generator.py`/`rules.py`/`templates.py` — this is the pattern the next device (MOMCap,
Phase 2) repeats.
