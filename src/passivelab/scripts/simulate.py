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

``--plot`` (board task ``6d1zgp2pm13nv6k6``): after a normal solve, also reduces the produced
``.s3p`` to the *full* ``Metrics`` (``characterization/openems/sparams.py``'s ``sparams_to_metrics``
-- the complete matrix, not the lightweight summary already embedded in this command's own
``report.json``) and writes an interactive S-parameter plot, both under
``out_dir/characterize/<passive_type>/<solver>/<sample_id>/``. Deliberately not a new command --
re-running `simulate` on an unchanged spec/config is already cheap (the vendored solver's own
hash-based skip-if-unchanged caching), so "post-process what's already there" and "solve, then
post-process" are the same code path here, not two.
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


def _write_characterize_output(result, spec, config, out_dir: pathlib.Path) -> pathlib.Path:
    """``--plot``'s post-processing step: reduce the just-produced `.s3p` to the full `Metrics`
    (not `result.raw["metrics"]`'s lightweight summary) and write it + an interactive S-parameter
    plot under `out_dir/characterize/<passive_type>/<solver>/<sample_id>/`. Deferred imports --
    `sparams_to_metrics`/`plot_sparams_interactive` pull in `skrf`/`plotly`, neither of which every
    `simulate` caller needs (plotly is the `viz` extra)."""
    from passivelab.characterization.openems.ports import PortDef
    from passivelab.characterization.openems.sparams import metrics_to_full_json, sparams_to_metrics
    from passivelab.characterization.openems.viz import plot_sparams_interactive

    port_defs = [PortDef(**p) for p in result.raw["ports"]]
    metrics = sparams_to_metrics(result.raw["s3p_path"], port_defs)

    char_dir = out_dir / "characterize" / spec.passive_type / config.solver / result.raw["sample_id"]
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / "report.json").write_text(
        json.dumps(metrics_to_full_json(metrics), indent=2), encoding="utf-8")
    plot_sparams_interactive(metrics, char_dir / "sparams.html")
    return char_dir / "report.json"


def simulate_command(spec_path: str | pathlib.Path, solver_config_path: str | pathlib.Path,
                      out_dir: str | pathlib.Path, *, plot: bool = False) -> pathlib.Path:
    """Load `spec_path`, generate its `Layout`, run it through the solver named in
    `solver_config_path`, and write `out_dir/simulate/<passive_type>/<solver>/report.json` --
    the primary deliverable, pointing at the backend's own per-sample manifest/`.s3p` (written
    under its own `out_dir`, per `docs/OPENEMS_BACKEND.md`'s output-folder design) rather than
    duplicating that data. If `plot`, also writes `out_dir/characterize/.../report.json` + an
    interactive plot (see `_write_characterize_output`). Returns the written `simulate` report path.

    `out_dir` is resolved to an absolute path up front -- openEMS's compiled `Run()` leaves the
    process's cwd inside the last excitation's `sub-N/` folder afterward (confirmed live), so a
    still-relative `out_dir` used for this function's *own* later writes (after the solve returns)
    would resolve against that changed cwd, not the caller's original one.
    """
    out_dir = pathlib.Path(out_dir).resolve()

    spec = load_spec(spec_path)
    spec.validate()
    layout = generate(spec)

    config = load_solver_config(solver_config_path)
    backend_cls = get_backend(config.solver)

    sim_out_dir = out_dir / "simulate" / spec.passive_type / config.solver
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
        if plot:
            report["characterize_report_path"] = str(_write_characterize_output(
                result, spec, config, out_dir))
    except Exception as e:
        report.update({"success": False, "error": f"{type(e).__name__}: {e}"})
        raise
    finally:
        sim_out_dir.mkdir(parents=True, exist_ok=True)
        (sim_out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    return sim_out_dir / "report.json"
