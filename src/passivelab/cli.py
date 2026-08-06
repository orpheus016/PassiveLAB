"""``passivelab`` CLI (sub-phase 1.3.3): ``spec.json -> generate(spec) -> GDS (+ PNG)``, the
analog-designer archetype's entry point -- state a device declaratively instead of writing Python.

``generate_command()`` is the testable core (returns the written GDS path); ``main()`` is the
thin argparse wrapper, also registered as the ``passivelab`` console script
(``pyproject.toml [project.scripts]``). Run as ``python -m passivelab.cli generate spec.json`` or,
once installed, ``passivelab generate spec.json``.

Imports every known device plugin package below so its ``__init__.py`` self-registration
(spec class + generator, see geometry/tcoil/__init__.py) has run before ``load_spec``/``generate``
are ever called -- currently one line; a real plugin-discovery mechanism (setuptools
entry_points) is future work, not needed for one device.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import gdstk

import passivelab.geometry.tcoil  # noqa: F401 -- self-registers "tcoil" (spec class + generator)
from passivelab.core import generate, load_spec


def generate_command(spec_path: str | pathlib.Path, out_dir: str | pathlib.Path, *,
                      png: bool = True) -> pathlib.Path:
    """Load `spec_path`, validate, generate, write the GDS (and PNG unless `png=False`) under
    `out_dir/<cell_name>/`. Returns the written GDS path."""
    spec = load_spec(spec_path)
    spec.validate()
    layout = generate(spec)

    cell_dir = pathlib.Path(out_dir) / layout.cell.name
    cell_dir.mkdir(parents=True, exist_ok=True)
    gds_path = cell_dir / f"{layout.cell.name}.gds"
    lib = gdstk.Library()
    lib.add(layout.cell)
    lib.write_gds(str(gds_path))

    if png:
        from passivelab.geometry.preview import render_png  # lazy: matplotlib is a `viz` extra
        render_png(layout.cell, cell_dir / f"{layout.cell.name}.png", title=layout.cell.name)

    return gds_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="passivelab")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate(spec) from a spec.json")
    gen.add_argument("spec_path", help="path to a spec.json")
    gen.add_argument("--out-dir", default="out", help="output directory (default: out)")
    gen.add_argument("--no-png", action="store_true", help="skip PNG preview rendering")

    args = parser.parse_args(argv)

    try:
        gds_path = generate_command(args.spec_path, args.out_dir, png=not args.no_png)
    except (ValueError, KeyError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(f"error: {e} (PNG preview needs matplotlib: pip install -e \".[viz]\", "
              f"or rerun with --no-png)", file=sys.stderr)
        return 1

    print(gds_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
