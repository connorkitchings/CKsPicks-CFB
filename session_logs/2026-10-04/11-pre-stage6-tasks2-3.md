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

- **Stage 1 reproduced a third time** under `4148ef0`: all four staged artifacts again byte-identical to runs 1 and 2; partial verify passed. (Baseline rebuild takes about 22 minutes and must repeat after every commit because the preflight binds the code SHA.)
- **Stage 2 `silver` built for all 10 seasons** (1,260,062 byplay rows, 54 MB staged). Nulled `ppa` totals 245,671, exactly the legacy zero-`ppa` count; `ppa` is the only value change in nine seasons. Reconciliation: no blocking rows; non-exact classification only `incomplete_source` in 2015-2019 (27 games, all provider-declared omissions).
- **`verify silver` failed once, correctly:** in 2025, 626 `Punt Return` plays changed `st`/`st_punt` from 0 to 1 versus the pre-fix R1 byplay (documented punt fix `5acd051`, known issue 2). Added a bounded explanation (`punt_return_fix`: only `Punt Return` rows, only 0 to 1, exact counts); any other change still fails. Old verify logic on the staged output reported no other problem. Per known issue 2, `ppp` and `epa_per_possession` are unaffected; the measurement stage must confirm this.

- **[SUPERSEDED] Silver on R1 parents.** The `silver` builds reported above (1,260,062 byplay rows; 245,671 nulled `ppa`; the 626-row punt finding) used the R1 derived ref set, which holds 8,521 games, not the 8,936-game Step 5 population. I had recommended that parent without verifying it; found by comparing legacy and R1 frames (2024: 125,027 vs 152,221 byplay rows). Retained here for the record; not usable evidence.
- **Corrected `silver` (smoke only, not yet built or verified through the harness):** parents pinned from the Step 5 byplay's own parent versions (`conf/rebuild/phase2c_silver_parents_v1.json`, sha `c85daae4…`). All ten seasons match the legacy chain's row counts and reconciliation classes exactly; only `ppa` changes (nulls == legacy zeros) plus 739 `Punt Return` flag rows in 2025. 7,146 + 920 + 870 = 8,936 games.
- `point_in_time_matchups` deferred by user decision (Amendment 2).

- **Eligibility and Step 5 comparison written; smoke only** (in-memory orchestrator on live Preview; 49 minutes including the baseline stage). All checks passed except one: the punt-flag effect. Investigation (keyed comparison, 2025): possession keys identical (31,447); `possession_eligible`, `quality_reason`, `period_class` unchanged on every possession; eligible possessions 20,204 in both; scoring events identical; only play-count bookkeeping moved (699 plays across 698 possessions, totals conserved; `mixed_eligibility` flipped on 530). Gate redefined as `punt_flag_change_bounded` with those exact conditions. The earlier sort-based comparison also showed `game_id`/`offense`/`week` differences; those were an artifact of sorting on changed columns and are superseded.
- Not yet done: `gold` stage (possessions, ledger, evidence builder, team-game metrics, season features) and a committed harness run of stages 1-4.

## Validation
- `tests/test_rebuild_harness.py`: 27 passed; ruff clean. Full suite, contracts-check and mkdocs not yet re-run for the harness commits.
