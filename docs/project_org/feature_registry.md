# Feature Registry (Hydra-First)

Track feature groups and their modeling status. Update this table whenever adding, deprecating, or toggling feature groups in `conf/features/`. Use explicit allow-lists; avoid wildcards.

## 2026 V4 Feature Families (authoritative)

The 2026 production model is the V4 ten-route bundle
`week0-2026-v4-strict-20260818-r2` (config `conf/weekly_bets/v4_2026.yaml`).
The strict point-in-time reference shipped **`prior_core` only**
(`prior_only_fallback`) — every additive preseason family lacked pre-kickoff
effective-time evidence for all required 2021–2026 team-seasons (CFBD talent
feed empty). Additive families remain defined as candidate variants but are
**not activated** for the 2026 launch.

| family               | module / config                                      | status (2026-08-18)     | notes                                                                                  |
| -------------------- | ---------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------- |
| prior_core            | `src/cks_picks_cfb/models/v4_feature_variants.py`   | ✅ **active** (launch)   | Activation-eligible prior performance + current-season shrinkage.                       |
| returning_production  | V4 additive candidate                                | ⛔ unavailable (strict)  | No pre-kickoff effective-time evidence across required team-seasons.                  |
| transfer_portal       | V4 additive candidate                                | ⛔ unavailable (strict)  | Same — not admitted to the strict reference.                                          |
| recruiting            | V4 additive candidate                                | ⛔ unavailable (strict)  | Same.                                                                                  |
| coaching             | V4 additive candidate                                | ⛔ unavailable (strict)  | Same.                                                                                  |
| roster_continuity     | V4 additive candidate                                | ⛔ unavailable (strict)  | Same.                                                                                  |
| preseason_rankings    | V4 additive candidate                                | ⛔ unavailable (strict)  | Same.                                                                                  |
| talent               | V4 additive candidate (CFBD)                         | ⛔ unavailable (strict)  | CFBD talent feed empty; all-or-nothing. No further rechecks this season.              |

A separate **reconstructed** reference track holds later-backfilled provider
data for research reports only — it cannot select routes, refit bundles, pass
readiness, or publish predictions. See
[`docs/modeling/early_season_regimes.md`](../modeling/early_season_regimes.md).

## V2 Feature Groups (Historical, Dec 2025)

| feature_group           | hydra_config                                 | status                   | phase   | promotion_date | baseline_vs | notes                                                                                            |
| ----------------------- | -------------------------------------------- | ------------------------ | ------- | -------------- | ----------- | ------------------------------------------------------------------------------------------------ |
| **V2 Active**           |                                              |                          |         |                |             |                                                                                                  |
| minimal_unadjusted_v1   | `conf/features/minimal_unadjusted_v1.yaml`   | ✅ **active** (baseline) | Phase 1 | 2025-12-06     | -           | 4 features: raw off/def EPA for home/away. Benchmark ROI: -3.35%.                                |
| opponent_adjusted_v1    | `conf/features/opponent_adjusted_v1.yaml`    | ✔️ **active** (promoted) | Phase 2 | 2025-12-07     | +2.38%      | Adds 4-iteration opponent adjustment. ROI -0.97%. Passed Phase 2.                                |
| recency_weighted_v1     | `conf/features/recency_weighted_v1.yaml`     | ✔️ **active** (promoted) | Phase 2 | 2025-12-07     | +3.49%      | EWMA (α=0.3) + opponent adjustment. 8 features. ROI +0.52% (spread). Superseded by matchup_v1.   |
| matchup_v1              | `conf/features/matchup_v1.yaml`              | 🏆 **active** (champion) | Phase 2 | 2025-12-08     | +0.48%      | 16 features: adds rush/pass YPP. Walk-forward validated. ROI +0.78% (spread), +6.35% (totals).   |
| **V2 Rejected**         |                                              |                          |         |                |             |                                                                                                  |
| interaction_v1          | `conf/features/interaction_v1.yaml`          | ❌ rejected              | Phase 2 | 2025-12-07     | -0.78%      | Off×Def EPA/SR interactions. Degraded performance from champion. Rejected.                       |
| combined_v1             | `conf/features/combined_v1.yaml`             | 📋 proposed              | Phase 2 | -              | TBD         | Combines opponent adjustment + recency weighting. Not yet tested.                                |
| **Legacy (Deprecated)** |                                              |                          |         |                |             |                                                                                                  |
| standard_v1             | `conf/features/standard_v1.yaml`             | 🗄️ deprecated            | -       | 2025-12-04     | -           | Legacy adjusted set with weather. Archived during V2 reorganization. See `archive/` for configs. |
| ppr_v1                  | `conf/features/ppr_v1.yaml`                  | 🗄️ deprecated            | -       | 2025-12-04     | -           | Legacy PPR features for spread_catboost_ppr v5. Archived.                                        |
| recency_v1              | `conf/features/recency_v1.yaml`              | 🗄️ deprecated            | -       | 2025-12-04     | -           | Legacy recency variant. Archived.                                                                |
| spread_top40            | `conf/features/spread_top_40.yaml`           | 🗄️ deprecated            | -       | -              | -           | SHAP-pruned legacy set. Archived.                                                                |
| weather_v1              | `conf/features/weather_v1.yaml`              | 🗄️ deprecated            | -       | -              | -           | Weather-focused sandbox. Never validated, archived.                                              |
| points_for_pruned_union | `conf/features/points_for_pruned_union.yaml` | 🗄️ deprecated            | -       | -              | -           | Points-for architecture rejected. Archived.                                                      |

## Rules of Engagement

- When adding a new feature group, create the Hydra config **and** insert a row here in the same change.
- Mark target applicability explicitly (`spread`, `total`, or `both`), even if infrastructure is shared.
- If a group is removed from production usage, set status to `deprecated` (do not delete rows; preserve history).
- Align every experiment entry in `docs/experiments/index.md` with the feature group(s) used.
