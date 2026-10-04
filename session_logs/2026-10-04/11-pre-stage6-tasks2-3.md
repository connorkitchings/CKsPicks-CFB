# Session: Pre-Stage-6 Tasks 2-3 (manifest orchestration and corrected-lineage rebuild)

## TL;DR
- **Worked On:** Start-session, exploration, plan approval, Step 0 prerequisites.
- **Outcome:** In progress. Task 1 committed by the user (`2f9ec06`, `1e9e3bd`); Amendment 1 appended to the contract. No harness code or data builds yet.
- **Plan Contract:** [02-pre-stage6-integrity-and-rebuild.md](../../docs/plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md)
- **Next:** Task 2 `rebuild/` package, tests, preflight.

## Decisions
- Gold: six outputs (four contracted + `point_in_time_matchups` + `season_level_features_v1` + `forecast_feature_frame_v1`).
- New pinned DAG; legacy runners untouched except for baseline reproduction.
- Scope: all of Task 3, stopping at any failed gate.

## Validation
(pending)
