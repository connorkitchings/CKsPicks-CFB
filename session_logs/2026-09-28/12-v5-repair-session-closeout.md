# Session: V5 repair research closeout

## TL;DR

- **Worked On:** Closed the V5 intended-update experiment, 2026 rating/forecast counterfactual, and 2025-lineage production decision.
- **Outcome:** The historical replica matched certified V5; concrete repaired 2026 ratings and three-arm forecasts were saved. Retrospective 2026 margin MAE improved, while totals were inconclusive. Accepted V5 remains selected in production.
- **Plan Contract:** [V5 estimator review and 2026 amendment](../../docs/plans/2026-09-28/v5-estimator-three-way-review.md) (Implemented, research only).
- **Approval / Status:** User authorized the research and requested `@end` closeout. No production publication or successor promotion was requested or performed.
- **Blockers:** No research blocker. Prospective paired outcome evidence and an exact release decision are still needed before any production change.
- **Next:** Verify the saved Week 5 research forecast timestamp, score it after certified finals, and decide whether to commission a separately verified successor release.

## Context and Decisions

- 2026 preseason priors use 2025 terminal opponent-adjusted PPP and usable possessions, not 2025 final ratings. Recalculation matched all 276 certified prior means and variances exactly.
- The full counterfactual bridge already uses repaired pregame states through 2025. Replacing only 2026 ratings improved retrospective margin MAE by `0.533`; refitting the bridge as well improved it by `1.397` over certified V5 on 215 completed 2026 games. Total gains were inconclusive.
- Keep accepted V5 in production. The retrospective games were reconstructed after the fact; Week 5's candidate is saved but unscored and must be checked for timestamp/immutability before it can count as prospective evidence. Six slates are not a fixed gate.

## Work Completed

- Published the [historical repair report](../../docs/research/2026-09-28-v5-intended-update-repair-experiment.md) and [2026 counterfactual report](../../docs/research/2026-09-28-v5-2026-counterfactual.md), with source checksums, full scorecards, and concrete rating/prediction CSVs.
- Added the research-only cutoff evidence path and V5 repair controls, source importer, focused tests, contract amendments, and current-status links.
- Preserved the pre-existing dirty worktree. No files were staged, committed, pushed, or published to production.

## Files Modified

Include these exact files in the proposed research commit:

- `docs/index.md`
- `docs/modeling/v5_status.md`
- `docs/plans/2026-09-28/v5-estimator-three-way-review.md`
- `docs/research/ratings-lab-v1.md`
- `docs/research/2026-09-28-v5-intended-update-repair-experiment.md`
- `docs/research/2026-09-28-v5-intended-update-results.json`
- `docs/research/2026-09-28-v5-intended-update-live-diagnostic.json`
- `docs/research/2026-09-28-v5-2026-counterfactual.md`
- `docs/research/2026-09-28-v5-repaired-2026-pregame-ratings.csv`
- `docs/research/2026-09-28-v5-repaired-2026-predictions.csv`
- `docs/research/2026-09-28-v5-repaired-2026-results.json`
- `scripts/research/v5_intended_update_review.py`
- `scripts/research/v5_intended_update_live_diagnostic.py`
- `scripts/research/v5_2026_source_import.py`
- `scripts/research/v5_2026_counterfactual.py`
- `src/cks_picks_cfb/ratings_lab/replay.py`
- `src/cks_picks_cfb/ratings_lab/v5_control.py`
- `src/cks_picks_cfb/ratings_lab/adjusted_game.py`
- `src/cks_picks_cfb/ratings_lab/updaters.py`
- `tests/ratings_lab/test_v5_intended_update.py`
- `session_logs/2026-09-28/09-intended-update-implementation.md`
- `session_logs/2026-09-28/10-v5-2026-counterfactual.md`
- `session_logs/2026-09-28/11-v5-2025-dependency-and-promotion-decision.md`
- `session_logs/2026-09-28/12-v5-repair-session-closeout.md`

## Validation

- [x] Exact historical V5 replica and accepted 2026 bridge parity gates passed.
- [x] 46 focused ratings-lab, live-forecast, and V5 replay tests passed at closeout.
- [x] Ruff format check and lint passed for all nine changed Python files.
- [x] `mkdocs build --quiet` passed; only existing cross-root link warnings remain.
- [x] `git diff --check` passed.
- [x] `git diff --cached --stat` was empty; all changes remain unstaged.

## Amendments and Blockers

- The user's 2026 counterfactual follow-up is documented in the research contract. No accepted artifact, production rating, forecast, pick, R2 object, or Neon row changed.
- The dedicated V6 R2 research bucket is unprovisioned; this experiment used pinned read-only Preview R2 sources and local output, with reviewable CSV/JSON summaries in the repository.

## Handoff Notes

- **Resume at:** Check Week 5 candidate timestamp and immutability, score against certified finals, review margin, total, interval, and stage behavior, then prepare a distinct exact release contract if warranted.
- **Watch out for:** Do not count the 215 retrospectively reconstructed games as prospective evidence or change the 2026 production selection on this report alone.
- **Proposed commit:** `research: replay intended V5 rating update through 2026`

**tags:** ["ratings", "v5", "2026", "research", "closeout"]
