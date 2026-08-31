# Session: Week 1 Readiness — Documentation Audit and Operations Plan

## TL;DR

- **Worked On:** Full project status review (start-session protocol), documentation
  audit for the Week 1 era, and creation of the Week 1 operations execution plan.
- **Outcome:** All documentation updated to reflect the current state (Week 0 games
  played, Week 1 active, R1 in-flight). Week 1 operations plan created with exact
  commands. No code changes; doc-only fast path.
- **Plan Contract:** `docs/plans/2026-08-31/week1-operations.md` (fast-path creation)
- **Approval / Status:** User approved implementation plan on 2026-08-31.
- **Blockers:** Week 0 freeze + close must happen before Week 1 prepare-week.
  All commands require user execution from terminal.
- **Next:** User runs `make freeze-week YEAR=2026 WEEK=0 ENV=production`, then
  `make close-week`, then begins Week 1 data preparation per Stage B of the ops plan.

## Context and Decisions

- Production health check confirmed: run `2026w0-55de0317120d`, state `published`,
  8/8/8 coverage, freshness 2026-08-20. Week 0 was never frozen.
- `freeze_week.py` checks coverage (8/8) not a timestamp — retroactive freeze
  is valid. Documented in Amendment 6 of the launch contract.
- All 6 stale documentation files identified and updated (see Files Modified).
- Week 0 launch contract formally closed (status: Implemented, Amendment 6 added).
- V4 config `week: 0` is not a problem — `publish-week` takes `--week N` as an
  argument that overrides the runtime routing; the config field is informational.
- R1 ratings research remains fully isolated from production work.

## Work Completed

- Reviewed: git log (20+ commits since Aug 26), all 4 Aug-28 session logs, production
  health endpoint, freeze/close script logic, key planning docs.
- Updated: AGENTS.md, production_runbook.md, weekly_pipeline.md, roadmap.md,
  QUICKSTART.md, docs/plans/index.md, docs/plans/2026-08-18/week0-launch-execution.md.
- Created: `docs/plans/2026-08-31/week1-operations.md` with exact commands for
  freeze→close→prepare→publish→freeze sequence.

## Files Modified

- `AGENTS.md` — Execution status updated to Week 1 era; R1 status current.
- `docs/ops/production_runbook.md` — Publication weeks made dynamic; Week 0 note
  added; regular-week cadence section added; last-updated current.
- `docs/ops/weekly_pipeline.md` — Publication weeks updated; prepare-week is
  now documented as required for Week 1+.
- `docs/planning/roadmap.md` — Last-updated bumped; milestones table updated with
  Week 0 close and Week 1 active window; R1 run ID recorded.
- `.codex/QUICKSTART.md` — Publication weeks example and weekly alias updated.
- `docs/plans/2026-08-18/week0-launch-execution.md` — Stage 4/5 checkboxes checked;
  Amendment 6 (retroactive freeze policy) added; plan marked Implemented.
- `docs/plans/index.md` — Week 1 ops plan entry added.
- `docs/plans/2026-08-31/week1-operations.md` — NEW. Week 1 execution plan.

## Validation

- [x] `make contracts-check` passed.
- [x] `git diff --check` passed (no whitespace errors).
- [x] No code changes; doc-only fast path.
- [ ] MkDocs strict build (optional; defer to user if needed).

## Amendments and Blockers

- None. Doc-only changes; no material conflicts.

## Handoff Notes

- **Resume at:** User runs `make freeze-week YEAR=2026 WEEK=0 ENV=production`
  from terminal, then `make close-week YEAR=2026 WEEK=0 AS_OF=2026-08-31T12:00:00Z ENV=production`.
  Then Stage B (prepare-week) per `docs/plans/2026-08-31/week1-operations.md`.
- **Watch out for:** (1) `ingest-week WEEK=0` must complete before `prepare-week WEEK=1`
  so Gold has Week 0 results; (2) Vercel `CFB_PUBLICATION_WEEKS` must be updated
  to `0,1` in the Vercel dashboard (not just .env) for the production site to
  show Week 1 predictions; (3) R1 run status is unknown — check the ops ledger
  for `r1-full-corpus-20260829-e9edee5` before resuming ratings work.

**tags:** ["week1", "operations", "documentation", "session-audit", "week0-close"]
