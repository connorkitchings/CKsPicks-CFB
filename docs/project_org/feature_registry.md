# Feature Registry (Hydra-First)

Track feature groups and their modeling status. Update this table whenever adding, deprecating, or toggling feature groups in `conf/features/`. Use explicit allow-lists; avoid wildcards.

| feature_group | hydra_config                          | status (proposed/active/deprecated) | used_in (spread/total/both) | notes |
| ------------- | ------------------------------------- | ----------------------------------- | --------------------------- | ----- |
| standard_v1   | `conf/features/standard_v1.yaml`      | active                              | total (primary), spread (legacy) | Baseline opponent-adjusted set with weather + wind interactions and rating stats. |
| ppr_v1        | `conf/features/ppr_v1.yaml`           | active                              | spread                      | Points-per-rating features for current spread champion (spread_catboost_ppr). |
| recency_v1    | `conf/features/recency_v1.yaml`       | hold                                | spread                      | Recency-heavy variant used in earlier CatBoost runs; keep for ablation. |
| spread_top40  | `conf/features/spread_top_40.yaml`    | deprecated                          | spread                      | SHAP-pruned set from prior cycle; retained for reference only. |
| weather_v1    | `conf/features/weather_v1.yaml`       | proposed                            | both                        | Weather-focused sandbox; not validated on locked split. |
| points_for_pruned_union | `conf/features/points_for_pruned_union.yaml` | deprecated | both | Points-for architecture rejected in decision log; keep for historical comparison only. |

## Rules of Engagement

- When adding a new feature group, create the Hydra config **and** insert a row here in the same change.
- Mark target applicability explicitly (`spread`, `total`, or `both`), even if infrastructure is shared.
- If a group is removed from production usage, set status to `deprecated` (do not delete rows; preserve history).
- Align every experiment entry in `docs/experiments/index.md` with the feature group(s) used.
