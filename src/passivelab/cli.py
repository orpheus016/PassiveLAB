"""``passivelab`` CLI (sub-phase 1.3.3, `sweep` added in the sweep-as-a-feature refactor,
`simulate` added in 1.4.9): ``spec.json -> generate(spec) -> GDS (+ PNG)``, ``sweep-spec.json ->
N-sample sweep -> GDS+PNG previews + report.json``, and ``spec.json + solver-config.json ->
characterize -> S-parameters + report.json`` -- the analog-designer, dataset-generation, and
simulation entry points -- state a device (or a sweep of one, or a solver run of one) declaratively
instead of writing Python.

``generate_command()``/``sweep_command()``/``simulate_command()`` (the latter two in
``scripts/sweep.py``/``scripts/simulate.py``) are the testable cores; ``main()`` is the thin
argparse wrapper, also registered as the ``passivelab`` console script (``pyproject.toml
[project.scripts]``). Run as ``python -m passivelab.cli generate spec.json`` / ``... sweep
sweep-spec.json`` / ``... simulate spec.json solver-config.json`` or, once installed, ``passivelab
generate spec.json`` / ``passivelab sweep sweep-spec.json`` / ``passivelab simulate spec.json
solver-config.json``.

Imports every known device *and solver* plugin package below so their ``__init__.py``
self-registration (spec class + generator / solver config + backend, see
geometry/tcoil/__init__.py and characterization/openems/__init__.py) has run before
``load_spec``/``generate``/``simulate_command`` are ever called -- currently one line each; a real
plugin-discovery mechanism (setuptools entry_points) is future work, not needed for one device and
one solver. Importing the openems plugin package needs no ``sim``-extra dependencies itself (see
``characterization/openems/plugin.py``'s module docstring) -- only an actual ``simulate`` run does.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import gdstk

import passivelab.characterization.openems  # noqa: F401 -- self-registers "openems" (solver config + backend)
import passivelab.geometry.tcoil  # noqa: F401 -- self-registers "tcoil" (spec class + generator)
from passivelab.config import paths
from passivelab.core import generate, load_spec
from passivelab.scripts.simulate import simulate_command
from passivelab.scripts.sweep import sweep_command


def generate_command(spec_path: str | pathlib.Path, out_dir: str | pathlib.Path, *,
                      png: bool = True) -> pathlib.Path:
    """Load `spec_path`, validate, generate, write the GDS (and PNG unless `png=False`) under
    `out_dir/generate/single/<passive_type>/`, named after the generated cell. Returns the written
    GDS path."""
    spec = load_spec(spec_path)
    spec.validate()
    layout = generate(spec)

    cell_dir = pathlib.Path(out_dir) / "generate" / "single" / spec.passive_type
    cell_dir.mkdir(parents=True, exist_ok=True)
    gds_path = cell_dir / f"{layout.cell.name}.gds"
    lib = gdstk.Library()
    lib.add(layout.cell)
    lib.write_gds(str(gds_path))

    if png:
        from passivelab.utils.preview import render_png  # lazy: matplotlib is a `viz` extra
        render_png(layout.cell, cell_dir / f"{layout.cell.name}.png", title=layout.cell.name)

    return gds_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="passivelab")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate(spec) from a spec.json")
    gen.add_argument("spec_path", help="path to a spec.json")
    gen.add_argument("--out-dir", default=paths.DEFAULT_OUT_DIR,
                      help=f"output directory (default: {paths.DEFAULT_OUT_DIR})")
    gen.add_argument("--no-png", action="store_true", help="skip PNG preview rendering")

    swp = sub.add_parser("sweep", help="generate a reproducible N-sample sweep from a sweep-spec.json")
    swp.add_argument("spec_path", help="path to a sweep-spec.json")
    swp.add_argument("--out-dir", default=paths.DEFAULT_OUT_DIR,
                      help=f"output directory (default: {paths.DEFAULT_OUT_DIR})")
    swp.add_argument("--no-png", action="store_true", help="skip PNG preview rendering")

    sim = sub.add_parser("simulate", help="characterize(spec) through a solver-config.json's solver")
    sim.add_argument("spec_path", help="path to a spec.json")
    sim.add_argument("solver_config_path", help="path to a solver-config.json (e.g. openems.config.json)")
    sim.add_argument("--out-dir", default=paths.DEFAULT_OUT_DIR,
                      help=f"output directory (default: {paths.DEFAULT_OUT_DIR})")
    sim.add_argument("--plot", action="store_true",
                      help="also write the full Metrics + an interactive S-parameter plot under "
                           "out-dir/characterize/... (needs the viz extra)")

    args = parser.parse_args(argv)

    try:
        if args.command == "generate":
            result_path = generate_command(args.spec_path, args.out_dir, png=not args.no_png)
        elif args.command == "sweep":
            result_path = sweep_command(args.spec_path, args.out_dir, png=not args.no_png)
        else:  # "simulate"
            result_path = simulate_command(args.spec_path, args.solver_config_path, args.out_dir,
                                            plot=args.plot)
    except (ValueError, KeyError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(f"error: {e} (PNG preview and --plot need matplotlib/plotly: "
              f"pip install -e \".[viz]\"; a solver needs its own extra, e.g. "
              f"pip install -e \".[sim]\" for openems)", file=sys.stderr)
        return 1

    print(result_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
