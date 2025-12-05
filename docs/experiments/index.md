# Experiments Index (Spread + Total Tracks)

Single source for tracking modeling experiments. Log every run that matters; link to session logs, MLflow runs, and configs. Use separate IDs per market even when infrastructure is shared.

| experiment_id | target (spread/total) | config/overrides | feature_group | split (train/test/deploy) | metrics (key) | decision (adopt/reject/hold) | links (session log, MLflow, artifacts) |
| ------------- | --------------------- | ---------------- | ------------- | ------------------------- | ------------- | ----------------------------- | -------------------------------------- |
| SPR-001       | spread                | `experiment=spread_catboost_ppr_v1` | `ppr_v1` | Train: 2019, 2021-2023; Test: 2024; Deploy: 2025 (locked) | 2024 (regen w/ weather): 226-207-8, 52.2% hit, ROI ≈ -0.36%; 2025 live thru W14 @5.0: 237-236-11, 50.1% hit, ROI ≈ -4.34% | adopt (current spread champion), monitor for uplift | session_logs/2025-12-03/01.md; model_registry: `spread_catboost_ppr` v5; data/production/scored/2024/CFB_week{2-16}_bets_scored.csv; data/production/scored/2025/CFB_week{2-14}_bets_scored.csv |
| TOT-001       | total                 | `experiment=totals_xgboost_ppr_v1` | `standard_v1` | Train: 2019, 2021-2023; Test: 2024; Deploy: 2025 (locked) | 2024 (regen w/ weather): 112-79-4, 58.6% hit, ROI ≈ +11.95%; 2025 live thru W14 @7.5: 95-90-0, 51.4% hit, ROI ≈ -1.97% | adopt (current total champion) | session_logs/2025-12-03/01.md; model_registry: `totals_xgboost_ppr` v5; data/production/scored/2024/CFB_week{2-16}_bets_scored.csv; data/production/scored/2025/CFB_week{2-14}_bets_scored.csv |

**Notes:** Higher-threshold comparison (spread 7.0 / total 8.0) for 2025 is preserved in `data/production/scored/2025/` (Weeks 2–14) and showed lower hit rates (spread ~49.3%, total ~51.0%); live config reverted to 5.0/7.5.
## Usage

1) Before running: assign an `experiment_id` (e.g., `SPR-001`, `TOT-001`).  
2) Record the Hydra config/overrides and feature_group (from `conf/features/*`).  
3) Log the key metrics (hit rate vs closing line, RMSE/MAE, ROI) on the locked split.  
4) Set a decision: `adopt`, `reject`, or `hold` (needs follow-up).  
5) Link to evidence: session log path, MLflow run ID, artifacts report.

## Guardrails

- Do not change the split without explicit approval (train: 2019/2021-2023, test: 2024, deploy: 2025).
- Keep spread and total experiments on separate rows/IDs, even if run together.
- When feature groups change, ensure the corresponding row exists in `docs/project_org/feature_registry.md`.
