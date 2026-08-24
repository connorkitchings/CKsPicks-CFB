# Documentation Audit — 2026-08-23

## Result

Every project-owned Markdown file was reviewed against the current 2026
rating-centric direction. The current authority set is intentionally small;
historical evidence is archived, and documents that described nonexistent or
superseded behavior were deleted.

The active architecture is:

~~~text
source data → canonical Bronze/Silver/Gold → football measurements
→ measurement-level opponent adjustment → team ratings/state
→ structured game prediction → optional ML residual → probabilistic output
→ market decision
~~~

V4 remains the 2026 production champion. Rating candidates remain shadow-only
until a separate promotion contract follows six frozen, normal-coverage slates.

## Review method

Inventory captured after cleanup: **347** present project-owned Markdown files.
Generated dependencies, build output, and .pytest_cache are excluded. Every
present file appears once in the disposition table below. Archive and
session-log contents were reviewed for retention and location, not rewritten
as current truth.

## Deleted files

| Path(s) | Disposition |
| --- | --- |
| `docs/guide.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/deployment/{README,DEPLOYMENT_CHECKLIST,production_guide,quick_start}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/ops/{data_ingestion,data_quality,monitoring,production_deployment,rollback_sop,system_stats_workflow}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/process/{adjustment_analysis_workflow,data_quality_workflow,data_science_navigator,first_prompt,closing_prompt,checklists,development_standards,hydra_guide}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/planning/{betting_line_integration,parquet_migration_plan,project_charter}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/phase2_setup_guide.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/modeling/{calibration,advanced_features,feature_engineering_guide}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/research/ppr_prd.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `docs/cfbd/{quickstart,data_ingestion}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `artifacts/{analysis,experiments,models,production}/README.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |
| `session_logs/{_template,log_template}.md` | Delete — duplicate, misleading, nonexistent, or superseded without standalone evidence |

## Present-file disposition

| Path | Disposition |
| --- | --- |
| `.agent/CONTEXT.md` | Active authority |
| `.agent/skills/CATALOG.md` | Operational skill |
| `.agent/skills/end-session/SKILL.md` | Operational skill |
| `.agent/skills/implement-plan/SKILL.md` | Operational skill |
| `.agent/skills/plan-session/SKILL.md` | Operational skill |
| `.agent/skills/plan-session/assets/implementation-contract-template.md` | Operational skill |
| `.agent/skills/start-session/SKILL.md` | Operational skill |
| `.agents/skills/neon-postgres/SKILL.md` | Operational skill |
| `.agents/skills/neon/SKILL.md` | Operational skill |
| `.codex/HYDRA.md` | Supporting reference |
| `.codex/MAP.md` | Active authority |
| `.codex/QUICKSTART.md` | Active authority |
| `.github/pull_request_template.md` | Supporting reference |
| `AGENTS.md` | Active authority |
| `CLAUDE.md` | Contributor redirect |
| `GEMINI.md` | Contributor redirect |
| `README.md` | Active authority |
| `archive/MANIFEST.md` | Archive |
| `archive/decision_log_legacy.md` | Archive |
| `archive/legacy_v1_2025/artifacts/analysis/adjustment_iteration_validation.md` | Archive |
| `archive/legacy_v1_2025/artifacts/analysis/feature_pack_discrepancy.md` | Archive |
| `archive/legacy_v1_2025/artifacts/analysis/weather_feature_analysis.md` | Archive |
| `archive/legacy_v1_2025/artifacts/plans/2025_prediction_plan.md` | Archive |
| `archive/legacy_v1_2025/artifacts/plans/dynamic_calibration_research.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/2025_performance_report.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/adjustment_iteration_summary.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/betting_analysis/betting_performance_report.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/calibration/calibration_analysis_2024.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/dynamic_calibration_research.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/error_analysis_2024.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/ppr_validation_summary.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/pruned_model_validation.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/quantile_eval_2024.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/session_plan.md` | Archive |
| `archive/legacy_v1_2025/artifacts/reports/walk_forward_summary.md` | Archive |
| `artifacts/README.md` | Supporting reference |
| `conf/experiment/legacy/README.md` | Supporting reference |
| `conf/features/legacy/README.md` | Supporting reference |
| `contracts/README.md` | Supporting reference |
| `docs/architecture/cfbd_point_in_time_pipeline.md` | Active authority |
| `docs/architecture/data_platform_2026.md` | Active authority |
| `docs/archive/2026-completed-plans/2026_codebase_modernization_and_refactoring_plan.md` | Archive |
| `docs/archive/2026-completed-plans/2026_historical_bootstrap_week0_execution.md` | Archive |
| `docs/archive/2026-rating-research/adjustment_iteration_experiments.md` | Archive |
| `docs/archive/2026-rating-research/adjustment_iteration_walkthrough.md` | Archive |
| `docs/archive/2026-rating-research/power_ratings.md` | Archive |
| `docs/archive/2026-rating-research/probabilistic_power_ratings_memo.md` | Archive |
| `docs/archive/2026-rating-research/probabilistic_power_ratings_prd.md` | Archive |
| `docs/archive/HYPERPARAMETER_OPTIMIZATION_HANDOFF.md` | Archive |
| `docs/archive/experiments_legacy.md` | Archive |
| `docs/archive/getting_started.md` | Archive |
| `docs/archive.md` | Active authority |
| `docs/archive/kb_overview.md` | Archive |
| `docs/archive/mlops_stack.md` | Archive |
| `docs/archive/model_history.md` | Archive |
| `docs/archive/next_steps_as_of_2025-10-18.md` | Archive |
| `docs/archive/open_decisions.md` | Archive |
| `docs/archive/points_for.md` | Archive |
| `docs/archive/points_for_model.md` | Archive |
| `docs/archive/refactoring/2026_modernization_verification.md` | Archive |
| `docs/archive/refactoring/REFACTORING_PLAN.md` | Archive |
| `docs/archive/refactoring/REFACTORING_STATUS.md` | Archive |
| `docs/archive/refactoring/legacy_audit.md` | Archive |
| `docs/archive/refactoring/time_calculation_fix.md` | Archive |
| `docs/archive/ridge_baseline_legacy.md` | Archive |
| `docs/archive/schema-snapshots/feature_dictionary.md` | Archive |
| `docs/archive/schema-snapshots/pipeline_overview.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/README.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/betting.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/coaches.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/games.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/plays.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/rosters.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/teams.md` | Archive |
| `docs/archive/schema-snapshots/raw_api/venues.md` | Archive |
| `docs/archive/schema-snapshots/transformed/README.md` | Archive |
| `docs/archive/schema-snapshots/transformed/drives.md` | Archive |
| `docs/archive/schema-snapshots/transformed/opponent_adjusted.md` | Archive |
| `docs/archive/schema-snapshots/transformed/plays.md` | Archive |
| `docs/archive/schema-snapshots/transformed/team_game.md` | Archive |
| `docs/archive/schema-snapshots/transformed/team_season.md` | Archive |
| `docs/archive/v2-modeling/12_week_implementation_plan.md` | Archive |
| `docs/archive/v2-modeling/artifacts_structure.md` | Archive |
| `docs/archive/v2-modeling/baseline.md` | Archive |
| `docs/archive/v2-modeling/experimentation_workflow.md` | Archive |
| `docs/archive/v2-modeling/ml_workflow.md` | Archive |
| `docs/archive/v2-modeling/promotion_framework.md` | Archive |
| `docs/cfbd/2026_provider_audit.md` | Supporting reference |
| `docs/data/README.md` | Supporting reference |
| `docs/data/ingestion_guide.md` | Active authority |
| `docs/decisions/README.md` | Supporting reference |
| `docs/decisions/decision_log.md` | Active authority |
| `docs/decisions/decision_template.md` | Supporting reference |
| `docs/experiments/index.md` | Active authority |
| `docs/index.md` | Active authority |
| `docs/modeling/betting_policy.md` | Supporting reference |
| `docs/modeling/early_season_regimes.md` | Active authority |
| `docs/modeling/evaluation.md` | Active authority |
| `docs/modeling/measurement_catalog.md` | Active authority |
| `docs/modeling/rating_system_requirements.md` | Active authority |
| `docs/archive/refactoring/data_paths.md` | Archive |
| `docs/ops/mlflow_mcp.md` | Supporting reference |
| `docs/ops/production_runbook.md` | Active authority |
| `docs/ops/validation.md` | Supporting reference |
| `docs/ops/weekly_pipeline.md` | Active authority |
| `docs/planning/roadmap.md` | Active authority |
| `docs/plans/2026-08-15/games-1-3-modeling.md` | Durable contract |
| `docs/plans/2026-08-15/pipeline-data-integrity-hardening.md` | Durable contract |
| `docs/plans/2026-08-15/week0-launch-readiness.md` | Durable contract |
| `docs/plans/2026-08-16/preview-readiness-repair.md` | Durable contract |
| `docs/plans/2026-08-17/early-season-v4-modeling.md` | Durable contract |
| `docs/plans/2026-08-18/week0-launch-execution.md` | Durable contract |
| `docs/plans/2026-08-21/week0-launch-week1-continuity.md` | Durable contract |
| `docs/plans/2026-08-21/week0-predictions-reveal.md` | Durable contract |
| `docs/plans/2026-08-22/modernization-phases-1-5-fidelity-and-refactor.md` | Durable contract |
| `docs/plans/2026-08-23/modernization-coverage-60.md` | Durable contract |
| `docs/plans/2026-08-23/modernization-phases-5-8-completion.md` | Durable contract |
| `docs/plans/2026-08-23/modernization-verification-audit.md` | Durable contract |
| `docs/plans/2026-08-23/modernization-verified-completion.md` | Durable contract |
| `docs/plans/2026-08-23/rating-centric-transition-documentation.md` | Durable contract |
| `docs/plans/2026-08-23/repository-documentation-and-2026-ratings-realignment.md` | Durable contract |
| `docs/plans/index.md` | Durable contract |
| `docs/process/mlops_experimentation.md` | Supporting reference |
| `docs/project_org/feature_registry.md` | Active authority |
| `scripts/archive/points_for/README.md` | Archive |
| `scripts/archive/tests/README.md` | Archive |
| `session_logs/2026-08-09/01-data-to-site-readiness-implementation.md` | Durable session record |
| `session_logs/2026-08-09/02-data-platform-modernization.md` | Durable session record |
| `session_logs/2026-08-09/03-week0-modeling-launch.md` | Durable session record |
| `session_logs/2026-08-09/04-cfbd-ingestion-pit-hardening.md` | Durable session record |
| `session_logs/2026-08-09/05-historical-r2-bootstrap.md` | Durable session record |
| `session_logs/2026-08-09/06-phase1-implementation-and-doc-sync.md` | Durable session record |
| `session_logs/2026-08-11/01-import-history-idempotency-and-silver-contract-fixes.md` | Durable session record |
| `session_logs/2026-08-12/01-cfbd-pickem-and-2026-finalization.md` | Durable session record |
| `session_logs/2026-08-13/01-modular-import-history-and-cfbd-pickem.md` | Durable session record |
| `session_logs/2026-08-13/02-2026-season-finalization-planning.md` | Durable session record |
| `session_logs/2026-08-14/01-2026-season-preview-readiness.md` | Durable session record |
| `session_logs/2026-08-15/01-sol-terra-workflow.md` | Durable session record |
| `session_logs/2026-08-15/02-week0-launch-implementation.md` | Durable session record |
| `session_logs/2026-08-15/03-pipeline-data-integrity-hardening.md` | Durable session record |
| `session_logs/2026-08-15/04-web-presentation-overhaul.md` | Durable session record |
| `session_logs/2026-08-15/05-games-1-3-modeling.md` | Durable session record |
| `session_logs/2026-08-16/01-preview-readiness-repair.md` | Durable session record |
| `session_logs/2026-08-17/01-early-season-v4-modeling.md` | Durable session record |
| `session_logs/2026-08-17/02-v4-immutable-feature-reference.md` | Durable session record |
| `session_logs/2026-08-18/01-v4-foundation-validation-and-commit.md` | Durable session record |
| `session_logs/2026-08-18/02-week0-launch-execution-planning.md` | Durable session record |
| `session_logs/2026-08-18/03-v4-tournament-and-production-deploy.md` | Durable session record |
| `session_logs/2026-08-19/01-documentation-refresh.md` | Durable session record |
| `session_logs/2026-08-20/01-stage4-phase0-game-week-readiness.md` | Durable session record |
| `session_logs/2026-08-20/02-model-accuracy-panel.md` | Durable session record |
| `session_logs/2026-08-21/01-week0-launch-week1-continuity.md` | Durable session record |
| `session_logs/2026-08-21/02-week0-predictions-reveal.md` | Durable session record |
| `session_logs/2026-08-21/03-week0-predictions-ui-context.md` | Durable session record |
| `session_logs/2026-08-21/04-fan-facing-predictions-ui.md` | Durable session record |
| `session_logs/2026-08-21/05-market-consensus-clarity.md` | Durable session record |
| `session_logs/2026-08-21/06-full-codebase-review-and-modernization-plan.md` | Durable session record |
| `session_logs/2026-08-21/07-modernization-phase1-dependency-and-legacy-hygiene.md` | Durable session record |
| `session_logs/2026-08-22/01-modernization-phase2-and-phase3-data-and-features-modularization.md` | Durable session record |
| `session_logs/2026-08-22/02-modernization-phases-1-5-fidelity-and-refactor.md` | Durable session record |
| `session_logs/2026-08-23/01-modernization-phases-5-8-plan.md` | Durable session record |
| `session_logs/2026-08-23/02-modernization-phases-5-8-completion.md` | Durable session record |
| `session_logs/2026-08-23/03-modernization-verification-audit.md` | Durable session record |
| `session_logs/2026-08-23/04-modernization-verified-completion.md` | Durable session record |
| `session_logs/2026-08-23/05-modernization-coverage-60.md` | Durable session record |
| `session_logs/2026-08-23/06-rating-centric-transition-documentation.md` | Durable session record |
| `session_logs/2026-08-23/07-repository-documentation-and-2026-ratings-realignment.md` | Durable session record |
| `session_logs/README.md` | Durable session record |
| `session_logs/TEMPLATE.md` | Durable session record |
| `session_logs/archive/README.md` | Archive |
| `session_logs/archive/daily/2025-09-25/01.md` | Archive |
| `session_logs/archive/daily/2025-09-25/02.md` | Archive |
| `session_logs/archive/daily/2025-09-26/01.md` | Archive |
| `session_logs/archive/daily/2025-09-28/01.md` | Archive |
| `session_logs/archive/daily/2025-09-28/02.md` | Archive |
| `session_logs/archive/daily/2025-09-29/01.md` | Archive |
| `session_logs/archive/daily/2025-09-29/02.md` | Archive |
| `session_logs/archive/daily/2025-09-30/01.md` | Archive |
| `session_logs/archive/daily/2025-09-30/02.md` | Archive |
| `session_logs/archive/daily/2025-09-30/03.md` | Archive |
| `session_logs/archive/daily/2025-10-01/01.md` | Archive |
| `session_logs/archive/daily/2025-10-01/02.md` | Archive |
| `session_logs/archive/daily/2025-10-02/01.md` | Archive |
| `session_logs/archive/daily/2025-10-02/02.md` | Archive |
| `session_logs/archive/daily/2025-10-02/03.md` | Archive |
| `session_logs/archive/daily/2025-10-03/01.md` | Archive |
| `session_logs/archive/daily/2025-10-03/02.md` | Archive |
| `session_logs/archive/daily/2025-10-04/01.md` | Archive |
| `session_logs/archive/daily/2025-10-05/01.md` | Archive |
| `session_logs/archive/daily/2025-10-06/01.md` | Archive |
| `session_logs/archive/daily/2025-10-06/02.md` | Archive |
| `session_logs/archive/daily/2025-10-07/01.md` | Archive |
| `session_logs/archive/daily/2025-10-07/02.md` | Archive |
| `session_logs/archive/daily/2025-10-07/03.md` | Archive |
| `session_logs/archive/daily/2025-10-09/01.md` | Archive |
| `session_logs/archive/daily/2025-10-10/01.md` | Archive |
| `session_logs/archive/daily/2025-10-10/02.md` | Archive |
| `session_logs/archive/daily/2025-10-11/01.md` | Archive |
| `session_logs/archive/daily/2025-10-17/01.md` | Archive |
| `session_logs/archive/daily/2025-10-17/02.md` | Archive |
| `session_logs/archive/daily/2025-10-18/01.md` | Archive |
| `session_logs/archive/daily/2025-10-18/02.md` | Archive |
| `session_logs/archive/daily/2025-10-18/03.md` | Archive |
| `session_logs/archive/daily/2025-10-18/04.md` | Archive |
| `session_logs/archive/daily/2025-10-19/01.md` | Archive |
| `session_logs/archive/daily/2025-10-19/02.md` | Archive |
| `session_logs/archive/daily/2025-10-20/01.md` | Archive |
| `session_logs/archive/daily/2025-10-20/02.md` | Archive |
| `session_logs/archive/daily/2025-10-20/03.md` | Archive |
| `session_logs/archive/daily/2025-10-20/04.md` | Archive |
| `session_logs/archive/daily/2025-10-20/05.md` | Archive |
| `session_logs/archive/daily/2025-10-21/01.md` | Archive |
| `session_logs/archive/daily/2025-10-21/02.md` | Archive |
| `session_logs/archive/daily/2025-10-21/03.md` | Archive |
| `session_logs/archive/daily/2025-10-21/04.md` | Archive |
| `session_logs/archive/daily/2025-10-21/05.md` | Archive |
| `session_logs/archive/daily/2025-10-22/01.md` | Archive |
| `session_logs/archive/daily/2025-10-22/02.md` | Archive |
| `session_logs/archive/daily/2025-10-22/03.md` | Archive |
| `session_logs/archive/daily/2025-10-22/04.md` | Archive |
| `session_logs/archive/daily/2025-10-22/05.md` | Archive |
| `session_logs/archive/daily/2025-10-22/06.md` | Archive |
| `session_logs/archive/daily/2025-10-22/07.md` | Archive |
| `session_logs/archive/daily/2025-10-23/01.md` | Archive |
| `session_logs/archive/daily/2025-10-23/02.md` | Archive |
| `session_logs/archive/daily/2025-10-23/03.md` | Archive |
| `session_logs/archive/daily/2025-10-24/01.md` | Archive |
| `session_logs/archive/daily/2025-10-24/02.md` | Archive |
| `session_logs/archive/daily/2025-10-28/01.md` | Archive |
| `session_logs/archive/daily/2025-10-29/01.md` | Archive |
| `session_logs/archive/daily/2025-10-29/02.md` | Archive |
| `session_logs/archive/daily/2025-10-30/01.md` | Archive |
| `session_logs/archive/daily/2025-11-17/01.md` | Archive |
| `session_logs/archive/daily/2025-11-18/01.md` | Archive |
| `session_logs/archive/daily/2025-11-18/02.md` | Archive |
| `session_logs/archive/daily/2025-11-18/03.md` | Archive |
| `session_logs/archive/daily/2025-11-19/01.md` | Archive |
| `session_logs/archive/daily/2025-11-19/02.md` | Archive |
| `session_logs/archive/daily/2025-11-19/03.md` | Archive |
| `session_logs/archive/daily/2025-11-20/01.md` | Archive |
| `session_logs/archive/daily/2025-11-20/02.md` | Archive |
| `session_logs/archive/daily/2025-11-20/03.md` | Archive |
| `session_logs/archive/daily/2025-11-20/04.md` | Archive |
| `session_logs/archive/daily/2025-11-20/05.md` | Archive |
| `session_logs/archive/daily/2025-11-20/06.md` | Archive |
| `session_logs/archive/daily/2025-11-21/01.md` | Archive |
| `session_logs/archive/daily/2025-11-22/01.md` | Archive |
| `session_logs/archive/daily/2025-11-22/02.md` | Archive |
| `session_logs/archive/daily/2025-11-23/01.md` | Archive |
| `session_logs/archive/daily/2025-11-23/02.md` | Archive |
| `session_logs/archive/daily/2025-11-23/03.md` | Archive |
| `session_logs/archive/daily/2025-11-24/01.md` | Archive |
| `session_logs/archive/daily/2025-11-24/02.md` | Archive |
| `session_logs/archive/daily/2025-11-24/03.md` | Archive |
| `session_logs/archive/daily/2025-11-25/01.md` | Archive |
| `session_logs/archive/daily/2025-11-25/02.md` | Archive |
| `session_logs/archive/daily/2025-11-26/01.md` | Archive |
| `session_logs/archive/daily/2025-11-26/02.md` | Archive |
| `session_logs/archive/daily/2025-11-26/03.md` | Archive |
| `session_logs/archive/daily/2025-11-26/04.md` | Archive |
| `session_logs/archive/daily/2025-11-27/01.md` | Archive |
| `session_logs/archive/daily/2025-11-27/02.md` | Archive |
| `session_logs/archive/daily/2025-11-27/03.md` | Archive |
| `session_logs/archive/daily/2025-11-27/04.md` | Archive |
| `session_logs/archive/daily/2025-12-01/01.md` | Archive |
| `session_logs/archive/daily/2025-12-03/01.md` | Archive |
| `session_logs/archive/daily/2025-12-04/01.md` | Archive |
| `session_logs/archive/daily/2025-12-04/02.md` | Archive |
| `session_logs/archive/daily/2025-12-04/03.md` | Archive |
| `session_logs/archive/daily/2025-12-05/01.md` | Archive |
| `session_logs/archive/daily/2025-12-05/02.md` | Archive |
| `session_logs/archive/daily/2025-12-06/01.md` | Archive |
| `session_logs/archive/daily/2025-12-06/02.md` | Archive |
| `session_logs/archive/daily/2025-12-07/01.md` | Archive |
| `session_logs/archive/daily/2025-12-07/02.md` | Archive |
| `session_logs/archive/daily/2025-12-07/03.md` | Archive |
| `session_logs/archive/daily/2025-12-07/04.md` | Archive |
| `session_logs/archive/daily/2025-12-08/01.md` | Archive |
| `session_logs/archive/daily/2025-12-08/02.md` | Archive |
| `session_logs/archive/daily/2025-12-08/03.md` | Archive |
| `session_logs/archive/daily/2025-12-08/04.md` | Archive |
| `session_logs/archive/daily/2025-12-08/05.md` | Archive |
| `session_logs/archive/daily/2025-12-08/06.md` | Archive |
| `session_logs/archive/daily/2025-12-08/07.md` | Archive |
| `session_logs/archive/daily/2025-12-08/08.md` | Archive |
| `session_logs/archive/daily/2025-12-09/01.md` | Archive |
| `session_logs/archive/daily/2025-12-09/02.md` | Archive |
| `session_logs/archive/daily/2025-12-09/03.md` | Archive |
| `session_logs/archive/daily/2026-02-10/01.md` | Archive |
| `session_logs/archive/daily/2026-02-10/2026-02-10-01_context.md` | Archive |
| `session_logs/archive/daily/2026-02-10/2026-02-10_sprint-2026-02-10-01.md` | Archive |
| `session_logs/archive/daily/2026-02-13/01-refactor-phase-0.md` | Archive |
| `session_logs/archive/daily/2026-02-13/02-refactor-phase-1.md` | Archive |
| `session_logs/archive/daily/2026-02-13/03-refactor-phase-3.md` | Archive |
| `session_logs/archive/daily/2026-02-13/04-refactor-phase-4.md` | Archive |
| `session_logs/archive/daily/2026-02-13/05-refactor-phase-5.md` | Archive |
| `session_logs/archive/daily/2026-02-13/06-refactor-phase-2-infrastructure.md` | Archive |
| `session_logs/archive/daily/2026-02-14/01-phase2-cleanup-and-parity-verification.md` | Archive |
| `session_logs/archive/daily/2026-02-14/02-phase6-validation-checkpoint.md` | Archive |
| `session_logs/archive/daily/2026-02-14/03-docs-strict-build-warning-remediation.md` | Archive |
| `session_logs/archive/daily/2026-02-14/04-end-session-handoff.md` | Archive |
| `session_logs/archive/daily/2026-02-14/05-phase6-cloud-storage-integration-complete.md` | Archive |
| `session_logs/archive/daily/2026-02-15/01-cloud-storage-feature-pipeline.md` | Archive |
| `session_logs/archive/daily/2026-02-15/02-renaming-project.md` | Archive |
| `session_logs/archive/daily/2026-02-16/01-baseline-validation.md` | Archive |
| `session_logs/archive/daily/2026-02-17/01.md` | Archive |
| `session_logs/archive/daily/2026-02-17/02-cleanup-hardcoded-paths.md` | Archive |
| `session_logs/archive/daily/2026-02-17/03-tier2-features-ingesters.md` | Archive |
| `session_logs/archive/daily/2026-02-17/04-comprehensive-data-review.md` | Archive |
| `session_logs/archive/daily/2026-02-17/05-comprehensive-data-review-infrastructure.md` | Archive |
| `session_logs/archive/daily/2026-02-18/01-pre-modeling-preparation.md` | Archive |
| `session_logs/archive/daily/2026-02-18/02-cross-validation-revelation.md` | Archive |
| `session_logs/archive/daily/2026-02-18/03-strategic-pivot-implementation.md` | Archive |
| `session_logs/archive/daily/2026-02-18/04-classifier-cv-results-and-analysis.md` | Archive |
| `session_logs/archive/daily/2026-02-19/01-external-data-feature-engineering.md` | Archive |
| `session_logs/archive/daily/2026-02-19/02-cloud-storage-optimization-external-data.md` | Archive |
| `session_logs/archive/daily/2026-02-20/01-cloud-tests-and-cv-leak.md` | Archive |
| `session_logs/archive/daily/2026-02-20/02-walk-forward-cv-implementation.md` | Archive |
| `session_logs/archive/daily/2026-02-20/03-catboost-walk-forward.md` | Archive |
| `session_logs/archive/daily/2026-02-20/04-implement-manual-weekly-ratings.md` | Archive |
| `session_logs/archive/daily/2026-02-21/01-internal-features-evaluation.md` | Archive |
| `session_logs/archive/daily/2026-02-21/02-internal-power-optimization.md` | Archive |
| `session_logs/archive/daily/2026-03-11/01-autonomous-ablation-mlp.md` | Archive |
| `session_logs/archive/daily/2026-07-06/01-2026-reorg-vercel-app.md` | Archive |
| `session_logs/archive/daily/2026-07-06/02-storage-unification-ingestion.md` | Archive |
| `session_logs/archive/daily/2026-07-07/01-web-app-polish.md` | Archive |
| `session_logs/archive/daily/2026-07-08/01-monorepo-reorganization.md` | Archive |
| `session_logs/archive/daily/2026-07-08/02-2026-data-ingestion.md` | Archive |
| `session_logs/archive/daily/2026-07-08/03-history-purge-nx-setup.md` | Archive |
| `session_logs/archive/daily/2026-07-09/01-2026-ops-cleanup.md` | Archive |
| `session_logs/archive/daily/2026-07-09/02-project-alignment.md` | Archive |
| `session_logs/archive/daily/2026-07-09/03-2026-season-readiness.md` | Archive |
| `session_logs/archive/daily/2026-07-24/01-ci-and-readiness-integration.md` | Archive |
| `session_logs/archive/daily/2026-07-24/02-preseason-week1-model.md` | Archive |
| `session_logs/archive/daily/2026-08-04/01-cfbd-client-readiness.md` | Archive |
| `session_logs/archive/daily/2026-08-05/01-session-closeout.md` | Archive |
| `session_logs/archive/daily/2026-08-08/01-2026-data-availability.md` | Archive |
| `session_logs/archive/historical_summary_through_2025-10.md` | Archive |
| `session_logs/archive/weekly/2025-09-23_week.md` | Archive |
| `session_logs/archive/weekly/2025-09-30_week.md` | Archive |
| `session_logs/archive/weekly/2025-10-07_week.md` | Archive |
| `session_logs/archive/weekly/2025-10-14_week.md` | Archive |
| `session_logs/archive/weekly/2025-10-21_week.md` | Archive |
| `session_logs/archive/weekly/2025-10-28_week.md` | Archive |
| `web/README.md` | Supporting reference |
| `web/db/migrations/README.md` | Supporting reference |

| `docs/reports/2026-08-23-documentation-audit.md` | Active authority |

## Notes

- docs/index.md, the roadmap, rating requirements, measurement catalog,
  evaluation policy, V4 contract, and current operations pages are the active
  authority set.
- docs/plans/ remains durable chronological contract history; superseded
  contracts are not deleted.
- Session logs dated before 2026-08-09 are retained under
  session_logs/archive/daily/; August 9 and newer logs remain active.
- Documentation and session-log archive paths are explicitly unignored so their
  moves remain reviewable and committable.
