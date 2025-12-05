# Feature Registry (Hydra-First)

Track feature groups and their modeling status. Update this table whenever adding, deprecating, or toggling feature groups in `conf/features/`. Use explicit allow-lists; avoid wildcards.

| feature_group               | hydra_config                                 | status                   | phase   | promotion_date | baseline_vs | notes                                                                                                          |
| --------------------------- | -------------------------------------------- | ------------------------ | ------- | -------------- | ----------- | -------------------------------------------------------------------------------------------------------------- |
| **V2 Active**               |                                              |                          |         |                |             |                                                                                                                |
| minimal_unadjusted_v1       | `conf/features/minimal_unadjusted_v1.yaml`   | ✅ **active** (baseline) | Phase 1 | 2025-12-XX     | -           | 4 features: raw off/def EPA for home/away. No adjustment, no recency weighting. Establishes floor performance. |
| **V2 Candidates (Phase 2)** |                                              |                          |         |                |             |                                                                                                                |
| opponent_adjusted_v1        | `conf/features/opponent_adjusted_v1.yaml`    | 📋 proposed              | Phase 2 | -              | TBD         | Adds 4-iteration opponent adjustment. Tests if SOS correction improves ROI +1.0%.                              |
| recency_weighted_v1         | `conf/features/recency_weighted_v1.yaml`     | 📋 proposed              | Phase 2 | -              | TBD         | Adds last-3-game recency weighting (3/2/1). Tests if recent form improves ROI +1.0%.                           |
| combined_v1                 | `conf/features/combined_v1.yaml`             | 📋 proposed              | Phase 2 | -              | TBD         | Combines opponent adjustment + recency weighting. Full legacy feature parity test.                             |
| **Legacy (Deprecated)**     |                                              |                          |         |                |             |                                                                                                                |
| standard_v1                 | `conf/features/standard_v1.yaml`             | 🗄️ deprecated            | -       | 2025-12-04     | -           | Legacy adjusted set with weather. Archived during V2 reorganization. See `archive/` for configs.               |
| ppr_v1                      | `conf/features/ppr_v1.yaml`                  | 🗄️ deprecated            | -       | 2025-12-04     | -           | Legacy PPR features for spread_catboost_ppr v5. Archived.                                                      |
| recency_v1                  | `conf/features/recency_v1.yaml`              | 🗄️ deprecated            | -       | 2025-12-04     | -           | Legacy recency variant. Archived.                                                                              |
| spread_top40                | `conf/features/spread_top_40.yaml`           | 🗄️ deprecated            | -       | -              | -           | SHAP-pruned legacy set. Archived.                                                                              |
| weather_v1                  | `conf/features/weather_v1.yaml`              | 🗄️ deprecated            | -       | -              | -           | Weather-focused sandbox. Never validated, archived.                                                            |
| points_for_pruned_union     | `conf/features/points_for_pruned_union.yaml` | 🗄️ deprecated            | -       | -              | -           | Points-for architecture rejected. Archived.                                                                    |

## Rules of Engagement

- When adding a new feature group, create the Hydra config **and** insert a row here in the same change.
- Mark target applicability explicitly (`spread`, `total`, or `both`), even if infrastructure is shared.
- If a group is removed from production usage, set status to `deprecated` (do not delete rows; preserve history).
- Align every experiment entry in `docs/experiments/index.md` with the feature group(s) used.
