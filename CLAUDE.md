# Global Rules

Think before acting.

If requirements are ambiguous:
- State assumptions.
- Ask if ambiguity affects correctness.

Prefer:
- Existing code
- Existing patterns
- Minimal changes
- Existing libraries

Do:
- Read existing files before writing.
- Thorough in reasoning, concise in output.
- Skip files over 100KB unless required.

Do not:
- Overengineer
- Refactor unrelated code
- Rewrite entire files unnecessarily
- Re-read unless changed
- Use sycophantic openers or closing fluff, emojis, or em-dashes.
- Guess APIs, versions, flags, commit SHAs, or package names. Verify by reading code or docs before asserting.

Verify outcomes before declaring completion.

Be concise unless detail is requested.

## Plan & state (PKOS / Second Brain)

This repo's plan, tasks, and knowledge live in the sibling vault `../Second Brain` (a Personal Knowledge OS). Read from there; do not duplicate plan state in this repo.

- Board (tasks / subtasks / milestones): `../Second Brain/Projects/PassiveLAB_tasks/` (Obsidian "Project Manager" plugin notes, Markdown + frontmatter). projectId `0523101dmrchi7e8`.
- Working memory / current state: read `../Second Brain/CURRENT.md` first, then the manifest `../Second Brain/100 indexes/llms.txt` (resolve ids via `100 indexes/INDEX.json`). `MAP.md` is human navigation, not a bulk-load target.
- Read the plan from this repo:
  - `python "../Second Brain/script/flow/pm.py" --project passivelab --list`
  - `python "../Second Brain/script/flow/pm.py" --sync`  (what changed since the AI last looked)
- Work loop: pick a `Claude`-assigned `todo`, set it `in-progress`, do the work here (code), then set the task to `review` on the board for James. Move a task with `python "../Second Brain/script/flow/pm.py" --set-status <task id> --to review`; it refuses `done` and `cancelled`, because only James graduates a task. If a task produces a knowledge draft under `../Second Brain/300 digest/`, add an inline `deliverable:: [[<id>]]` line to the task body so the vault's `make gate` promotes it into `400 wiki` when James accepts.
- Status vocab: `todo`, `in-progress`, `blocked`, `review`, `done`, `cancelled`. Assignees: `Claude` (AI worker), `James` (human reviewer).
- Grounding: the golden T-coil source is `../Second Brain/300 digest/DocIR/DOC-tcoil-0001.md` (+ claims JSONL); the Phase-1 PRD is `docs/PRD/Phase 1 — TCoil Platformization.md` in this repo.
- Reference: `reference` for code to later be platformized. jupyter notebook is true source while python and markdown is for simplified parsing. `reference` is not a library, but a source of truth for the T-coil platformization effort.

## Development

The package lives under `src/passivelab/` (src layout). It is intentionally empty: the stable core
interfaces are the deliverable of sub-phase 1.2 and arrive through the plan/review loop, not by
guessing them up front.

```bash
pip install -e ".[dev]"
pytest
```

Before opening a PR:

- Run `pytest` locally. `.github/workflows/ci.yml` runs it again on every push and PR.
- CI must be green before review. `claude-review.yml` reads the CI result when reviewing.
- Every sub-phase needs spec, tests, validation criteria, and docs (see `docs/AGENTS.md`). Add tests
  alongside the code that satisfies each sub-phase's validation criteria in the PRD.