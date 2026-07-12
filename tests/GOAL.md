# Goal: `tests/`

Per-device functional/correctness tests live next to their device
(`src/passivelab/geometry/<device>/tests/`), not here.

Root-level `tests/` is for whole-package concerns only:
- **Import / package smoke tests** (`test_smoke.py`) — the package installs and imports.
- **API-surface tests** — once `passivelab/__init__.py` exports a stable public API
  (sub-phase 1.2+), tests that the exported surface behaves as documented.
- **Cross-module / end-to-end pipeline tests** — once multiple layers exist (geometry →
  solver → dataset → ...), tests that exercise the full chain, not any single device.
- **Cross-repo integration tests** — checks against the plan-layer bridge to the Second Brain
  vault (`CLAUDE.md`'s `vault_rel` pointer, `config/projects.py` on the vault side), if that
  ever needs its own test coverage.

If you're adding a test for one device's geometry, rules, or generation behavior, it belongs in
that device's own `tests/` folder, not here.
