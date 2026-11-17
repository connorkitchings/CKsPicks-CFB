# Session: Status documentation hygiene pass

## TL;DR

- **Worked On:** Reconciled stale statements in `docs/status.md` and `docs/modeling/v5_status.md`.
- **Outcome:** Preview release ID matches the header; stale catch-up, "16 failures" and "pending activation" statements removed; Open items now record the postseason decision and the broken pre-0029 rollback path.
- **Plan Contract:** N/A (fast path)
- **Approval / Status:** Owner-approved stock-take plan of 2026-11-11.
- **Blockers:** None
- **Next:** Contract `docs/plans/2026-11-11/release-readback-additive-columns.md` for the rollback readback fix; owner decisions on postseason option (b), PR #32, and the `codex/v5-ratings-audit` branch.

**tags:** ["docs", "status", "rollback"]

## Context and Decisions

- Migration 0029 added nullable columns to an existing `season_release_*` table, so the readback hash of releases staged before 0029 no longer matches; rollback to them fails closed. Documented as "currently unusable" until a fix lands.
- Stash `wac-tmp` holds only the catch-up work merged as #18; `.worktrees/cleanup-backups` is an unregistered directory holding `data-architecture-roadmap`. Neither was deleted; owner approval needed.

## Work Completed

- Updated the Week 11 row, Open items and the model status guide; updated one documentation test that pinned the stale "pending activation" wording.

## Files Modified

- `docs/status.md`, `docs/modeling/v5_status.md`, `tests/test_data_first_documentation_authority.py`

## Validation

- [x] `ruff format --check`, `ruff check`, documentation tests, `mkdocs build --strict`
- [x] `git diff --check`
- [ ] Full `make check` not completed here: the web lint step needs `eslint`, absent in this worktree (no `node_modules`).
