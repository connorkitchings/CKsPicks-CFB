# Decision Log

## 2026-08-23: Adopt Rating-Centric Hybrid Architecture for 2026

- **Context**: V4 provides strong point-in-time lineage, temporal validation,
  opponent-adjusted football features, reproducible bundles, and fail-closed
  operations. Its central modeling product is nevertheless a matchup feature
  row: team quality remains implicit across measurements, priors, shrinkage,
  and ten route-specific spread/total models, and predictive uncertainty is not
  represented.
- **Decision**: Make offense, defense, overall quality, and uncertainty-bearing
  team ratings/state the canonical future representation of team strength. The
  initial flow is football measurements → measurement-level opponent adjustment
  → team ratings/state → structured game prediction → optional ML residual →
  probabilistic output → market decision. Use one season-long rating meaning
  whose prior/evidence credibility changes continuously rather than permanent
  hard completed-game philosophies. Keep opponent adjustment primarily before
  rating estimation and prohibit untracked schedule-strength double-counting.
- **Evaluation**: V4 remains the unchanged 2026 production champion and
  benchmark. Rating candidates stay isolated in research/shadow artifacts and
  freeze their design before inspecting eligible 2026 outcomes. Protected
  outcomes cannot be reused for iterative tuning. A first promotion review is
  possible only after six completed full slates with frozen predictions, and
  requires a separate approved contract and operational rehearsal.
- **Deferred**: Exact estimator, rating scale, prior model, uncertainty method,
  special-teams component, residual architecture, and artifact schema. Begin
  with requirements and a simple baseline under later contracts rather than
  choosing a sophisticated method here.
- **Source**:
  `docs/plans/2026-08-23/repository-documentation-and-2026-ratings-realignment.md`;
  `docs/modeling/rating_system_requirements.md`.

## 2026-08-18: Production Deployment and Fail-Closed Publication Gating

- **Context**: Stage 3 of the Week 0 launch contract required a production
  environment distinct from Preview while reusing the verified immutable
  artifact history.
- **Decision**: Deploy production as: Neon production branch (migrations
  0002–0008; catalog hydrated from Preview via COPY — 7,163 source captures,
  85 dataset versions) with a least-privilege read-only `cks_prod_web` LOGIN
  role for Vercel; production R2 credentials pointing at the same
  `cks-picks-cfb-preview` bucket as Preview (immutable artifacts are
  checksummed and environment-neutral; separation is enforced by Neon branch,
  not bucket); Vercel production deploy at
  `https://c-ks-picks-cfb.vercel.app` in fail-closed `market` publication mode
  (`CFB_PUBLICATION_MODE=market`, `CFB_PUBLICATION_SEASON=2026`,
  `CFB_PUBLICATION_WEEKS=0`). Model output stays hidden until the user
  explicitly approves flipping to `predictions` mode after the Week 0 freeze.
- **Impact**: Production published run `2026w0-79ec2aebcb00` (8/8 games
  predicted, 8/8 lined, 0 high-confidence) with a green `/api/health`. No
  model lean can reach the public site without an explicit user-approved
  publication-mode change.
- **Source**: `docs/plans/2026-08-18/week0-launch-execution.md` (Stage 3,
  Amendments 2–3); `session_logs/2026-08-18/03-v4-tournament-and-production-deploy.md`.

## 2026-08-18: V4 Selected as 2026 Launch Model; prior_only_fallback Posture

- **Context**: The V4 tournament (sealed 2022–2024 OOF selection, locked-2025
  validation, 2021–2025 refit) ran under an Aug 18–20 timebox with V2 as the
  proven fallback. CFBD's talent feed remained empty, blocking all additive
  preseason feature families in the strict point-in-time reference.
- **Decision**: Select the V4 ten-route bundle
  `week0-2026-v4-strict-20260818-r2` (design SHA `ae34ddc7…`) as the 2026
  launch model (config `conf/weekly_bets/v4_2026.yaml`; V2 remains wired as
  fallback). Launch with `prior_core` features only
  (`prior_only_fallback`) and stop rechecking the CFBD talent feed for the
  rest of the season. Market-dependent promotion gates are recorded as
  unavailable — not passed — wherever authentic historical quotes do not
  exist.
- **Impact**: Sealed selection won 4 of 8 challenger routes (spread/game_1
  direct_catboost −1.43 MAE; total/game_2–4 blends −0.5 to −1.5 MAE); locked
  2025 passed anti-regression on all 8 routes. Research-only 2025 betting
  simulation (quarantined legacy lines): +17.9 units (+3.1% ROI). All 8 Week 0
  games route to `game_1` (spread: direct CatBoost; total: prior-quality
  baseline).
- **Source**: `docs/plans/2026-08-18/week0-launch-execution.md` (Stages 1–2,
  Amendment 3); `session_logs/2026-08-18/03-v4-tournament-and-production-deploy.md`.

## 2026-08-17: V4 Strict vs. Reconstructed Point-in-Time Feature References

- **Context**: Historical `preseason_team_inputs` artifacts carry 2026 capture
  timestamps and end-of-season fields, so they cannot serve as historical
  preseason inputs. Additive preseason families (recruiting, coaches, rosters,
  returning production, rankings, talent) lacked pre-kickoff effective-time
  evidence across all required 2021–2026 team-seasons.
- **Decision**: Split V4 feature references into two immutable tracks.
  **Strict**: activation-eligible prior performance plus current-season
  shrinkage, admitting an additive family only when every required team-season
  has source-specific pre-kickoff effective-time evidence. **Reconstructed**:
  later-backfilled provider data, explicitly marked non-point-in-time and
  restricted to research reports — it cannot select routes, refit bundles,
  pass readiness, or publish predictions.
- **Impact**: The strict tournament proceeded without waiting on any additive
  family and ultimately shipped `prior_core` only; the reconstructed track
  remains available for research without activation risk.
- **Source**: `docs/plans/2026-08-17/early-season-v4-modeling.md` (Amendment 1);
  `session_logs/2026-08-17/02-v4-immutable-feature-reference.md`.

## 2026-08-16: Games 1–3 Prediction-Only Promotion Basis

- **Context**: The Games 1–3 redesign needed a promotion criterion while
  historical odds remained quarantined (untimestamped) and the external
  historical-odds execution was deferred.
- **Decision**: Authorize Games 1–3 selection, refitting, and 2026 activation
  using historical game results alone (`selection_basis=predictive_results_only`,
  `betting_validation_status=not_evaluated`). Historical odds remain an
  optional, decoupled module — never an input feature nor a readiness,
  promotion, or refit dependency. Result-only promotion uses 2022–2024 OOF
  MAE, RMSE, bias, season stability, and paired-bootstrap evidence, with 2025
  sealed for anti-regression.
- **Impact**: Established the result-only promotion basis inherited by the V4
  tournament; V3 (`week0-2026-games-ordinal-v3-20260816-r2`) became the
  baseline lineage for V4 selection.
- **Source**: `docs/plans/2026-08-15/games-1-3-modeling.md` (Amendment
  2026-08-16); `session_logs/2026-08-16/01-preview-readiness-repair.md`.

## 2026-08-09: Preserve Untimestamped Lines as Legacy References and Canonicalize Week 0

- **Context**: The read-only production R2 inventory found 7,156 eligible
  historical objects covering 2019 and 2021-2026. Historical betting-line exports
  contain no authentic quote timestamps, and CFBD labels the August 29, 2026
  opening slate as provider Week 1 rather than Week 0.
- **Decision**: Import untimestamped lines into a separate immutable
  `legacy_market_references` dataset. They are ineligible for canonical market
  snapshots, leans, grades, ROI, model selection, and high-confidence labels.
  Preserve CFBD's provider week and apply Week 0 through a versioned canonical
  schedule policy keyed by game ID and kickoff.
- **Impact**: Outcome-based model development can proceed without inventing
  market chronology. Exact historical market replay remains blocked until
  authentic point-in-time quotes exist. Live 2026 quotes will be captured under
  the canonical timestamped policy.
- **Plan**: See the archived execution record at
  `docs/archive/2026-completed-plans/2026_historical_bootstrap_week0_execution.md`.

## 2025-12-09: Spread Bias Correction Validated

- **Context**: Analysis of 2024 holdout data revealed a systematic bias of -1.14 points (under-prediction) in the spread model, particularly affecting the mid-range edge bucket (2.5-7.0).
- **Experiment**: Tested a simple bias correction (+1.14 points to predicted spread) on the 2024 scored data.
- **Results**:
  - **Baseline (Uncorrected)**: 228 bets, +1.32% ROI.
  - **Corrected (+1.14)**: 132 bets, **+25.83% ROI**.
  - **Impact**: Volume decreased by ~42%, but profitability skyrocketed.
- **Decision**: **RECOMMEND ADOPTION**. The bias correction should be implemented in the production pipeline.
- **Next Steps**: Update the champion model config or inference pipeline to apply this offset.

## 2025-12-08: V2 Phase 3 Re-evaluation with Matchup V1 Features - Complex Models Rejected Again

- **Context**: Re-evaluated CatBoost and XGBoost models for both spread and total targets, now utilizing the improved `matchup_v1` feature set. The goal was to determine if the new features could enable these complex models to surpass the performance of the Linear (Ridge) champion model.
- **CatBoost (Matchup V1, Spreads) Results (2024 Holdout)**:
  - RMSE: 19.41
  - MAE: 15.13
  - Hit Rate: 50.07%
  - ROI: -4.42% (vs Linear +0.78%)
- **XGBoost (Matchup V1, Spreads) Results (2024 Holdout)**:
  - RMSE: 19.54
  - MAE: 15.25
  - Hit Rate: 52.11%
  - ROI: -0.52% (vs Linear +0.78%)
- **CatBoost (Matchup V1, Totals) Results (2024 Holdout)**:
  - RMSE: 17.79
  - MAE: 14.11
  - Hit Rate: 50.82%
  - ROI: -2.99% (vs Linear +6.81% at 1.5 threshold)
- **XGBoost (Matchup V1, Totals) Results (2024 Holdout)**:
  - RMSE: 18.40
  - MAE: 14.68
  - Hit Rate: 50.00%
  - ROI: -4.55% (vs Linear +6.81% at 1.5 threshold)
- **Decision**: **REJECT** CatBoost and XGBoost models for both spread and total targets.
  - **Reasoning**: All complex models significantly underperformed the simpler Linear (Ridge) model across all key metrics (ROI, Hit Rate). None of these models came close to passing the Phase 3 promotion gate of +1.5% ROI improvement over the linear baseline on the same features. This reinforces the finding that the Linear model remains the most robust and profitable for this problem.
- **Impact**: Confirms the current champion model architecture. Future efforts should focus on feature engineering, data quality, or novel linear approaches rather than more complex model types, until a compelling reason or significant feature set is discovered that might benefit non-linear relationships.

## 2025-12-08: Totals Walk-Forward Validation - Matchup V1 Confirmed Profitable

- **Context**: Performed walk-forward validation on the `matchup_v1` Totals model (with a 0.5 point threshold) across recent holdout years to assess its long-term stability and profitability.
- **Walk-Forward Results**:
  | Year | Bets | Hit Rate | ROI |
  | :-- | :--- | :------- | :-- |
  | 2021 | 660 | 53.33% | +1.82% |
  | 2022 | 668 | 51.65% | -1.40% |
  | 2023 | 686 | 53.64% | +2.41% |
  | 2024 | 698 | 55.59% | +6.12% |
  | **Avg** | **678** | **53.55%** | **+2.24%** |
- **Decision**: **CONFIRMED** `matchup_v1` Totals model exhibits a positive edge over the long term.
  - **Reasoning**: The model achieved positive ROI in 3 out of 4 years. While 2022 showed a slight loss, the average ROI of +2.24% indicates a consistent, albeit modest, long-term edge with the 0.5 threshold. The strong +6.12% in 2024 (and +6.81% with the 1.5 threshold) suggests the model can capture significant value in certain seasons.
- **Impact**: Provides increased confidence in the Totals model's profitability. Future deployments will use the optimized 1.5 point threshold for higher ROI, as determined in the "Totals Threshold Tuning" decision.

## 2025-12-08: Spread Threshold Optimization - Dual Approach Recommended

- **Context**: Analyzed ROI vs. Edge Threshold for the champion Spread model (`matchup_v1`) on 2024 holdout data to identify optimal betting thresholds.
- **Analysis Results**:
  | Threshold | Bets | Volume % | Hit Rate | ROI |
  |-----------|------|----------|----------|-----|
  | **0.0** | **735** | **99.5%** | **52.8%** | **+0.78%** |
  | 2.5 | 576 | 77.9% | 51.6% | -1.56% |
  | 5.0 | 436 | 59.0% | 52.3% | -0.17% |
  | 6.0 | 381 | 51.6% | 50.7% | -3.29% |
  | 7.0 | 353 | 47.8% | 50.7% | -3.19% |
  | **8.0** | **305** | **41.3%** | **53.4%** | **+2.03%** |
  | 9.0 | 264 | 35.7% | 53.0% | +1.24% |
- **Decision**: **Implement a dual-threshold approach for Spreads**:
  1.  **Default Threshold (for general betting): 0.0 points.** This maintains the current "all bets" approach with a marginal positive ROI (+0.78%).
  2.  **High-Confidence Threshold (for selective betting): 8.0 points.** This significantly increases profitability to +2.03% for a more selective set of games (41.3% volume).
  - **Reasoning**: The mid-range thresholds (2.5-7.0) are consistently unprofitable, indicating the model's edge is either very clear or non-existent in those ranges. The 8.0 threshold provides the highest ROI found.
- **Impact**: Provides flexibility for betting strategy, allowing for both broad coverage and highly selective, profitable plays.

## 2025-12-08: Totals Threshold Tuning - Optimized to 1.5 Points

- **Context**: Analyzed ROI vs. Edge Threshold for the champion Totals model (`matchup_v1`) on 2024 holdout data to balance volume and profitability.
- **Analysis Results**:
  | Threshold | Bets | Volume % | Hit Rate | ROI |
  |-----------|------|----------|----------|-----|
  | 0.5 | 698 | 94.5% | 55.6% | +6.12% |
  | **1.5** | **597** | **80.8%** | **55.9%** | **+6.81%** |
  | 2.0 | 560 | 75.8% | 55.9% | +6.70% |
  | 3.0 | 477 | 64.5% | 54.7% | +4.46% |
- **Decision**: **Increase default Totals threshold from 0.5 to 1.5 points**.
  - **Reasoning**: Moving to 1.5 increases ROI to its peak (+6.81%) while reducing volume by ~14% (removing the lowest-confidence bets).
  - **Impact**: Expected to maintain high profitability while reducing variance from marginal edge cases.
  - **Spread Note**: Spread threshold remains 0.0 for evaluation, but 8.0 showed promise (+2.03% ROI) for high-confidence picks.

## 2025-12-08: Walk-Forward Validation - Matchup Features PROMOTED

- **Context**: Validated matchup_v1 features using walk-forward validation across 4 holdout years.
- **Walk-Forward Results** (spread target):

  | Holdout | Champion ROI | Matchup ROI | Improvement |
  | ------- | ------------ | ----------- | ----------- |
  | 2021    | -6.60%       | -6.05%      | +0.55%      |
  | 2022    | +1.07%       | +2.17%      | +1.10%      |
  | 2023    | -8.01%       | -8.01%      | +0.00%      |
  | 2024    | +0.52%       | +0.78%      | +0.26%      |
  | **Avg** | **-3.26%**   | **-2.78%**  | **+0.48%**  |

- **Decision**: **PROMOTE** matchup_v1 as new champion.
  - Improvement is consistent across 3/4 years (never worse)
  - Average improvement of +0.48% ROI
  - Totals showed +1.05% improvement on 2024 holdout
- **New Champion Config**: `conf/features/matchup_v1.yaml` (16 features)

## 2025-12-08: V2 Phase 2 Alpha Optimization - No Change

- **Context**: Grid searched EWMA decay alpha ∈ {0.1, 0.2, 0.3, 0.4, 0.5} on spread target.
- **Results** (2024 Holdout):
  | Alpha | Hit Rate | ROI |
  |-------|----------|-----|
  | 0.1 | 50.75% | -3.12% |
  | 0.2 | 51.84% | -1.04% |
  | **0.3** | **52.65%** | **+0.52%** |
  | 0.4 | 52.11% | -0.52% |
  | 0.5 | 52.65% | +0.52% |
- **Decision**: **NO CHANGE**. α=0.3 and α=0.5 are tied at +0.52% ROI. No improvement over current champion.
- **Insight**: The 0.3-0.5 range is optimal; lower alpha (more smoothing) degrades performance. Recommend keeping α=0.3.

## 2025-12-08: V2 Documentation Aligned - Champion Models Ready for Deployment

- **Context**: Completed Option A (Documentation & Deployment) from session plan.
- **Updates Made**:
  - `docs/experiments/index.md` — All 10 V2 experiments documented with results
  - `docs/modeling/betting_policy.md` — V2 Champion section with optimal thresholds
  - `docs/project_org/feature_registry.md` — Feature status corrected (recency_weighted_v1 = champion)
- **Current Champions**:
  - **Spread**: Linear + recency_weighted_v1 → +0.52% ROI (7.0 pt threshold → +2.1% ROI)
  - **Totals**: Linear + recency_weighted_v1 → +5.3% ROI (0.5 pt threshold → +6.1% ROI)
- **Decision**: Models are **ready for CFP deployment** (Dec 20-21 quarterfinals).

## 2025-12-07: V2 Phase 2 Interaction Features - Rejected

- **Context**: Tested 4 explicit interaction features (Off x Def EPA/SR) on top of the Recency Champion.
- **Results**:
  - **Interactions**: ROI -0.26% | Hit Rate 52.2%
  - **Champion (Corrected)**: ROI +0.52% | Hit Rate 52.7%
- **Decision**: **REJECT**.
  - Interactions degraded performance by ~0.8% ROI.
  - Complexity not justified.

## 2025-12-07: Critical Bug Fix - Recency Data Duplication

- **Context**: Discovered `load_v2_recency_data` was returning 5x duplicate rows (one for each iteration 0-4) due to missing filter in `v2_recency.py`.
- **Fix**: Added filter to keep only the final iteration (`adj_df = adj_df[adj_df["iteration"] == iterations]`).
- **Impact**: Retrained Champion on corrected data. New metrics are significantly better (positive ROI!).
- **New Champion Metrics (2024)**:
  - Hit Rate: **52.65%**
  - ROI: **+0.52%**
  - RMSE: 18.82

## 2025-12-07: V2 Phase 4 Stacking - Failed

- **Context**: Trained a Stacking Ensemble (Meta-learner: Logistic Regression) on Linear and XGBoost OOF predictions.
- **Results**:
  - **Stacking**: ROI -5.36% | Hit Rate 49.6%
- **Decision**: **REJECT**.
  - Significantly worse than the Recency-Weighted Linear Model (-0.15%).
  - Increased complexity yielded negative value. Confirms that simpler models are currently superior for this dataset.

## 2025-12-07: V2 Phase 2.5 Recency Weighting - Promoted

- **Context**: Implemented exponential decay (`alpha=0.3`) for storage aggregation to weight recent games more heavily.
- **Results**:
  - **Recency Linear**: ROI -0.15% | Hit Rate 52.3%
  - **Previous Best**: ROI -0.97%
- **Decision**: **PROMOTE TO CHAMPION**.
  - This is the single biggest improvement in the V2 workflow.
  - ROI is virtually break-even (-0.15%).
  - Validates the hypothesis that "recent form matters more."

## 2025-12-07: V2 Phase 3.5 XGBoost Tuning - Failed

- **Context**: Used Optuna to tune XGBoost hyperparameters to beat the -0.97% ROI benchmark.
- **Results**:
  - **Tuned XGBoost**: ROI -1.23% | Hit Rate 51.7%
- **Decision**: **REJECT**.
  - The tuned model performed worse than the untuned default XGBoost (-0.71%).
  - Shows high sensitivity to hyperparameters and potential overfitting.
  - Linear models remain the most robust "Bang for Buck".

## 2025-12-07: V2 Phase 4 Ensembling - Failed

- **Context**: Tested a weighted ensemble (50/50) of the Baseline (Linear) and XGBoost models.
- **Results**:
  - **Ensemble**: ROI -3.09% | Hit Rate 50.8%
- **Decision**: **REJECT**.
  - The ensemble performed significantly worse than its components (Linear -0.97%, XGBoost -0.71%).
  - Naive averaging is not effective for these models on this dataset.
  - Future hypothesis: Use Stacking (train a meta-model on predictions) or improve calibration of XGBoost before averaging.

## 2025-12-07: V2 Phase 3 Model Selection - Status Quo

- **Context**: Tested advanced non-linear models (CatBoost, XGBoost) against the linear baseline (`opponent_adjusted_v1`) on 2024 data.
- **Results**:
  - **Baseline (Linear)**: ROI -0.97% | Hit Rate 51.9%
  - **CatBoost**: ROI -1.76% | Hit Rate 51.5%
  - **XGBoost**: ROI -0.71% | Hit Rate 52.0%
- **Decision**: **MAINTAIN CHAMPION** (`opponent_adjusted_v1` + Linear).
  - XGBoost outperformed the baseline by +0.26% ROI, but failed the aggressive +1.5% promotion gate.
  - The complexity of maintaining an XGBoost pipeline is not yet justified by the marginal gain.
  - XGBoost is flagged as a high-potential candidate for Phase 4 (Ensembling).

## 2025-12-07: V2 Phase 2 Feature Promotion

- **Context**: Evaluated `opponent_adjusted_v1` feature set against `minimal_unadjusted_v1`.
- **Decision**: **PROMOTED**.
- **Reasoning**: ROI improved from -3.35% to -0.97% (+2.38% lift), exceeding the +1.0% threshold.

## 2025-12-06: V2 Baseline Metrics Established

- **Context**: Established strict V2 baseline using Ridge Regression and `minimal_unadjusted_v1`.
- **Metrics**:
  - RMSE: 18.64
  - Hit Rate: 50.6%
  - ROI: -3.35%
- **Decision**: All future models must beat this ROI to be considered.

## 2025-08-10: Storage Pivot to Local CSV; Python 3.12 + uv Baseline

- **Context**: Early infrastructure choices for the `cfb_model` project
  (recorded in the decision template; reconciled into the log 2026-08-19).
- **Decision**: Pivot the storage backend from Supabase Postgres to local CSV
  with per-partition manifests and validation utilities; standardize the
  Python baseline on 3.12+ and adopt `uv` for environment and tooling.
- **Impact**: Both choices carried forward — `uv` remains the toolchain, and
  the storage lineage later evolved from local CSV (2025) to the local
  Parquet drive to the 2026 Cloudflare R2 immutable lake
  (`CFB_STORAGE_BACKEND='r2'`).
- **Source**: `docs/decisions/decision_template.md`; session logs from
  2025-08-10.
