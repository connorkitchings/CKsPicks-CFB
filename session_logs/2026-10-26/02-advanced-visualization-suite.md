# Session: Advanced Visualization Suite Planning

## TL;DR

- **Worked On:** Investigated database schemas, current chart architecture, and design options for expanding the site's visualization capabilities. Drafted a comprehensive Sol-to-Terra implementation contract for five new experimental visualizations across `/stats` and `/matchup`.
- **Outcome:** Decision-complete plan created at [`docs/plans/2026-10-26/02-advanced-visualization-suite.md`](../../docs/plans/2026-10-26/02-advanced-visualization-suite.md).
- **Plan Contract:** [`docs/plans/2026-10-26/02-advanced-visualization-suite.md`](../../docs/plans/2026-10-26/02-advanced-visualization-suite.md)
- **Approval / Status:** Draft; awaiting user authorization before implementation.
- **Blockers:** None. All required data fields already exist in verified release projection tables (`team_season_stats`, `team_resume`, `v5_rating_snapshots`, `predictions`, `games`). Zero migrations or pipeline changes are required.
- **Next:** User reviews the contract and authorizes implementation via the `implement-plan` skill in a fresh Terra task.

**tags:** ["charts", "visualizations", "stats", "matchup", "planning"]

## Context and Scope

The user requested an experimental expansion of the site's graphs and comparative visualizations. Investigation confirmed:
- `season_release_team_season_stats` already holds per-team, per-role, per-week observations for `early_down_epa`, `conv_rate_3rd_4th`, `scoring_opp_rate`, `pts_per_scoring_opp`, `epa_pass`, `epa_rush`, etc.
- `season_release_team_resume` already serves `sor`, `sor_rank`, `sos_played_elite`, and record data.
- `season_release_predictions` and `season_release_games` serve the weekly slate spreads, totals, and model forecasts.
- `season_release_matchup_data_publications` and existing matchup helpers calculate the Five Core Factors.

## Visualizations Specified in Contract

1. **Situational Football (`chart=downs`):** Standard Downs (Early Down EPA) vs. Passing Downs (3rd/4th Down Conversion Rate) with offensive/defensive toggles.
2. **Finishing Drives (`chart=finishing-drives`):** Scoring Opportunity Rate vs. Points per Scoring Opportunity (Red Zone Lethality).
3. **Resume vs. Dominance (`chart=resume-quality`):** V5 Rating Dominance vs. Strength of Record (SOR).
4. **Slate Market Board (`chart=market-board`):** 2D scatter of Market Spread/Total vs. Model Line with consensus diagonal and edge highlighting.
5. **Head-to-Head 5 Factors Tape:** Bi-directional comparative visual profile on `/matchup/[gameId]` across Efficiency, Explosiveness, Finishing Drives, 3rd/4th Down Conversions, and Turnover Margin.

## Validation

- [x] `git diff --check`
- [x] `uv run mkdocs build --strict`
