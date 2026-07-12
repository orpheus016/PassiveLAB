# Goal: `src/passivelab/geometry/`

Each passive device type gets its own folder here:

```
geometry/<device>/
  generator.py    # the params dataclass + the orchestrating generate_<device>(params) function
  templates.py     # reusable geometry primitives specific to this device (via arrays, pads,
                    # ground planes, ...) — the building blocks generator.py assembles
  rules.py          # parameter validation (PRD-specified ranges / DRC-style constraints);
                     # validate(params) raises on out-of-spec values
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
1.2's architecture review) — the per-device folders here are real, working code that 1.2 wraps
behind the approved `LayoutGenerator` interface, not throwaway code.
