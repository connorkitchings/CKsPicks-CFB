# Team Charts Methodology

> **Status:** Six-chart expansion under the approved [October 18 contract](../plans/2026-10-18/01-charts-review-and-expansion.md), with owner-selected 20+ yard rate and yards per successful play. Local implementation does not establish Preview acceptance or Production promotion; current serving state remains in [Current Status](../status.md).

The **Charts** page is available only with exact `CFB_CHARTS_ENABLED=1`. Every environment defaults off; disabled direct access returns HTTP 404. Eight team charts are implemented, including V5 rating trajectory and Possession efficiency ([contract](../plans/2026-10-18/03-charts-ratings-and-possession.md)). When enabled, the page shows five: Net success rate, Efficiency vs explosiveness, Adjusted PPA/play, Possession efficiency and Game log. By owner decision on 2026-10-18, Schedule adjustment and Team trajectory (not readable enough yet) and V5 rating trajectory (reserved for the Ratings tab) are implemented but not shown: `ready: false` in `web/src/lib/chart-config.ts` hides them from the picker, and a URL naming one falls back to Net success rate. Their methodology below is retained. They are descriptive analysis of completed games. They never feed ratings, forecasts, picks or grading, and they use no market data.

| Chart | What it shows |
| --- | --- |
| **Net success rate** | One bar per game of a single week: the winner's offensive success rate minus the loser's. The header and PNG export carry the credit "Concept by Parker Fleming: “Did We Really Get Beat That Bad?”". The winner's logo sits at the bar tip; the loser's sits just across the zero line, opposite the bar. The label is the winner's abbreviation and the final score. Available from Week 0. |
| **Efficiency vs explosiveness** | Cumulative success rate (x) against 20+ yard rate or yards per successful play (y) through Week N. Retained `charts_v1` releases show Success Rate vs PPA/play, with no explosiveness toggle. Offense or defense; defense axes invert so up and right is better. Available from Through Week 2. |
| **Adjusted PPA/play** | Adjusted offense (x) against adjusted defense allowed (y, inverted), with dashed play-weighted averages and corner labels relative to them. Available from "Through Week 2". |

| **Schedule adjustment** | Venue-neutral to opponent-adjusted PPA/play per team and role, Through Week N. The default national view shows the 15 largest and 15 smallest schedule effects, plus an extra highlighted row when needed; Show all displays every qualifying row. |
| **Team trajectory** | Adjusted net, offense or defense allowed across every stored Through Week window. Gray national context, conference-colored trajectories, and a bold highlighted team. |
| **V5 rating trajectory** | V5 model overall, offense or defense rating of every team after each week's games, Through Week 0 onward. Gray national context, conference-colored trajectories, a bold highlighted team, and a dashed weekly roster mean. |
| **Possession efficiency** | Opponent-adjusted offense (x) against defense allowed (y, inverted) in points per possession or PPA per possession, Through Week N, with possession-weighted averages and corner labels relative to them. Available from Through Week 2. |
| **Game log** | One team's completed FBS games over the whole release: offense and defense-allowed success rate, PPA/play or (with `charts_v2`) 20+ yard rate, final scores, weekly national references, and season-to-date values and ranks. |

PPA/play is an efficiency measure, not a standalone explosiveness measure. The owner selected both yardage measures after the [pinned Week 7 comparison](../research/chart-explosiveness-comparison-2026-10-16.md). Their public source is now the active release's companion yardage projection; no static research values are substituted for missing release capability.

## Definitions

- **Plays.** `scrimmage_play_mask` (`src/cks_picks_cfb/data/play_filters.py`): regulation scrimmage plays; garbage time, special teams, penalties, two-point tries, dead plays and kicking plays are excluded.
- **Games.** FBS-vs-FBS, regular season, completed. This is the same population as `build_team_season_stats` (`src/cks_picks_cfb/data/team_stats.py`).
- **Success rate** is the mean of the play-level `success` flag over eligible plays that have one.
- **PPA/play** is CFBD Predicted Points Added averaged over eligible plays with valid PPA; `ppa` is masked where `ppa_missing`. Internal `epa_*` field names and all calculations are retained. Yards per successful play is a yardage measure, not IsoPPP (points per successful play).
- **20+ yard rate** is the count of eligible plays with finite `yards_gained >= 20` divided by the count with finite yardage (`yards_n`). It does not use the play-type-dependent `explosive` flag.
- **Yards per successful play** is the sum of finite yardage on eligible plays with `success == 1`, divided by the count of those same plays (`success_yards_n`). It is not total yardage divided by successes. No sign constraint is imposed on the sum.
- **Independent denominators.** Success, PPA, yardage and successful yardage each drop their own missing values. Cumulative rates pool numerators and denominators rather than averaging game rates. Zero exposure gives null, never zero.
- **"Through Week N"** means games in weeks `<= N`, stored as `as_of_week = N + 1`.
- **Roster and conference.** The published `team_season_roster` (pinned Silver `teams`, FBS classification) is the only list of teams and the only source of conference. Team logos, abbreviations and colors in `web/src/lib/team-logos.generated.ts` are display metadata only.

## Cutoff semantics: reconstruction, not a snapshot

Chart tables are recomputed from the release's pinned revision data and windowed by week only. Cumulative profiles pool independent numerators and denominators through the selected week; adjusted charts read the matching stored window. Later source corrections may affect earlier reconstructed windows. They are **not** historical cutoff snapshots and make no claim about what was knowable at a given time. Each chart footnote says "reconstructed from this release's data".

## Venue-neutral, opponent-adjusted PPA/play

Implemented in `src/cks_picks_cfb/charts/adjusted_epa.py`, for each window from "Through Week 2" to the active week:

1. **Observations.** One per team-game offense: `y = epa_sum / epa_n`, weight `w = epa_n`, venue sign `s` (+1 home, -1 away, 0 neutral from the Silver neutral-site flag). Rows with `epa_n = 0` are excluded.
2. **Venue coefficient `h`.** Weighted least squares `y = mu + o_i + d_j + h*s`, with each observation row and its response scaled by `sqrt(w)` (`X_weighted = X * sqrt(w)[:, None]`, `y_weighted = y * sqrt(w)`; columns are never scaled separately). The design columns are `[intercept, off_0..off_N-1, def_0..def_N-1, s]` with teams sorted by name. One tolerance, `RCOND = max(X.shape) * eps`, drives both the rank computations and the fit. `h` is used only when it is identified: `rank(X) == rank(X without s) + 1`. Otherwise `h = 0` and `venue_identified` is false. Team effects are discarded.
3. **Neutralization.** Offense rows use `epa_sum - s*h*epa_n`; defense rows (PPA allowed, `s` from the defender's side) use `epa_sum + s*h*epa_n`.
4. **Opponent adjustment.** The unchanged V5 four-pass `adjust_possession_history` runs on the neutralized values. Its first return value is the neutral baseline.
5. **Ranks** are minimum ranks among roster teams per window and role (offense descending, defense ascending); `cohort_size` is the number of ranked teams.

Each `team_adjusted_epa` row stores the decomposition `raw - venue_correction - opponent_adjustment = adjusted`, plus the window's `venue_coefficient` and `venue_identified`. `games` counts the games that contributed PPA observations for that role. A team can have an offense row without a defense row, or the reverse; such a team is listed as "not plotted" rather than drawn.

## Release tables and verification

| Table | Content |
| --- | --- |
| `team_season_roster` | `season, team, conference` for every FBS team. |
| `team_game_stats` | One row per team per completed game: opponent, site, points, and offense and defense `plays`, `success_n`, `success_sum`, `epa_n`, `epa_sum`. |
| `team_adjusted_epa` | One row per `(as_of_week, team, role)` as described above. |
| `team_game_yardage` | Companion row for every `(season, game_id, team)` in `team_game_stats`; independent offense/defense `yards_n`, `explosive_n`, `success_yards_n`, `success_yards_sum`. |

The first three tables form `charts_v1` (migration 0026). `charts_v2` adds only the companion yardage table (migration 0027); prior columns and payload hashes are preserved. New candidates require `charts_v2` and the migration before staging. Retained `core_v1` and `charts_v1` releases retain their recorded table and verification sets. Capability detection uses the recorded set and existing relations; a `charts_v1` request never references the yardage relation. Every chart query is pinned to the same release as its capability; chart queries never fall back to mutable live tables.

The `team_chart_reconciliation` verification check proves, from the payload alone: the roster is unique and contains every team; every game has exactly two mirrored rows; every cumulative window reproduces `team_season_stats` success rate, PPA/play, counts and games; and every stored adjusted value, rank and cohort size equals a full recomputation through the same entry point that built it, with exactly the expected set of windows, teams and roles.

Yardage reconciliation at staging checks the exact team-game key population, offense/defense mirrors, nonnegative integer counts and exposure bounds. The prepare-time `chart_yardage_recomputed` check independently rebuilds the candidate yardage from the pinned, checksum-verified byplay. Its passing evidence binds the source URI/hash, projected row count and projection hash to the sealed candidate. Staging verifies that binding without fetching plays. Structural agreement alone is insufficient: a matching error in both mirrored rows must fail play-level recomputation.

## Schedule and trajectory interpretation

Schedule adjustment isolates opponent effects: `neutral = raw - venueCorrection`. Its better-is-positive effect is `adjusted - neutral` on offense and `neutral - adjusted` on defense. Positive means the venue-neutral performance understated the team against tougher opponents; negative means it was inflated against weaker opponents. The graph does not attribute venue corrections to schedule strength. Rows sort by effect descending, then team name. Boundary ties resolve by name; small groups show each team once. Defense uses allowed values and an inverted horizontal axis.

Trajectory uses Through Week (`as_of_week - 1`) from Week 2 onward, with no week selector. Net is adjusted offense minus adjusted defense allowed. Missing windows create gaps, never interpolated values; a lone observation is a dot. The dashed reference is the national play-weighted average for each stored window and metric, computed before conference filtering. Endpoint logos may be displaced for readability with connectors to their true values. Defense's vertical axis is inverted.

Game logs cover completed FBS-vs-FBS regular-season games in the whole release, ordered by week and game ID. Offense and defense-allowed panels share the game order; defense is inverted. Each game's dashed reference pools all eligible national team-games in that week. Season headers use the release's latest charted week and national competition ranks, independent of conference filters. Missing metric exposure leaves the game and its result visible with an `n/a` value. The default team has the highest adjusted net in the latest stored window, ties by name; with no eligible adjusted profile, use the first qualifying team with games. The team picker can select any eligible roster team in the selected group.

## V5 rating trajectory and possession efficiency

Both charts read core release tables (`v5_rating_snapshots`, `team_possession_adjusted`) that every atomic release carries, so they work on `charts_v1` and `charts_v2` releases alike. Unlike the chart tables above, these rows are the V5 model's own as-of state and inputs, not a chart reconstruction.

- **Rating trajectory.** One point per roster team per `current` snapshot `week` (the rating after that week's games), plotted at Through Week `week` from Week 0, with no week selector. Every component is higher-is-better: the materializer stores defense as `-(allowed - center) / scale`, and `overall_rating = (offense_rating + defense_rating) / 2`. On the Preview active release of 2026-10-18, current Week 7 `defense_rating` correlates -0.81 with Through Week 7 adjusted PPA per possession allowed, so no axis is inverted. Ratings are on the model's rating scale, not PPA/play, and are not centered at zero; the dashed reference is each week's unweighted mean over roster teams with a snapshot, computed before conference filtering. A missing team-week is a gap, never interpolated; a lone week is a dot. Tooltips show the rating ± one standard deviation (`sqrt(variance)` of the selected component) and the weekly national competition rank among roster teams with a snapshot (ties share the minimum rank).
- **Possession efficiency.** For Through Week N (`as_of_week = N + 1`, from Through Week 2) and the selected measurement (`ppp`, or PPA per possession stored as `epa_per_possession` and built from the CFBD `ppa` play column; the site says PPA, and `metric=epa_per_possession` and `metric=ppa_per_possession` both select it), a team is plotted when it has both an offense row and a defense row with an adjusted value; the rest are listed as not plotted. Unlike the FBS-vs-FBS chart tables, the adjuster runs over every game, FCS opponents included (rows are emitted for FBS teams only), so the subtitle reads "FBS teams, all games"; the rating trajectory's reads "FBS teams". Defense values are allowed, with the vertical axis inverted so up and right is better. The dashed lines are per-role averages weighted by `primary_exposure` (possessions) over the plotted teams. Ranks are competition ranks over the plotted teams (offense higher first, defense allowed lower first); they equal the stored `adjusted_rank` whenever every ranked team is plotted. Tooltips show raw value, adjusted value, opponent adjustment, games and both ranks.

## Reading the charts

- The conference/group filter limits qualifying bars, scatter points, schedule rows and game-log team choices. Net-success games qualify when either team belongs to the group; this chart has no team finder. Trajectory retains faint national context while coloring the selected conference. PNGs follow each view's displayed population.
- Scatter domains and play-weighted FBS averages use the full eligible national population before filtering. They change with the week/side, never with filtering or highlighting. Scatters draw no equal-net diagonals and no in-chart note; the corner labels read relative to the dashed averages, as each footnote says.
- Scatter tooltips that show ranks use national competition ranks computed independently for each plotted metric (ties share the minimum rank, so 1, 1, 3). Offense ranks higher values first; defense allowed ranks lower values first. No combined scatter rank is defined.
- Search narrows the highlight dropdown. Select one team or activate its logo by click/tap, Enter or Space to enlarge and label it; activate the same logo again or choose None to clear. Hover/focus tooltips are transient. Conference exclusion clears a selection; week navigation preserves it and reports when its observation is unavailable.
- Net success is the winner's success-rate advantage or disadvantage in percentage points. A negative bar means the winning team had the lower offensive success rate. Bars are ordered by that success gap, ascending (ties by game ID); the order is fixed, with no sort control.
- The visible charts have no table view. Teams without eligible games or valid observations are listed under the chart.
- Use the PNG export for sharing: the icon buttons at the right of the controls row download the PNG or, where the browser allows it, copy the image. Scatter, trajectory and game-log cards export at 2000x1125 px; net-success bars export at `max(2000, 140 + 30 x games)` px wide. Schedule cards grow vertically with the displayed rows. Static exports omit interactive focus outlines and include window, group and selected metric.
