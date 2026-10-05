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

## Progress
- Task 2 harness committed (`3370d59`, `ef9c567`, `3368e66`, `edab279`); 27 harness tests pass.
- **Stage 1 `baseline_reproduction` PASSED (2026-10-04).** All eight gate checks held: 86,937 baseline / 82,416 candidate / 85,457 admitted events; decisions 1,416 admitted / 28 contradicted / 1,749 unverified; `admission_decisions.csv` (`dcabd4e6…`) and `admission_report.json` (`ba1a1c03…`) byte-identical to the Step 5 pins; independent verifier ok; 0 v1 contract problems; empty report diff.
- Reproduced twice on different code SHAs (`3368e66`, `edab279`): all four staged artifacts (decisions, report, admitted-events parquet, gate) are byte-identical across runs. Partial `verify --stage baseline_reproduction` passed. First run kept at `artifacts/rebuild/6a-rebuild-20261004-r1.stage1-at-3368e66`.
- Harness bug found and fixed in the first run: building one stage tried to set up later unbuilt stages; partial verify now never persists a record.
- Silver stage findings: R1 derived ref set pins normalized Silver per season; the legacy byplay also used an unpinned `data_corrections` parent (`856e1bac8626b395e922464f`, 65 rows) that needs its own pin.

## Validation
- `tests/test_rebuild_harness.py`: 27 passed; ruff clean. Full suite, contracts-check and mkdocs not yet re-run for the harness commits.
