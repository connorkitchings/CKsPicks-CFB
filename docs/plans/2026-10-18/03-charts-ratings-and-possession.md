# Charts 7 and 8: V5 rating trajectory and Possession efficiency

**Status:** In Progress — code complete and released hidden behind `CFB_CHARTS_ENABLED` (live `/charts` returns 404). Remaining before publication: real-data visual review, Preview acceptance and the owner's publication decision, tracked in [Charts pre-publication verification](../2026-10-20/03-charts-pre-publication.md). `rating-trajectory` stays `ready: false` by owner decision. Earlier record: approved by the owner on 2026-10-18. Data layer, views (`RatingTrajectoryView`, `PossessionView`, on a shared `TrajectoryPanel`), page wiring, unit tests and e2e implemented locally; `possession` is `ready: true` behind `CFB_CHARTS_ENABLED`; `rating-trajectory` is implemented but `ready: false` (not shown on /charts) by owner decision on 2026-10-18, reserved for a later move to the Ratings tab. The real-data look is part of the deferred visual verification; CI on `dev` and `main` is green. Owner controls commits, merges, migrations, Preview rehearsal and Production.

- **Created:** 2026-10-18
- **Decision source:** Owner chose these two charts on 2026-10-18, after the 6-chart expansion ([01-charts-review-and-expansion.md](01-charts-review-and-expansion.md)) became code-complete.
- **Scope:** Web only. No migration, no new projection set, no Python change. Both charts read tables that every atomic release already carries (`v5RatingSnapshots`, `teamPossessionAdjusted`, `CORE_RELEASE_TABLES` in `web/src/lib/season-release-query.ts`), so they work on `charts_v1` and `charts_v2` releases alike. Charts stay behind `CFB_CHARTS_ENABLED`.

## Data check (read-only, Preview active release `preview-season-2026-b1e0ac13c88baf86b97ab213`, 2026-10-18)

**`season_release_v5_rating_snapshots`**
- `snapshot_class = 'current'`: exactly 138 rows (one per roster team) for each `week` 0 through 7, one `cutoff_utc` per week, no `fallback_reason`. Each is the rating after that week's games, so `week = N` is "Through Week N".
- `snapshot_class = 'pregame'`: 138 rows per `week` 0 through 8, one per team-week (1,242 rows, 1,242 distinct team-weeks). Pregame week 8 is effectively the same state as current week 7, so it is not plotted. One row has `fallback_reason = 'no_predecessor'` (pregame week 0).
- Teams on a bye still have a `current` row each week (the rating carries forward by the model), so there are no gaps today. The chart still treats any missing team-week as a gap, never an interpolated value.
- Ratings are **not centered at zero**: current-snapshot means are overall 0.409, offense 0.417, defense 0.402 (overall range −1.02 to 2.06). The reference line is therefore the unweighted mean over the displayed roster teams for each week, computed before conference filtering, like the PPA trajectory.
- `overall_variance`, `offense_variance` and `defense_variance` are stored, so the tooltip can show rating ± one standard deviation (`sqrt(variance)`).

**`season_release_team_possession_adjusted`**
- `as_of_week` 1 through 8 present; `measurement_id` in `ppp` and `epa_per_possession`; both roles. `adjusted_rank` and `cohort_size` are populated on every row.
- Coverage by window: `as_of_week` 1 has 14-15 teams and 2 has 77-90, so they are too thin to chart. From `as_of_week` 3 (Through Week 2) offense and defense have 118-130 teams, reaching 138 by `as_of_week` 5-8 (a few teams lack an `epa_per_possession` row until then).
- This matches the existing convention: "Through Week N" is `as_of_week = N + 1`, available from Through Week 2.

## Chart 7: V5 rating trajectory (`rating-trajectory`)

- Group: Teams. Controls: metric `overall | offense | defense`, conference/group filter, `team=` highlight. No week selector (all stored windows are shown).
- Series: one point per team per `current` snapshot `week` 0..7, plotted at Through Week N. **`defense_rating` is higher = better defense** (verified 2026-10-18). In `src/cks_picks_cfb/ratings/possession_rating_materializer.py` the defense observation is `-(allowed - center) / scale` ("defense sign reversal") and `overall_rating = (offense_rating + defense_rating) / 2`. On the Preview active release, current Week 7 `defense_rating` correlates -0.81 with Through Week 7 (`as_of_week = 8`) adjusted `epa_per_possession` allowed across 129 teams (offense rating vs offense PPA/possession: +0.85); the top defense ratings (Texas, LSU, TCU) allow the least. Offense, defense and overall are all higher-is-better, so no axis is inverted.
- Reuse `TrajectoryChart.tsx` by generalizing its series input (gaps, lone-point dots, conference coloring, highlighted team, endpoint logo displacement already exist). The dashed reference is the weekly unweighted roster mean for the selected metric.
- Tooltip: team, Through Week, rating, ± standard deviation, rank among displayed roster teams for that week (competition ranking; ties share a rank).
- Table view: team, week, rating, standard deviation. PNG export at 2000x1125 like the other trajectory cards.
- Caption must say ratings are V5 model ratings on the rating scale, not PPA, and that they are not centered at zero.

## Chart 8: Possession efficiency (`possession`)

- Group: Teams. Controls: Through Week N (2 through the active week), metric `ppp | epa_per_possession` (shown as PPA/possession; `ppa_per_possession` is accepted as an alias), conference/group filter, `team=` highlight.
- Marks: scatter of adjusted offense (x) against adjusted defense allowed (y, inverted so up and right is better), one point per team with both roles present for that window and measurement. Teams missing either role are omitted and counted in the footnote.
- Reuse `ScatterView`/`ScatterChart` the way `AdjustedView.tsx` does: dashed pooled-average lines with corner labels relative to them, competition ranks from `adjusted_rank` (recomputed in the transform if the displayed population changes), PNG export. By owner decision (2026-10-18) the visible scatters have no equal-net diagonals, no in-chart note and no table view. The pooled average is weighted by `primary_exposure` (possessions) per role.
- Tooltip: raw value, adjusted value, opponent adjustment, games, offense and defense rank.
- Caption states the measurement (points per possession or PPA per possession), that values are opponent-adjusted, and the Through Week window.

## Implementation plan

1. `web/src/lib/chart-config.ts`: add `rating-trajectory` and `possession` to `ChartKind` and `CHART_REGISTRY` (group Teams, parameters, defaults).
2. `web/src/lib/charts.ts`: pure transforms `ratingTrajectorySeries` and `possessionPoints`.
3. `web/src/lib/chart-queries.ts`: queries through the release-pinned `getChartsDb`, selecting `current` snapshots for the season and the `teamPossessionAdjusted` rows for one window. The roster comes from the existing roster query.
4. Views/components: a thin `RatingTrajectoryView`, a `PossessionView` modeled on `AdjustedView.tsx`, and the generalization of `TrajectoryChart.tsx`. Load the `dataviz` skill before writing chart code.
5. Fixtures in `web/src/test/fixtures/charts.ts`; methodology entries in `docs/modeling/team_charts_methodology.md`.
6. Registry-driven gate: new kinds must 404 with the flag off (`test:charts-gate`).

## Acceptance

- Unit tests (`test:publication`): gaps, metric switching, rank ties, missing windows or roles, mean reference computed before group filtering, exposure-weighted averages, sign and inversion.
- e2e (`test:ui`): both kinds render, the possession table view is absent (the skipped rating-trajectory spec keeps its `openTable` checks), keyboard tooltip, PNG export, `team` persists across chart switches.
- `test:charts-gate`, `lint`, `typecheck`, `build` pass; fixture screenshots (`CFB_CHART_VISUALS=1`) inspected at desktop and 390px in both themes; real-data look on Preview with `CFB_CHARTS_ENABLED=1 make web-local ENV=preview`; CI on `dev` green.

## Owner decisions

1. The rating trajectory includes Through Week 0 (current snapshots for weeks 0 through 7 are plotted at Through Week N).
2. The possession chart starts at Through Week 2 (`as_of_week >= 3`), like the other adjusted charts.
