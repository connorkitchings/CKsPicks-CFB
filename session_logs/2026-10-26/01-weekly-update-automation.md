# Session: Weekly update automation (GitHub Actions)

## TL;DR

- **Worked On:** Built the unattended weekly season update: score-exception refresh, release parity check, completed-week cutoff check in the revision builder, the `weekly_automation.py` controller and the `weekly-season-update.yml` workflow, plus the documentation. This log covers the documentation changes; the code is in the files listed by the other workers' reports.
- **Outcome:** The runbook has an "Automated weekly update" section; Production activation is documented as automatic when every gate passes, with rollback owner-only; stale statements were corrected.
- **Plan Contract:** [`docs/plans/2026-10-26/01-weekly-update-automation.md`](../../docs/plans/2026-10-26/01-weekly-update-automation.md)
- **Approval / Status:** Owner decisions of 2026-10-26 (automatic Production activation; exceptions only when line scores verify; Sunday and Monday 12:00 ET; GitHub-only notifications). Contract status Implemented, uncommitted.
- **Blockers:** None for the documentation. The automation stays off until the owner completes the setup and rehearsal.
- **Next:** Owner creates the `season-production` environment and secrets, releases `dev` to `main` with a merge commit, runs `plan-only` and a `skip_production=true` close-week rehearsal, then sets `CFB_WEEKLY_AUTOMATION_ENABLED=true`.

**tags:** ["automation", "github-actions", "runbook", "season", "decision"]

## Context and Decisions

- `main` no longer fast-forwards from `dev` since PR #9 was squash-merged, so the runbook, `AGENTS.md` and `docs/status.md` now release `dev` to `main` by a pull request merged with a merge commit. Scheduled workflows run only from `main`.
- Pushes with `GITHUB_TOKEN` do not trigger `ci.yml`; the workflow runs its own gates.
- The Week 9 manifests carry a stale Week 8 `pre_week_cutoff` (2026-10-20T18:00:00Z against the certified 14:39:00Z in `revision_manifest_w8_v3.json`). No numeric effect (last Week 8 capture 14:33:30Z; parity showed identical grades). The manifests are not edited; the Week 10 build corrects it and the builder now checks.

## Work Completed

- `docs/ops/weekly_runbook.md`: new "Automated weekly update" section (schedule, gates, rerun, disable, rollback, owner setup); Production activation sentence replaced; check counts corrected to 32 for `resume_v1`; Step 4 now releases through a merge-commit pull request.
- `AGENTS.md`, `docs/status.md`: automation, merge-commit release path, Production activation wording. `docs/status.md` also reordered the release-state history newest first, marked earlier paragraphs as dated, corrected the Week 9 rollover paragraph that said Production was unchanged, and added the stale-cutoff note and the open items.
- `docs/decisions/decision_log.md`, `docs/plans/index.md`, `docs/plans/2026-10-26/01-weekly-update-automation.md`: decision entry, index row and the contract.
- `.codex/QUICKSTART.md`: `WEEK=` added to `season-market-revision`; Production activation comment. `Makefile` help text: `season-close-week` replaces `season-revision` as the weekly command.

## Files Modified

- `docs/ops/weekly_runbook.md`, `docs/status.md`, `docs/decisions/decision_log.md`, `docs/plans/index.md`, `docs/plans/2026-10-26/01-weekly-update-automation.md`, `AGENTS.md`, `.codex/QUICKSTART.md`, `Makefile` (help text only), `session_logs/2026-10-26/01-weekly-update-automation.md`.

## Validation

- [x] `uv run mkdocs build --strict`
- [ ] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Owner setup and rehearsal (see plan contract).
- **Watch out for:** open items carried forward are listed in `docs/status.md` (16 pre-existing `make test` failures on `dev`, rollback drill never run, owner decisions on final-site-review findings #13, #15, #16 and #17, removable `incremental-close-week` worktree, an unused market-quotes catalog version).
