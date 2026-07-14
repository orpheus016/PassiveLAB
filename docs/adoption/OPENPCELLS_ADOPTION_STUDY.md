# Adoption study: openPCells for spec-driven PCell generation

> **Status: study only — not adopted.** Decision input for a future ADR (tracked as the board task
> *spec.json entry format + loader/CLI*, and a later PCell-export task). Written during sub-phase
> 1.2.2; the mapping is against the fixed core interfaces. openPCells is **not** a dependency.

## Why it comes up

The **analog / IC designer** archetype's journey is: *write a spec → run a script → get PCells
usable in xschem (or any schematic/layout editor) → later run inverse design.* Two gaps sit outside
1.2.2's interfaces:
1. a **spec entry point** (a `spec.json` + loader/CLI) that produces a `PassiveSpec`;
2. a **PCell / xschem export** path from a generated `Layout` (L9 circuit integration).

openPCells ([patrickschulz/openPCells](https://github.com/patrickschulz/openPCells)) is a mature,
spec-driven, PDK-aware parametric layout/PCell generator (Lua) — prior art the Master PRD already
lists (`OpenPCELL`, "auto-PCell target").

## Where it would touch our interfaces

| openPCells concept | PassiveLab seam | Fit |
|---|---|---|
| Cell definition + parameters | `PassiveSpec` (`passive_type` + params) | conceptual match |
| `pcell` generation → layout | `LayoutGenerator.generate(spec) -> Layout` | a candidate backend implementation |
| Technology/PDK files | our (deferred) PDK-stackup handling | complementary — openPCells is PDK-aware |
| Export (GDS, and toward PCell/schematic) | `Layout` → PCell/xschem export (L9) | fills the designer's output gap |

## Options

1. **Adopt as a generator backend.** A `LayoutGenerator` implementation delegating to openPCells for
   passives it supports.
   - Pro: PDK-aware, mature, spec-driven — squarely the designer journey.
   - Con: Lua runtime + interop; unclear IHP SG13G2 coverage; our chosen backend for the T-coil is
     already **gdstk** (decided in 1.1.3), so openPCells would be an *additional* backend, not a
     replacement.
2. **Learn-from for the `spec.json` schema.** Borrow openPCells' spec/parameter conventions to design
   our `spec.json` + loader (which yields a `PassiveSpec`), keep generation on gdstk for now.
   - Pro: gets the designer a real entry point without a Lua dependency; consistent with the gdstk
     decision; low risk.
   - Con: doesn't get us openPCells' PCell/PDK machinery for free.
3. **Defer entirely.** Ship the `spec.json` loader against our own minimal schema; revisit openPCells
   when a second PDK-aware backend is genuinely needed.

## Recommendation (for the ADR to decide)

Lean **Option 2 (learn-from for the spec schema now; keep gdstk as the generator)** — it unblocks the
designer's `spec.json → generate` entry without adding a Lua runtime or contradicting the 1.1.3 gdstk
decision. Keep Option 1 open for later PDK-aware passives (aligns with the deferred glayout note in
`DEC-1-1-3-…`). The **PCell/xschem export** (L9) is a separate, later task regardless.

## Open questions for the ADR

- Does openPCells support **IHP SG13G2** (our target PDK)? If not, Option 1's PDK-awareness benefit
  shrinks to the same "manual stackup" gdstk already does.
- Lua ↔ Python interop cost vs. value.
- Is the `spec.json` schema better anchored on openPCells, on the tcoil notebook's parameter table,
  or on a neutral minimal schema?

## References
- Interfaces this maps onto: `src/passivelab/core/geometry/` (`spec.py`, `generator.py`).
- `docs/CORE_INTERFACE_DESIGN.md`; `docs/GENERATOR_BACKEND_RECOMMENDATION.md` (gdstk decision);
  Master PRD §5 (prior art). Related board tasks: spec.json loader/CLI; PCell + xschem export.
