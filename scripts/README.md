# `scripts/` — repo-root, operational tooling (NOT installed)

One-off or repo-ops tooling a maintainer runs by hand: environment bootstrap, MLflow pipeline
glue (once adopted -- see `../docs/adoption/MLFLOW_ADOPTION_STUDY.md`, currently "study only, not
adopted"), release helpers. Never packaged (`pyproject.toml`'s `[tool.setuptools.packages.find]
where = ["src"]` already guarantees this).

**Not to be confused with:**
- `src/passivelab/scripts/` — user-facing, *installed* features (e.g. `sweep.py`, behind the
  `passivelab sweep` CLI subcommand). If it ships to users, it lives there, not here.
- `benchmark/` — evaluation/measurement tooling (timing, notebook-fidelity sweeps, comparison
  matrices). If it's about *validating* the generator, it lives there, not here.

Nothing lives here yet -- MLflow isn't adopted, so there's no pipeline glue to write. This
README is the placeholder; add scripts here once there's a concrete operational need, not before.
