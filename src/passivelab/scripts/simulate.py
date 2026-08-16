"""``spec.json + solver-config.json -> characterize -> S-parameters + report.json``, sub-phase
1.4.9. Mirrors ``sweep.py``'s split (testable core + thin CLI wrapper) and its "one command, one
artifact" shape -- `passivelab generate`/`passivelab sweep` state a device declaratively;
`passivelab simulate` runs it through a solver the same way.

Solver-agnostic by construction: the solver config's own ``"solver"`` discriminator field (e.g.
``"openems"``) resolves the backend *class* via ``core/characterization/registry.py`` (built in
1.4.1 precisely so a second solver plugin wouldn't need CLI changes here) -- this module never
imports ``OpenEMSBackend`` directly.

Single-spec only for v1 (1.4.9's own scope) -- auto-detecting a sweep-spec vs a single spec.json
from the input JSON's shape is a documented future enhancement (see the 1.4.9 board task body),
not built here. Feeding it a sweep-spec today raises a clean error rather than guessing.
"""
from __future__ import annotations

import json
import pathlib

from passivelab.core import generate, load_spec
from passivelab.core.characterization.registry import get as get_backend
from passivelab.core.geometry.spec_loader import read_spec_json


def load_solver_config(path: str | pathlib.Path):
    """Read a solver-config.json's ``solver`` discriminator and construct the matching config
    object via that solver's own loader (resolved through the registry the same way
    ``spec_from_dict()`` resolves a ``PassiveSpec`` by ``passive_type``) -- this function itself
    stays solver-agnostic; it never imports a specific backend's config class."""
    data = read_spec_json(path)
    solver = data.get("solver")
    if solver is None:
        raise ValueError(f"{path}: missing required 'solver' field")
    backend_cls = get_backend(solver)
    loader = getattr(backend_cls, "load_config", None)
    if loader is None:
        raise ValueError(f"solver {solver!r} (backend {backend_cls.__name__}) has no load_config")
    return loader(path)


def simulate_command(spec_path: str | pathlib.Path, solver_config_path: str | pathlib.Path,
                      out_dir: str | pathlib.Path) -> pathlib.Path:
    """Load `spec_path`, generate its `Layout`, run it through the solver named in
    `solver_config_path`, and write `out_dir/simulate/<passive_type>/<solver>/report.json` --
    the primary deliverable, pointing at the backend's own per-sample manifest/`.s3p` (written
    under its own `out_dir`, per `docs/OPENEMS_BACKEND.md`'s output-folder design) rather than
    duplicating that data. Returns the written report path.
    """
    spec = load_spec(spec_path)
    spec.validate()
    layout = generate(spec)

    config = load_solver_config(solver_config_path)
    backend_cls = get_backend(config.solver)

    sim_out_dir = pathlib.Path(out_dir) / "simulate" / spec.passive_type / config.solver
    backend = backend_cls(config, out_dir=sim_out_dir)

    report = {
        "passive_type": spec.passive_type,
        "solver": config.solver,
        "spec_path": str(spec_path),
        "solver_config_path": str(solver_config_path),
    }
    try:
        result = backend.simulate(layout)
        report.update({
            "success": True,
            "backend": result.backend,
            "sample_id": result.raw.get("sample_id"),
            "sim_dir": result.raw.get("sim_dir"),
            "s3p_path": result.raw.get("s3p_path"),
            "ports": result.raw.get("ports"),
            "wall_clock_seconds": result.raw.get("wall_clock_seconds"),
            "metrics": result.raw.get("metrics"),  # 1.4.4: post-processed S-parameter summary
        })
    except Exception as e:
        report.update({"success": False, "error": f"{type(e).__name__}: {e}"})
        raise
    finally:
        sim_out_dir.mkdir(parents=True, exist_ok=True)
        (sim_out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    return sim_out_dir / "report.json"
