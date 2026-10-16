# Team Charts Methodology

> **Status:** Implemented locally on branch `connorkitchings/charts-module`, not yet committed or released. Charts go live with the first weekly release staged after the owner applies migration 0026 to Preview and Production and approves activation. Contract: [Charts module](../plans/2026-10-16/01-charts-module.md).

The **Charts** page shows three weekly team charts. They are descriptive analysis of completed games. They never feed ratings, forecasts, picks or grading, and they use no market data.

| Chart | What it shows |
| --- | --- |
| **Did We Really Get Beat That Bad?** | One bar per game of a single week: the winner's offensive success rate minus the loser's. The winner's logo sits at the bar tip; the loser's sits just across the zero line, opposite the bar. The label is the winner's abbreviation and the final score. Available from Week 0. |
| **Efficiency and EPA/play** | Cumulative success rate (x) against EPA/play (y) through Week N, offense or defense, with dashed FBS-average lines. Defense axes are inverted so up and right is better. Available from "Through Week 2". |
| **Opponent-adjusted EPA/play** | Adjusted offense (x) against adjusted defense allowed (y, inverted), with dashed play-weighted averages, diagonal equal-net lines and corner labels. Available from "Through Week 2". |

EPA/play is shown as an efficiency measure on the same axes as success rate. It is not presented as a standalone explosiveness measure.

## Definitions

- **Plays.** `scrimmage_play_mask` (`src/cks_picks_cfb/data/play_filters.py`): regulation scrimmage plays; garbage time, special teams, penalties, two-point tries, dead plays and kicking plays are excluded.
- **Games.** FBS-vs-FBS, regular season, completed. This is the same population as `build_team_season_stats` (`src/cks_picks_cfb/data/team_stats.py`).
- **Success rate** is the mean of the play-level `success` flag over eligible plays that have one.
- **EPA/play** is the mean `ppa` over eligible plays that have one; `ppa` is masked where `ppa_missing`.
- **Independent denominators.** Success and EPA each drop their own missing values, so `success_n`, `epa_n` and the eligible `plays` count differ. A metric with no valid observation is null, never zero.
- **"Through Week N"** means games in weeks `<= N`, stored as `as_of_week = N + 1`.
- **Roster and conference.** The published `team_season_roster` (pinned Silver `teams`, FBS classification) is the only list of teams and the only source of conference. Team logos, abbreviations and colors in `web/src/lib/team-logos.generated.ts` are display metadata only.

## Cutoff semantics: reconstruction, not a snapshot

Chart tables are recomputed from the release's pinned revision data and windowed by week only. They are **not** historical cutoff snapshots and make no claim about what was knowable at a given time. Each chart footnote says "reconstructed from this release's data".

## Venue-neutral, opponent-adjusted EPA/play

Implemented in `src/cks_picks_cfb/charts/adjusted_epa.py`, for each window from "Through Week 2" to the active week:

1. **Observations.** One per team-game offense: `y = epa_sum / epa_n`, weight `w = epa_n`, venue sign `s` (+1 home, -1 away, 0 neutral from the Silver neutral-site flag). Rows with `epa_n = 0` are excluded.
2. **Venue coefficient `h`.** Weighted least squares `y = mu + o_i + d_j + h*s`, with each observation row and its response scaled by `sqrt(w)` (`X_weighted = X * sqrt(w)[:, None]`, `y_weighted = y * sqrt(w)`; columns are never scaled separately). The design columns are `[intercept, off_0..off_N-1, def_0..def_N-1, s]` with teams sorted by name. One tolerance, `RCOND = max(X.shape) * eps`, drives both the rank computations and the fit. `h` is used only when it is identified: `rank(X) == rank(X without s) + 1`. Otherwise `h = 0` and `venue_identified` is false. Team effects are discarded.
3. **Neutralization.** Offense rows use `epa_sum - s*h*epa_n`; defense rows (EPA allowed, `s` from the defender's side) use `epa_sum + s*h*epa_n`.
4. **Opponent adjustment.** The unchanged V5 four-pass `adjust_possession_history` runs on the neutralized values. Its first return value is the neutral baseline.
5. **Ranks** are minimum ranks among roster teams per window and role (offense descending, defense ascending); `cohort_size` is the number of ranked teams.

Each `team_adjusted_epa` row stores the decomposition `raw - venue_correction - opponent_adjustment = adjusted`, plus the window's `venue_coefficient` and `venue_identified`. `games` counts the games that contributed EPA observations for that role. A team can have an offense row without a defense row, or the reverse; such a team is listed as "not plotted" rather than drawn.

## Release tables and verification

| Table | Content |
| --- | --- |
| `team_season_roster` | `season, team, conference` for every FBS team. |
| `team_game_stats` | One row per team per completed game: opponent, site, points, and offense and defense `plays`, `success_n`, `success_sum`, `epa_n`, `epa_sum`. |
| `team_adjusted_epa` | One row per `(as_of_week, team, role)` as described above. |

They ship in the `charts_v1` projection set, written atomically with the release (migration `contracts/migrations/0026_team_chart_tables.sql`). Releases staged before charts keep the `core_v1` set and are read back by their recorded set; new candidates must be `charts_v1`.

The `team_chart_reconciliation` verification check proves, from the payload alone: the roster is unique and contains every team; every game has exactly two mirrored rows; every cumulative window reproduces `team_season_stats` success rate, EPA/play, counts and games; and every stored adjusted value, rank and cohort size equals a full recomputation through the same entry point that built it, with exactly the expected set of windows, teams and roles.

## Reading the charts

- Dim logos are teams outside the selected conference filter; the searched team is enlarged with a ring.
- "Show as table" lists exactly the plotted rows. Teams without eligible games or valid observations are listed under the chart.
- Use the PNG export for sharing. Scatters export at 2000x1125 px; the net-success bars export at `max(2000, 140 + 30 x games)` px wide.
