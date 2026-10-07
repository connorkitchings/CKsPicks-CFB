# Preview vs Production `team_season_stats` (read-only, captured 2026-10-07)

Rows: Preview 11,506, Production 10,460. Same 2026 teams per week (16/94/137/138/138), same `source_versions`.

- **Extra rows (1,046, Preview only):** the `ppa_per_play` metric, offense and defense, 523 team-weeks each. Production has no `ppa_per_play`.
- **Changed rows (2,923 shared rows in three metrics):** `conv_rate_3rd_4th`, `explosive_rate`, `turnover_rate`. Of the 2,454 shared rows where the play count `n` differs, Preview `n` is lower in all of them (never higher); game counts never differ. Largest value change: 0.10 (3rd/4th-down conversion rate, Weeks 2-3).
- **Unchanged on every row:** `avg_start_field_pos`, `early_down_epa`, `epa_pass`, `epa_rush`, `pts_per_scoring_opp`, `scoring_opp_rate`, `success_rate`.
- **Publish times:** Production 2026-10-02 15:25Z, Preview 2026-10-02 18:39Z.

Matches the documented punt-return fix (`docs/plans/2026-10-02/03-team-stats-feeds-ratings.md`, known issues #2 and the 2026-10-02 entry): excluding `Punt Return` rows lowers play counts, adds `ppa_per_play`, and leaves the listed unaffected metrics identical. Conclusion: Preview has the fix; Production still serves the pre-fix 2026-10-02 15:25Z stats until the Window 1 production republish. `source_versions` does not record the play filter, so identical versions do not show the code differs.
