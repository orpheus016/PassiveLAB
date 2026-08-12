# `config/` — repo-root, dev-tooling data (NOT installed)

Data consumed only by `benchmark/` (dev-only tooling). Not to be confused with
`src/passivelab/config/` (in-package, ships with the installed wheel, consumed by product code
like `cli.py`). Same installed-vs-not-installed split as `scripts/` vs. `src/passivelab/scripts/`
-- see `../scripts/README.md`.

## `cases/<device>/*.json`

Benchmark-case data, loaded via `passivelab.core.load_spec()` by
`benchmark/geometry/<device>/cases.py` (e.g. `cases/tcoil/large.json`). A device's `SMALL`-sized
case points at `examples/<device>.spec.json` directly instead of duplicating it here -- only
cases with no existing canonical spec file get a new one under this folder.
