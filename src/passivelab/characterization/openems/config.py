"""``openems.config.json -> OpenEMSConfig`` loader (sub-phase 1.4.1).

Flat JSON with a ``solver`` discriminator, mirroring ``scripts/sweep.py``'s ``SweepSpec``/
``load_sweep_spec()`` pattern one layer up (solver config instead of sweep config) -- and, like
``SweepSpec``, has no ``validate()``: these are solver knobs, not a device's geometric rules, so
there's no rules.py-style business validation to delegate to.

Every field default matches the golden reference's own hardcoded constants
(``simulator_openems.py``'s equivalent in the notebook: 0-100 GHz / 1001 points / PEC*6 boundaries
/ margin=200 / refined_cellsize=1.0 / cells_per_wavelength=20 / energy_limit=-50 dB /
merge_polygon_size=1.5 / preprocess_gds=True) -- this config schema is what turns those notebook
constants into backend config, per 1.4.1's own deliverable text, without silently changing any of
them.

Deliberately has no ``gpu`` field: openEMS has no supported GPU/CUDA path, so a reserved-but-inert
flag here would be dead weight. A future GPU-capable solver plugin would carry its own ``gpu``
field on its own config schema -- solver configs are per-solver, not shared (matches
``core/characterization/GOAL.md``: extraction/solver setup is inherently solver-specific).
"""
from __future__ import annotations

import dataclasses
import pathlib

from passivelab.core.geometry.spec_loader import read_spec_json

DEFAULT_BOUNDARY_CONDITIONS = ("PEC", "PEC", "PEC", "PEC", "PEC", "PEC")


@dataclasses.dataclass
class OpenEMSConfig:
    """openEMS backend settings: solver discriminator + the mesh/frequency/boundary knobs the
    golden reference hardcoded in-script. ``xml_path`` is the foundry stackup XML (e.g.
    ``SG13G2.xml``) -- PDK/stackup identity lives here, not on ``Layout.metadata``, so ``core/``
    and the tcoil plugin stay untouched by this sub-phase."""

    xml_path: str
    solver: str = "openems"
    num_cpus: int = 8
    freq_start: float = 0.0
    freq_stop: float = 100e9
    numfreq: int = 1001
    boundary_conditions: tuple[str, str, str, str, str, str] = DEFAULT_BOUNDARY_CONDITIONS
    margin: float = 200.0
    refined_cellsize: float = 1.0
    cells_per_wavelength: int = 20
    energy_limit_db: float = -50.0
    merge_polygon_size: float = 1.5
    preprocess_gds: bool = True


def load_openems_config(path: str | pathlib.Path) -> OpenEMSConfig:
    """Read an ``openems.config.json`` file and construct its ``OpenEMSConfig``. Reuses
    ``read_spec_json()`` (the same generic JSON-file reader ``load_spec()``/``load_sweep_spec()``
    use) rather than routing through ``spec_from_dict()``/the ``PassiveSpec`` registry, since an
    ``OpenEMSConfig`` isn't a ``PassiveSpec`` -- it configures the solver, not the geometry."""
    data = dict(read_spec_json(path))
    if "boundary_conditions" in data:
        data["boundary_conditions"] = tuple(data["boundary_conditions"])
    try:
        return OpenEMSConfig(**data)
    except TypeError as e:
        raise ValueError(f"{path}: malformed openems.config.json: {e}") from e
