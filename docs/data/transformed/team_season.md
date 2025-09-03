# Transformed Team-Season Schema

This schema describes the team-season dataset. The columns are the same metrics as the team-game data, but they are aggregated up to the season level as a season-to-date rolling average with recency weighting.

**Derived From:** `transformed/team_game.md`

## Schema

The key for this dataset is `(season, team)`.

* `games_played`
* All of the `off_*` and `def_*` metrics listed in the team-game schema (e.g., `off_sr`, `def_ypp`, etc.).
* `avg_luck_factor`: The team's average luck factor per game for the season.
* `cumulative_luck_factor`: The sum of the team's luck factor across all games in the season.
* Opponent-adjusted versions of the core metrics, which are stored in a separate dataset. See `opponent_adjusted.md`.
