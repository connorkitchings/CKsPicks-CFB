# Post-V5 Cleanup Disposition Inventory

**Date:** 2026-09-27

**Contract:** [Conservative Post-V5 Repository Simplification](../plans/2026-09-27/01-post-v5-repo-simplification.md)
**Decision:** Retain all tracked candidates in this pass. No importable code, script, config, test, plan, or session log is moved or deleted.

## Method and limits

The original draft proposed 129 named tracked files across eight removal groups. This scan expanded its directory and wildcard proposals against `git ls-files`, then checked each file name, repository path, and Python module name against tracked code, tests, configuration, Make, CI, documentation, plans, and session logs. The counts below are file-level textual hits excluding the candidate itself, and the example is one matching tracked file. Textual references are evidence, not a complete runtime call graph: dynamic commands, external automation, and immutable code identities can preserve a path even when a row shows no hit. The prior [Phase 0 disposition](2026-09-05-phase0-cleanup-disposition.md) and `conf/repository/compatibility_v1.yaml` therefore take precedence over a zero-hit inference.

## Decisive dependencies

- The shared weekly generator dispatches V5 live and replay serving and still imports V2 recency for V4/legacy mode. The V5 stage controller names the shared generator and its research runners/verifiers by path. The system-stats script imports V1/V2 modules. Those modules are not dead on the proposed evidence.
- Preflight and database publication import V5 replay serving; replay serving imports both replay builders. The proposed script archive would break these entry points.
- The scheduled `data-first-pregame-capture` workflow invokes `capture_data_first_phase2.py`. Several tournament scripts, configs, and rating modules are named benchmark paths in the compatibility manifest.
- Tests currently cover many historical modules; moving a test because it fails would remove regression evidence. The current suite baseline is 1456 passed, 2 skipped, 66.17% coverage.
- Moving 151 tracked logs dated before 2026-09-14 would break references in 63 tracked documents/code files; 175 logs are already archived. The 39 Implemented and 26 Superseded task plans under `docs/plans/` retain links and lifecycle context. The root `archive/` destination is gitignored.

## Proposed tracked-file moves

Every path below was checked and is **retained** for this contract. Reference counts are classified as executable code, tests, commands/config (including Make and CI), docs/other, and lineage (plans/logs). No textual references means a later identity/external-use audit is needed before removal.

### 1A legacy source (14 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `src/cks_picks_cfb/analysis/unadjusted.py` | tests 1, docs/other 1, lineage 5 | `tests/test_unadjusted_analysis.py` |
| `src/cks_picks_cfb/features/external.py` | code 1, tests 2, docs/other 1, lineage 4 | `src/cks_picks_cfb/features/v2_recency.py` |
| `src/cks_picks_cfb/features/v1_pipeline.py` | code 6, docs/other 5, lineage 5 | `research/evaluate_v1.py` |
| `src/cks_picks_cfb/features/v2_recency.py` | code 11, tests 3, docs/other 2, lineage 12 | `research/analysis/check_edge_distribution.py` |
| `src/cks_picks_cfb/flows/__init__.py` | code 1, tests 1, docs/other 1, lineage 9 | `src/cks_picks_cfb/audit/independence.py` |
| `src/cks_picks_cfb/flows/example_flow.py` | none in tracked text | unresolved external/identity use |
| `src/cks_picks_cfb/flows/preaggregations.py` | none in tracked text | unresolved external/identity use |
| `src/cks_picks_cfb/models/v1_baseline.py` | code 7, tests 1, docs/other 3, lineage 2 | `research/analysis/check_edge_distribution.py` |
| `src/cks_picks_cfb/models/v2_catboost.py` | code 5, docs/other 1, lineage 1 | `research/research/autonomous_ablate.py` |
| `src/cks_picks_cfb/models/v2_classifier.py` | code 1, lineage 2 | `src/cks_picks_cfb/train.py` |
| `src/cks_picks_cfb/models/v2_ensemble.py` | code 1 | `src/cks_picks_cfb/train.py` |
| `src/cks_picks_cfb/models/v2_stacking.py` | code 1, lineage 1 | `src/cks_picks_cfb/train.py` |
| `src/cks_picks_cfb/models/v2_xgboost.py` | code 5, docs/other 1, lineage 1 | `research/research/autonomous_ablate.py` |
| `src/cks_picks_cfb/training/train.py` | commands/config 3, code 1, docs/other 5, lineage 8 | `conf/experiment/legacy/01_train_baseline.yaml` |

### 1B transition scripts (15 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `scripts/pipeline/build_v4_preseason_feature_reference.py` | tests 1, docs/other 2, lineage 3 | `tests/test_v4_feature_reference.py` |
| `scripts/pipeline/build_v5_replay.py` | code 1, lineage 2 | `scripts/pipeline/generate_v5_replay_weekly_bets.py` |
| `scripts/pipeline/build_v5_week4_replay.py` | code 1, lineage 2 | `scripts/pipeline/generate_v5_replay_weekly_bets.py` |
| `scripts/pipeline/cache_running_season_stats.py` | docs/other 1 | `.codex/MAP.md` |
| `scripts/pipeline/cache_weekly_stats.py` | code 1, docs/other 2, lineage 7 | `src/cks_picks_cfb/analysis/unadjusted.py` |
| `scripts/pipeline/compare_preview_model_bundles.py` | docs/other 2, lineage 1 | `.codex/MAP.md` |
| `scripts/pipeline/generate_v5_replay_weekly_bets.py` | code 4, lineage 7 | `scripts/pipeline/generate_weekly_bets.py` |
| `scripts/pipeline/publish_historical_model_context.py` | docs/other 1, lineage 2 | `docs/ops/weekly_pipeline.md` |
| `scripts/pipeline/publish_model_artifact.py` | docs/other 1 | `.codex/MAP.md` |
| `scripts/pipeline/publish_model_bundle_v2.py` | docs/other 1 | `.codex/MAP.md` |
| `scripts/pipeline/rehearse_v5_bestquote_replay_preview.py` | code 1, lineage 3 | `scripts/pipeline/release_v5_bestquote_replacement_production.py` |
| `scripts/pipeline/release_v5_bestquote_replacement_production.py` | tests 1, lineage 3 | `tests/test_v5_bestquote_production_release.py` |
| `scripts/pipeline/replay_season_v4.py` | tests 1, docs/other 1, lineage 3 | `tests/test_replay_season_v4.py` |
| `scripts/pipeline/select_preseason_blend.py` | docs/other 1, lineage 1 | `.codex/MAP.md` |
| `scripts/pipeline/validate_v5_release_packet.py` | docs/other 1, lineage 4 | `docs/ops/v5_weekly_operator.md` |

### 1C tournament scripts (15 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `scripts/pipeline/audit_successor_cross_lineage.py` | code 1 | `src/cks_picks_cfb/ops/__main__.py` |
| `scripts/pipeline/build_r2_prior_tournament.py` | commands/config 1, docs/other 3, lineage 6 | `conf/repository/compatibility_v1.yaml` |
| `scripts/pipeline/build_rating_shadow_freeze.py` | commands/config 1, code 1, docs/other 2, lineage 3 | `conf/repository/compatibility_v1.yaml` |
| `scripts/pipeline/build_rating_shadow_score.py` | commands/config 1, code 1, docs/other 2, lineage 3 | `conf/repository/compatibility_v1.yaml` |
| `scripts/pipeline/build_rating_v4_benchmark.py` | lineage 1 | `session_logs/2026-08-25/02-v4-benchmark-recovery.md` |
| `scripts/pipeline/build_successor_history_ref_set.py` | commands/config 1, code 1, docs/other 1, lineage 1 | `conf/repository/compatibility_v1.yaml` |
| `scripts/pipeline/build_successor_legacy_comparison_ref_set.py` | code 1, tests 1, lineage 4 | `src/cks_picks_cfb/ops/__main__.py` |
| `scripts/pipeline/build_successor_r1_foundation.py` | commands/config 1, code 1, docs/other 2, lineage 2 | `conf/repository/compatibility_v1.yaml` |
| `scripts/pipeline/certify_successor_history.py` | commands/config 1, code 1, docs/other 2, lineage 3 | `conf/repository/compatibility_v1.yaml` |
| `scripts/pipeline/evaluate_game_ordinal_predictions.py` | commands/config 2, tests 1, docs/other 2, lineage 2 | `Makefile` |
| `scripts/pipeline/generate_game_ordinal_candidates.py` | commands/config 2, code 1, docs/other 3, lineage 2 | `Makefile` |
| `scripts/pipeline/refit_game_ordinal_bundle.py` | commands/config 1, tests 1, docs/other 1, lineage 4 | `Makefile` |
| `scripts/pipeline/restore_legacy_comparison_2019.py` | none in tracked text | unresolved external/identity use |
| `scripts/pipeline/run_rating_shadow_rehearsal.py` | lineage 2 | `docs/plans/2026-08-26/phase4-shadow-operations.md` |
| `scripts/pipeline/run_successor_tournament.py` | code 1, lineage 2 | `scripts/pipeline/build_r2_prior_tournament.py` |

### 1D legacy configs and template (41 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `conf/experiment/legacy/01_train_baseline.yaml` | commands/config 1 | `conf/experiment/legacy/README.md` |
| `conf/experiment/legacy/02_test_adjusted_features.yaml` | commands/config 1 | `conf/experiment/legacy/README.md` |
| `conf/experiment/legacy/README.md` | code 1, tests 1, docs/other 13, lineage 28 | `research/debug/check_links.py` |
| `conf/experiment/v2_catboost_adv_elo.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-21/01-internal-features-evaluation.md` |
| `conf/experiment/v2_catboost_crossval.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-18/03-strategic-pivot-implementation.md` |
| `conf/experiment/v2_catboost_internal_adv.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-21/01-internal-features-evaluation.md` |
| `conf/experiment/v2_catboost_internal_power.yaml` | code 1, lineage 1 | `research/tuning/tune_catboost.py` |
| `conf/experiment/v2_catboost_walk_forward.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-20/02-walk-forward-cv-implementation.md` |
| `conf/experiment/v2_champion_crossval.yaml` | code 2, lineage 1 | `research/analysis/shap_stability.py` |
| `conf/experiment/v2_champion_validation.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-18/01-pre-modeling-preparation.md` |
| `conf/experiment/v2_classifier_crossval.yaml` | lineage 2 | `session_logs/archive/daily/2026-02-18/03-strategic-pivot-implementation.md` |
| `conf/experiment/v2_phase2_interaction_v1.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-18/01-pre-modeling-preparation.md` |
| `conf/experiment/v2_phase2_recency_baseline.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-18/01-pre-modeling-preparation.md` |
| `conf/experiment/v2_phase3_catboost_matchup_v1.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-18/01-pre-modeling-preparation.md` |
| `conf/experiment/v2_phase3_xgboost_matchup_v1.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-18/01-pre-modeling-preparation.md` |
| `conf/experiment/v2_walk_forward_cv.yaml` | lineage 1 | `session_logs/archive/daily/2026-02-20/02-walk-forward-cv-implementation.md` |
| `conf/legacy/sweeper/params/points_for_elastic_net.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/points_for_gradient_boosting.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/points_for_ridge.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/points_for_xgboost.yaml` | code 1, lineage 4 | `research/training/train_points_for_production.py` |
| `conf/legacy/sweeper/params/spread_catboost.yaml` | docs/other 2, lineage 1 | `archive/decision_log_legacy.md` |
| `conf/legacy/sweeper/params/spread_elastic_net.yaml` | lineage 2 | `session_logs/archive/daily/2025-10-22/01.md` |
| `conf/legacy/sweeper/params/spread_hist_gradient_boosting.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/spread_huber.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/spread_lightgbm.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/spread_ridge.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/spread_xgboost.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/total_catboost.yaml` | docs/other 2 | `archive/decision_log_legacy.md` |
| `conf/legacy/sweeper/params/total_gradient_boosting.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/total_hist_gradient_boosting.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/total_lightgbm.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/total_random_forest.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/total_ridge.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/sweeper/params/total_xgboost.yaml` | none in tracked text | unresolved external/identity use |
| `conf/legacy/training/default.yaml` | docs/other 3, lineage 3 | `.codex/HYDRA.md` |
| `conf/weekly_bets/v2_champion.yaml` | commands/config 1, code 6, tests 1, docs/other 3, lineage 5 | `conf/weekly_bets/v2_preview_2026.yaml` |
| `conf/weekly_bets/v2_preview_2026.yaml` | commands/config 2, docs/other 2, lineage 4 | `Makefile` |
| `conf/weekly_bets/v3_preview_games_ordinal_2026.yaml` | commands/config 1, docs/other 2, lineage 1 | `conf/repository/compatibility_v1.yaml` |
| `conf/weekly_bets/v4_2025_replay.yaml` | code 1, docs/other 1, lineage 2 | `scripts/pipeline/replay_season_v4.py` |
| `conf/weekly_bets/v4_2025_retrospective_context.yaml` | code 1, lineage 2 | `scripts/pipeline/build_historical_model_context.py` |
| `templates/email_weekly_picks_v3.html` | code 1, lineage 2 | `scripts/archive/publish_picks.py` |

### 1E research scripts (21 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `scripts/research/audit_data_first_evidence.py` | tests 1, docs/other 1, lineage 3 | `tests/test_data_first_evidence_audit.py` |
| `scripts/research/build_data_first_eligibility.py` | lineage 1 | `docs/plans/2026-09-06/04-phase2d-recertification-eligibility-and-capture-activation.md` |
| `scripts/research/build_data_first_phase2c.py` | lineage 3 | `docs/plans/2026-09-06/03-phase2c-materialization-and-ref-set-closure.md` |
| `scripts/research/build_phase2d_eligibility.py` | lineage 2 | `session_logs/2026-09-06/06-phase2d-recertification-and-capture-activation.md` |
| `scripts/research/capture_data_first_phase2.py` | commands/config 1, docs/other 1, lineage 3 | `.github/workflows/data-first-pregame-capture.yml` |
| `scripts/research/certify_data_first_phase2e.py` | lineage 2 | `session_logs/2026-09-06/07-transformation-check-in-phase2d-repair.md` |
| `scripts/research/recertify_data_first_phase2d.py` | tests 1, lineage 2 | `tests/test_data_first_phase2d.py` |
| `scripts/research/repair_data_first_catalog.py` | none in tracked text | unresolved external/identity use |
| `scripts/research/run_data_first_historical_audit.py` | code 1, docs/other 1, lineage 3 | `src/cks_picks_cfb/audit/independence.py` |
| `scripts/research/run_data_first_phase3.py` | code 1, lineage 1 | `scripts/research/verify_data_first_phase3_v2.py` |
| `scripts/research/run_data_first_phase3_v2.py` | code 1, lineage 7 | `scripts/research/verify_data_first_phase3_v2.py` |
| `scripts/research/run_data_first_phase4a.py` | lineage 1 | `session_logs/2026-09-08/01-phase3-closure-and-phase4a-rating-selection.md` |
| `scripts/research/run_data_first_phase4b.py` | lineage 2 | `docs/plans/2026-09-07/03-phase4b-target-context-selection.md` |
| `scripts/research/run_v5_foundation_blocker_diagnosis.py` | lineage 1 | `session_logs/2026-09-21/02-v5-foundation-blocker-diagnosis.md` |
| `scripts/research/run_v5_historical_readiness_review.py` | docs/other 1, lineage 2 | `docs/archive/v5-contracts/2026-09-21/06-v5-12-historical-results-and-readiness-review.md` |
| `scripts/research/verify_data_first_historical_audit.py` | code 1, docs/other 2, lineage 1 | `src/cks_picks_cfb/audit/independence.py` |
| `scripts/research/verify_data_first_phase3.py` | lineage 2 | `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md` |
| `scripts/research/verify_data_first_phase3_v2.py` | code 1, lineage 2 | `scripts/research/run_data_first_phase3_v2.py` |
| `scripts/research/verify_data_first_phase4a.py` | code 1, tests 1, lineage 1 | `scripts/research/run_data_first_phase4a.py` |
| `scripts/research/verify_data_first_phase4b.py` | code 1, tests 1, lineage 2 | `scripts/research/run_data_first_phase4b.py` |
| `scripts/research/verify_phase2d_automation_admission.py` | tests 1, lineage 2 | `tests/test_data_first_phase2d.py` |

### 2C ratings modules (12 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `src/cks_picks_cfb/ratings/context_admission.py` | tests 1, lineage 1 | `tests/ratings/test_successor_history.py` |
| `src/cks_picks_cfb/ratings/cross_lineage.py` | code 2, tests 1, lineage 2 | `scripts/pipeline/audit_successor_cross_lineage.py` |
| `src/cks_picks_cfb/ratings/foundation_review.py` | code 1, tests 1, lineage 1 | `scripts/pipeline/build_rating_foundation_review.py` |
| `src/cks_picks_cfb/ratings/phase3.py` | code 4, tests 2, docs/other 1, lineage 4 | `scripts/research/run_data_first_phase3.py` |
| `src/cks_picks_cfb/ratings/phase4a.py` | code 2, tests 1, docs/other 1, lineage 2 | `scripts/research/run_data_first_phase4a.py` |
| `src/cks_picks_cfb/ratings/phase4b.py` | code 2, tests 1, lineage 3 | `scripts/research/run_data_first_phase4b.py` |
| `src/cks_picks_cfb/ratings/prospective.py` | code 7, tests 3, docs/other 2, lineage 2 | `scripts/pipeline/audit_rating_prospective_evidence.py` |
| `src/cks_picks_cfb/ratings/shadow.py` | commands/config 1, code 7, tests 1, docs/other 4, lineage 7 | `conf/repository/compatibility_v1.yaml` |
| `src/cks_picks_cfb/ratings/successor_history.py` | commands/config 1, code 5, tests 1, docs/other 2, lineage 4 | `conf/repository/compatibility_v1.yaml` |
| `src/cks_picks_cfb/ratings/successor_manifest.py` | commands/config 1, tests 1, lineage 1 | `conf/repository/compatibility_v1.yaml` |
| `src/cks_picks_cfb/ratings/successor_tournaments.py` | code 2, tests 1, lineage 3 | `scripts/pipeline/build_r2_prior_tournament.py` |
| `src/cks_picks_cfb/ratings/v4_benchmark.py` | code 2, tests 1, lineage 1 | `scripts/pipeline/build_rating_v4_benchmark.py` |

### 2D forecast modules (9 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `src/cks_picks_cfb/forecast/conditional_verification.py` | code 2, tests 1, lineage 1 | `scripts/research/run_v5_conditional_forecast_verification.py` |
| `src/cks_picks_cfb/forecast/final_historical_scorecard.py` | code 2, tests 1, docs/other 1, lineage 2 | `scripts/research/run_v5_historical_readiness_review.py` |
| `src/cks_picks_cfb/forecast/final_scorecard_publication.py` | code 1, tests 1, lineage 1 | `scripts/research/run_v5_historical_readiness_review.py` |
| `src/cks_picks_cfb/forecast/historical_scorecard.py` | code 4, tests 2, docs/other 2, lineage 3 | `scripts/research/run_v5_conditional_scorecard.py` |
| `src/cks_picks_cfb/forecast/market_diagnostic.py` | code 2, tests 1, docs/other 1, lineage 1 | `scripts/research/run_v5_market_diagnostic.py` |
| `src/cks_picks_cfb/forecast/market_diagnostic_publication.py` | code 1, docs/other 1, lineage 1 | `scripts/research/run_v5_market_diagnostic.py` |
| `src/cks_picks_cfb/forecast/scorecard_publication.py` | code 2, tests 1, lineage 2 | `scripts/research/run_v5_conditional_scorecard.py` |
| `src/cks_picks_cfb/forecast/shadow.py` | commands/config 1, code 11, tests 5, docs/other 4, lineage 7 | `conf/repository/compatibility_v1.yaml` |
| `src/cks_picks_cfb/forecast/shadow_verification.py` | code 2, tests 1, docs/other 1, lineage 1 | `scripts/research/verify_v5_shadow.py` |

### 3C assistant redirects (2 tracked files)

| Candidate path | Observed references | Example matching path |
| --- | --- | --- |
| `CLAUDE.md` | docs/other 4, lineage 6 | `.codex/MAP.md` |
| `GEMINI.md` | docs/other 3, lineage 4 | `.codex/MAP.md` |

## Other proposed changes

| Proposal | Disposition and evidence |
| --- | --- |
| Remove game-ordinal Make targets | Retain. Their scripts and V3 config are named benchmark compatibility paths; help text identifies them as historical. |
| Rename/consolidate prediction generators or repoint `weekly` | Retain behavior. The shared generator is the V5 live/replay dispatcher and V4 rollback path; `weekly` remains an alias of `publish-week`. |
| Archive corresponding tests | Retain. A failed test is a blocker, not a removal criterion. |
| Move pre-2026-09-14 session logs | Retain 151 tracked files in place; 175 are already archived and 63 tracked files reference old dated log paths. |
| Move completed/superseded plans | Retain 39 Implemented and 26 Superseded task plans in place; contract links and implementation-log paths are stable evidence. |
| Delete `CLAUDE.md` / `GEMINI.md` or remove `.opencode/` | Retain assistant entry points; `.opencode/` exists and was not investigated as an independent product removal. |
| Unified V5 one-command pipeline and data-package reorganization | Defer to separate architecture/production contracts. The reviewed stage and release gates remain unchanged. |

## Ignored local candidates

Sizes are apparent file bytes, not allocated disk blocks. The before-inventory confirms all nine paths are ignored, untracked, and contain no symlinks. No R2 content was read in this review. Training artifacts require per-file immutable R2 checksum equality or a byte-verified backup before deletion; no such proof was established. Generated output deletion is limited to the MkDocs site and pytest coverage database after their generators are verified.

| Local path | Files | Before bytes | Disposition / proof |
| --- | ---: | ---: | --- |
| `artifacts/preview/training` | 5 | 1154627528 | Retain: no per-file immutable R2/backup proof. |
| `artifacts/mlruns` | 3176 | 187690673 | Retain: local MLflow run evidence may be unique. |
| `artifacts/hydra_outputs` | 578 | 36540490 | Retain: generated but may contain unique run evidence. |
| `archive/legacy_v1_2025/artifacts` | 455 | 192688010 | Retain: ignored historical artifacts, no backup proof. |
| `site` | 223 | 11796531 | Deleted: MkDocs rebuilt to `/tmp/post-v5-mkdocs-site`; every old relative file path was regenerated and `index.html` exists. |
| `data_pipeline.log` | 1 | 1060982 | Retain: local event log may be unique. |
| `.coverage` | 1 | 1953792 | Deleted: pytest-cov regenerated it in the final full-suite run; 1957888 bytes at deletion. |
| `catboost_info` | 4 | 52303 | Retain: experiment diagnostics may be unique. |
| `models` | 3 | 3867 | Retain: V4/V2 configs reference model paths; no per-file backup proof. |

## Cleanup result

- The R2 backend and source/Preview credential presence were checked without printing secrets. No R2 object was read, so no training artifact was treated as verified for deletion.
- Removed only ignored, untracked `site/` (11796531 apparent bytes; 223 files; no symlinks) and `.coverage` (1957888 bytes at deletion). **Removed-path total: 13754419 bytes.** No tracked path was removed.
- The nine candidate paths held 1586414176 apparent bytes at first inventory. The seven retained paths held 1572678401 bytes after validation. **Net apparent reduction: 13735775 bytes**; tests increased retained logs/diagnostics by 14548 bytes and regenerated a coverage file 4096 bytes larger than the first inventory before its deletion.
- The 1.1 GB Preview training directory, MLflow runs, Hydra outputs, archived historical artifacts, event log, CatBoost diagnostics, and model files remain in place. Their local-only evidence or exact backup status is unresolved.
