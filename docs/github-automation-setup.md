# GitHub automation setup (claude-code-action)

One-time, human, repo-admin steps to activate the AI GitHub workflows in this repo
(`orpheus016/PassiveLAB`). The workflow files are already committed under
`.github/workflows/`.

## 1. Install the Claude GitHub App
- Install `https://github.com/apps/claude` and grant it access to this repository.
- Required repository permissions: Contents Read & Write, Issues Read & Write, Pull requests Read & Write.
- From a Claude Code terminal you can instead run `/install-github-app`, which guides the install and secret setup.

## 2. Add the auth secret
Add one secret under Settings > Secrets and variables > Actions:
- `CLAUDE_CODE_OAUTH_TOKEN` (Pro/Max, recommended): generate locally with `claude setup-token` and paste the token. Draws on your subscription rate limits, no per-token bill.
- or `ANTHROPIC_API_KEY` (starts with `sk-ant-`): per-token billing, separate from interactive use. If you use this, change the workflow input from `claude_code_oauth_token:` to `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}`.

Never commit tokens. Use Actions secrets only.

## 3. What the workflows do
- `.github/workflows/claude.yml`: responds to `@claude` in issue/PR comments and to assigned issues (implements changes, opens PRs, answers questions).
- `.github/workflows/claude-review.yml`: auto-reviews opened/updated PRs against the `docs/ARCHITECTURE.md` invariants.

## 4. Try it
- Board tasks are mirrored to Issues from the vault: run `python "../Second Brain/script/flow/gh_sync.py" --project passivelab --push` (drop `--limit 1` to push all). Each issue carries a `pm-task: <id>` marker and the task note gets an `issue:: <url>` line back.
- Open one of those issues, comment `@claude implement this`, and the Action opens a PR. `--pull` in the vault reports when an issue's state diverges from its board task (files win).

## 5. Local adapter note
The vault's `gh_sync` uses the `gh` CLI. It resolves `gh` via `config.GH_BIN`
(env `GH_BIN` -> PATH -> `C:\Program Files\GitHub CLI\gh.exe`). If a shell cannot find
`gh`, add its folder to PATH or set `GH_BIN`.
