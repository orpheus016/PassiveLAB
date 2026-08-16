# Port / reference-plane / de-embedding convention (sub-phase 1.4.2)

> Deliverable for board task **1.4.2** (`Projects/PassiveLAB_tasks/
> 1.4.2-port-definition,-reference-plane-and-de-embedding-conv.md`). Non-blocking for the Phase-1
> DoD, but cheap now and expensive once a dataset exists without it — this pins down *where the
> ports are* and *what has (or hasn't) been de-embedded*, the single most common silent reason two
> EM datasets of the same structure disagree.

## Why this exists

Neither the Master PRD nor the reference paper's future-work section addresses this. The golden
notebook encodes it only implicitly, in geometry (`PORT_START`/`PORT_LENGTH` constants and where
the port markers happen to sit). `characterization/openems/ports.py`'s module docstring and
`docs/OPENEMS_BACKEND.md` both explicitly deferred generalizing it to this task. This document plus
the `PortDef` fields it's backed by (`reference_plane_offset`, `de_embedded`) make the convention
data, not tribal knowledge.

## Port placement

Every T-coil port is a **vertical via port**, defined in
`characterization/openems/ports.py::_PORT_METAL_CONVENTION`:

| Port | GDS layer (`PORT_START + n`) | From metal | To metal | Optional? |
|------|-------------------------------|------------|----------|-----------|
| PAD  | 201                           | Metal4     | TopMetal2| No        |
| TAP  | 202                           | Metal4     | Metal5   | Yes — only if the sampled geometry hits `generator.py`'s `flag_add_tap` condition |
| CIR  | 203                           | Metal4     | Metal5   | No        |

`PORT_START` (200) itself is never used to tag geometry — it is only the base of the 4-layer block
(`geometry/tcoil/templates.py`). `geometry/tcoil/generator.py::split_ports()` strips these
openEMS-only marker layers out of the PDK-facing `Layout.cell` into
`Layout.metadata["ports_cell"]`; `characterization/openems/ports.py::merge_layout_for_solver()`
re-unions them back into the GDS actually handed to the solver. Ports are **renumbered contiguously
by presence** (1..N in layer order), not by `layernum - PORT_START` — see `derive_port_definitions()`
for why (an absent TAP port must not leave a numbering gap).

## Reference plane

Each port box is offset **`PORT_LENGTH` = 4 microns** from the via array / ground-trace transition
(`geometry/tcoil/templates.py::PORT_LENGTH`, duplicated in `ports.py` for the same
no-geometry-import reason as `PORT_START`). The vendored solver has **no separate calibration or
subtraction step**: `util_simulation_setup.addPorts_to_CSX()` builds
`FDTD.AddLumpedPort(...)` directly at that port-box location, and
`util_utilities.calculate_Sij()` computes `S_ij = CSXport_i.uf_ref / CSXport_j.uf_inc` reading
straight off that same box.

**The reference plane is therefore the port box itself** — 4 microns from the via, not at the via,
not at the pad, not at any external calibration plane. Every `SimulationResult` from this backend
carries `reference_plane_offset` on each port entry (and a human-readable summary under the
top-level `port_convention` key) so this is legible from the data alone, not just this document.

## De-embedding

**None is applied.** There is no calibration structure (open/short/thru), no post-solve
subtraction, and no reference-plane shift anywhere in `characterization/openems/`. The raw
S-parameters written to the `.s{n}p` file include whatever parasitics sit between the port box and
the physical via/pad — this is a real, consistent limitation of the current pipeline, not an
oversight to paper over.

`PortDef.de_embedded` is `False` for every port from every run today. The field exists (rather than
being omitted) so that if de-embedding is ever implemented, a de-embedded run is distinguishable
from every prior raw-reference-plane run **by metadata alone** — the explicit validation bar this
task was given.

## Port impedance normalization

`port_Z0 = 50 Ω`, resistive, for every port — matches the golden reference
(`simulator_openems.py`'s `simulation_port` calls) and is echoed as `port_z0` on both the per-port
`PortDef` entries and the top-level `port_convention` summary.

## Where this is stamped

- Per-port: `SimulationResult.raw["ports"][i]` — `PortDef._asdict()`, includes
  `reference_plane_offset`, `de_embedded`, `port_z0` alongside the existing port fields.
- Summary: `SimulationResult.raw["port_convention"]` — `{"reference_plane": ..., "de_embedding":
  "none applied", "port_z0": 50.0}`, so a reader doesn't need to cross-check every port entry to
  know the convention a dataset row was produced under.

## Scope

This document is **T-coil-specific**, matching `ports.py`'s existing `_PORT_METAL_CONVENTION` (also
T-coil-specific, copied verbatim from the golden reference). Generalizing a port/reference-plane
convention across passive types — should PassiveLAB grow beyond T-coils — is future work, not this
task's scope (same "don't design past a sample of one" reasoning as `geometry/GOAL.md`).

This document does **not** implement de-embedding. Building an actual calibration/subtraction
pipeline (open-short-thru or similar) is a substantially larger feature than declaring the existing
convention explicit, and is not what 1.4.2 asked for.

## See also

- `characterization/openems/ports.py` — `PortDef`, `_PORT_METAL_CONVENTION`,
  `derive_port_definitions()`.
- `docs/OPENEMS_BACKEND.md`'s "Port re-embedding" section.
- Board task **1.4.8** (notebook S-parameter equivalence check) — cites this document so "same
  S-parameters as the notebook" is a claim about a stated reference plane, not an assumption.
