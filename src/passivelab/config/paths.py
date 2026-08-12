"""Default output-directory paths for passivelab's CLI-facing commands. Extracted so `cli.py`'s
`generate`/`sweep` subcommands share one place to change a default, instead of two independently
hardcoded argparse `default="out"` strings.

Deliberately does NOT include `benchmark/`'s dev-only `sweep_out` path
(`benchmark/geometry/tcoil/test_sweep.py`'s `OUT_DIR`) -- that's file-relative dev-tooling output,
unrelated to product config, and `benchmark/` isn't part of the installed package this module
ships in.

The canonical example/default spec is `examples/tcoil.spec.json` (byte-identical to
`tests/test_cli.py`'s `BASELINE_FIELDS` and, via `benchmark/geometry/tcoil/cases.py`, its `SMALL`
benchmark case) -- no separate "spec defaults" file lives here, to avoid a fourth copy of the
same values.
"""
DEFAULT_OUT_DIR = "out"
