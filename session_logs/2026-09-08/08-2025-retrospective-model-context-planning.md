# Session: 2025 Retrospective Model Context Planning

## TL;DR

- **Worked On:** Investigated and persisted the approved cross-stack plan for
  displaying 2025 V4 retrospective spread and total context on the 2026 site.
- **Outcome:** A decision-complete approved implementation contract now pins
  the leakage-safe forecast, locked feature, and reconstructed market refs and
  specifies isolated R2, Neon, and web behavior.
- **Plan Contract:** `docs/plans/2026-09-08/2025-retrospective-model-context.md`
- **Approval / Status:** User explicitly requested implementation on 2026-09-08;
  contract status is `Approved`.
- **Blockers:** Terra implementation requires the user-controlled clean,
  committed checkpoint mandated by the contract workflow.
- **Next:** Open a fresh Terra task with the approved contract path.

## Context and Decisions

- Reuse the certified V4 historical replay rather than the 2021-2025 production
  refit, which would leak 2025 outcomes.
- Preserve reconstructed lines as diagnostic-only evidence, separate from
  canonical grades, system records, ROI, selection, and promotion.
- Keep the live 2026 record and add separate full-2025 and matching-week spread
  and total rates. Week 0 has no 2025 weekly comparison.
- Investigation reproduced full-season spread 379-366-16 and total 398-358-5;
  Week 2 is spread 26-22-2 and total 28-22-0.
- R2, Preview Neon, and production Neon configuration was present without
  exposing secret values.
- Existing modified weekly-ops files and the untracked Week 1/Week 2 session
  log remain user-owned and outside scope.

## Work Completed

- Read the start-session and plan-session workflows, core repository context,
  recent session logs, relevant model/market/database/web code, and current git
  state.
- Verified the pinned 2025 V4 replay has 1,522 rows, 761 games, and
  `training_max_year=2024`.
- Verified the Phase 2e reconstructed market reference covers the V4 population
  under `consensus_then_median_v1` and diagnostic-only usage.
- Persisted the approved implementation contract.

## Files Modified

- `docs/plans/2026-09-08/2025-retrospective-model-context.md` - approved
  implementation contract.
- `session_logs/2026-09-08/08-2025-retrospective-model-context-planning.md` -
  planning and handoff record.

## Validation

- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`

## Amendments and Blockers

- No amendment. The repository workflow prohibits Sol from editing
  implementation files in this planning task.

## Handoff Notes

- **Resume at:** Task 1 of the approved contract after a clean committed
  checkpoint.
- **Watch out for:** Do not use the V4 production refit or write retrospective
  comparisons to `prediction_grades`/`system_stats`; preserve unrelated dirty
  worktree changes.

**tags:** ["planning", "model-lineage", "historical-context", "neon", "web"]
