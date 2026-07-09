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
- Working memory / current state: read `../Second Brain/CURRENT.md` first, then `../Second Brain/MAP.md` and `../Second Brain/700 registry/registry.json`.
- Read the plan from this repo:
  - `python "../Second Brain/script/flow/pm.py" --project passivelab --list`
  - `python "../Second Brain/script/flow/pm.py" --sync`  (what changed since the AI last looked)
- Work loop: pick a `Claude`-assigned `todo`, set it `in-progress`, do the work here (code), then set the task `in-review` on the board for James. If a task produces a knowledge draft under `../Second Brain/300 digest/`, add an inline `deliverable:: [[<id>]]` line to the task body so the vault's `make gate` promotes it into `400 wiki` when James accepts.
- Status vocab: `todo`, `in-progress`, `blocked`, `in-review`, `done`, `cancelled`. Assignees: `Claude` (AI worker), `James` (human reviewer).
- Grounding: the golden T-coil source is `../Second Brain/300 digest/DocIR/DOC-tcoil-0001.md` (+ claims JSONL); the Phase-1 PRD is `docs/PRD/Phase 1 - TCoil Platformization.md` in this repo.
- Reference: `reference` for code to later be platformized. jupyter notebook is true source while python and markdown is for simplified parsing. `reference` is not a library, but a source of truth for the T-coil platformization effort.