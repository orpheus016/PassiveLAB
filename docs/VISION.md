# PassiveLab — VISION

> Repo doc. The full product spec is the **Master PRD** (`../00 Master PRD.md`); this file
> is the short, durable "why". If the two disagree, the Master PRD wins.

## One line

PassiveLab is **OpenROAD for passive structures** — an open-source platform that turns a
passive **specification** into a generated, characterized, optimized, and benchmarked
layout, PDK-agnostic, with the research-platform clarity of OpenDPD.

## The problem

Chip designers — especially on open PDKs — hit the same wall:

- **Missing primitives.** The passive a circuit needs isn't in the PDK (e.g. GF180MCU
  ships no inductors).
- **Slow characterization.** EM / TCAD / field solvers are the bottleneck of the design
  loop.
- **No GDS → PCell path.** Getting a generated structure into the EDA as a usable PCell is
  hand-coded, every time.
- **A manual, spreadsheet-driven loop.** Draw → extract → sweep → maintain spreadsheets,
  all by hand.

Nobody is building open passive-structure generation *as a platform*. That gap is the
product.

## What we're building

Instead of drawing and characterizing passives by hand, the user states a spec and
PassiveLab automatically:

```
Generate geometry → Characterize performance → Store in a reusable library
                  → Optimize structure → Benchmark optimization algorithms
```

It platformizes three proven pieces — the **tcoil inductor notebook** (the golden
reference), the **pcLab** generator, and **OpenPCELL** generation — behind clean,
stable interfaces.

## Who it's for

Three archetypes, each a first-class user:

1. **Analog / IC designer** — state `target_value`, `max_area`, `min_voltage_margin` →
   get an optimized, implementable passive.
2. **Device researcher** — state a parameter sweep → get datasets and characterization.
3. **Algorithm developer** — bring an optimization algorithm → get a fair benchmark score
   against baselines.

## Principles

- **Files/specs over apps.** A `PassiveSpec` is the single source of truth; everything
  downstream is derived.
- **Reuse before build.** Integrate OSS → wrap APIs → adapters → new code only when
  unavoidable.
- **Human-first *and* AI-friendly.** Readable and specifiable without the tool; automatable
  with it.
- **Modular & PDK-agnostic.** Run only the steps you need; assume no specific PDK.
- **No optimization without characterization.** Fair, physics-grounded results only.

## North star

Make creating a trustworthy, implementable passive structure for *any* PDK a matter of
stating a spec — and make benchmarking the algorithms that optimize them fair, open, and
reproducible.

## See also
- `../00 Master PRD.md` — full spec · `ROADMAP.md` · `ARCHITECTURE.md` · `AGENTS.md`
