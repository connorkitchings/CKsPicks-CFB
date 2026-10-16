# Charts module: weekly team charts

- **Status:** In Progress. Tasks 1–7 committed; Preview prepared, verified, activated and inspected. Follow-up chart organization, PNG focus-ring fixes and accepted baseline logo spacing are committed and pushed to `dev` at `b2335ae5`. Production remains separately owner-gated.
- **Created:** 2026-10-16
- **Approval source:** Owner approved revision 3 of the plan in chat on 2026-10-16, after two owner code reviews.
- **Implementation log:** `session_logs/2026-10-16/02-charts-module-implementation.md` (planning log: `session_logs/2026-10-16/01-charts-module-planning.md`)
- **Branch:** `connorkitchings/charts-module`
- **Baseline:** `dev` at `a08bf6f3`, clean. Active release `production-season-2026-d0272a48d3a0252fd4196db3`; Week 7 active; Week 8 pending Sunday finals. **Week 8 is an optional delivery opportunity, not a deadline**; weekly release scope does not expand to accommodate charts.

## Context

The site has Picks, Results, Ratings and Performance but no visual team analysis. The owner wants a **Charts** section with three weekly charts modeled on reference images:

1. **Did We Really Get Beat That Bad?** (Parker Fleming): one bar per game in a single week. Value = winner's offensive success rate minus loser's offensive success rate. Winner logo at the bar tip, loser logo just across the zero line opposite the bar, x-label `WINNER_ABBR w-l` (owner-requested placement amendment 13).
2. **Efficiency and EPA/play** (offense and defense; reference title "Explosiveness and Efficiency"): cumulative success rate (x) vs EPA/play (y), FBS-vs-FBS, logo markers, dashed FBS-average lines. Axes labeled "Success Rate" and "EPA/play"; EPA/play is not presented as a standalone explosiveness measure. Defense axes inverted so good is up and right.
3. **Opponent-adjusted EPA/play** (jbuddavis-style): adjusted offense (x) vs adjusted defense allowed (y, inverted), dashed averages, diagonal equal-net lines, "Good/Bad Offense/Defense" corner labels. No hand annotations.

Owner decisions (2026-10-16): new atomic release projection tables; adjusted EPA/play built on the existing V5 iterative adjuster with a venue step; all FBS teams with conference/P4 filter and team search, conference from published data; scatters start at Through Week 2, the single-week bar chart from Week 0.

Revision 3 incorporates two owner code reviews: independent valid-observation denominators; versioned projection sets with recorded-set readback for retained releases and `charts_v1`-only staging; release-scoped chart CTEs; a published FBS roster; a jointly estimated venue coefficient with one tolerance policy; verification by full recomputation; descriptive-reconstruction semantics; an achievable model-isolation test; and the UI gaps.

Session routing: schema, release pipeline and web follow the repo `plan-session` workflow. The planning session's only action is persisting this contract and its session log. No implementation in the planning session.

Delivery order (authoritative, mirrored in Ordered tasks): metric definitions and adjustment specification → release compatibility → builders/schema → verification → web → operational rehearsal.

## 1. Metric definitions and semantics

- Plays: `scrimmage_play_mask` (`src/cks_picks_cfb/data/play_filters.py:83`), garbage time excluded; games FBS-vs-FBS, regular season, completed — identical to `build_team_season_stats` (`src/cks_picks_cfb/data/team_stats.py:222`).
- Success and EPA validity follow `_role_rows` (`team_stats.py:162`) exactly: EPA = `ppa` coerced numeric, masked where `ppa_missing`; success coerced numeric; each metric drops its own missing values independently. A metric with zero valid observations is null, never 0.
- "Through Week N" = weeks `≤ N` = `as_of_week = N + 1`.
- **Cutoff semantics: descriptive reconstruction.** Chart tables are recomputed from the release's pinned revision data, windowed by week only. They are not historical cutoff snapshots and make no availability claim; the methodology footnote says "reconstructed from this release's data". They never feed ratings, forecasts or grading.
- **Isolation:** all chart code lives in a new module `src/cks_picks_cfb/charts/` (`roster.py`, `team_game_stats.py`, `adjusted_epa.py`). It calls `adjust_possession_history` (`ratings/possession_measurements.py:1383`) unchanged. No edits to the shared adjuster, V5 measurements, ratings, forecasts, or existing projection builders.

## 2. Adjustment specification

For each `as_of_week` from 3 (Through Week 2) to `active_week`, over FBS-vs-FBS game observations with weeks `< as_of_week`:

**Observations.** One per team-game-offense: `y = epa_sum / epa_n`, weight `w = epa_n`, offense team `i`, defense team `j`, venue sign `s = +1` home, `−1` away, `0` neutral (Silver games' neutral-site flag). Rows with `epa_n = 0` excluded.

**Venue coefficient (joint estimate).** Weighted least squares `y = μ + o_i + d_j + h·s`. Team effects are identified only up to per-component constants; `h` is used, `o`/`d` are discarded.
- **Column layout (shared by implementation and tests):** `X = [intercept, off_0 … off_{N−1}, def_0 … def_{N−1}, s]`, where `N` teams are those appearing in the window's observations, sorted by team name. The intercept together with full offense and full defense indicator sets is deliberately rank-deficient; the rank condition below accounts for this.
- **Weighting:** scale each observation row and its response, not the parameter columns:
  `X_weighted = X * np.sqrt(w)[:, None]` and `y_weighted = y * np.sqrt(w)`. Use `X_weighted` for rank detection and least-squares fitting, with `y_weighted` as the response. Do not separately scale columns.
- **One tolerance policy:** `RCOND = max(X_weighted.shape) · float64 eps`, relative to `σ_max(X_weighted)`. Use `numpy.linalg.matrix_rank(·, rtol=RCOND)` (numpy 2.2.6 is locked; do not use the deprecated `tol`) for both rank computations, and `numpy.linalg.lstsq(·, rcond=RCOND)` for the fit.
- **Identification (authoritative):** `h` is identified iff `rank(X_weighted) == rank(X_weighted without the s column) + 1` under that policy. Otherwise `h = 0`, `venue_identified = false`. No other heuristic (e.g. home/away variation per component) substitutes for the rank condition.

**Neutralization (chart-only).** Offense rows `numerator_neutral = epa_sum − s·h·epa_n`; defense rows (EPA allowed; `s` from the defending team's perspective) `numerator_neutral = epa_sum + s·h·epa_n`.

**Opponent adjustment.** Unchanged `adjust_possession_history` with `measurement_id='epa_per_play'`, `numerator=numerator_neutral`, `denominator=epa_n`. Its first return value (its "raw") is therefore the **neutral** baseline: store it as `neutral_epa_per_play`. The builder computes `raw_epa_per_play = Σepa_sum / Σepa_n` itself, from the un-neutralized sums, before neutralization. Ranks among roster FBS teams in the window (`method="min"`): offense descending, defense ascending; `cohort_size` = ranked teams per window/role.

**Stored decomposition per team/role:** `raw_epa_per_play`, `venue_correction` (team-specific signed, `raw − neutral`), `neutral_epa_per_play`, `opponent_adjustment` (`neutral − adjusted`), `adjusted_epa_per_play`, plus window `venue_coefficient` and `venue_identified`. Identity: `raw − venue_correction − opponent_adjustment = adjusted`.

Arithmetic example: home offense 0.4 over 60 plays, away 0.0 over 40, given h = 0.2 → both neutralize to 0.2; pooled mean 0.20 vs raw 0.24. Comparisons are against the neutralized baseline, never raw.

## 3. Release compatibility

Problems: `_readback` (`src/cks_picks_cfb/season/release.py:250`) requires `set(checks) == set(PROJECTION_KEYS)`; the web resolver (`web/src/lib/season-release-context.ts:51-56`) requires every registered relation; `seasonReleaseDb()` (`web/src/lib/season-release-query.ts:18`) builds release CTEs from one fixed list.

**Python.**
- `season/projection_common.py`: `PROJECTION_SETS = {"core_v1": <current 18 tables, current order>, "charts_v1": core_v1 + ("team_season_roster", "team_game_stats", "team_adjusted_epa")}`; `STAGING_PROJECTION_SET = "charts_v1"`; `PROJECTION_ORDER = PROJECTION_SETS["charts_v1"]`.
- A helper `recognized_projection_set(keys)` returns the set name whose tables exactly equal `keys`, else raises. Unknown or partial sets always fail.
- **Retained releases (readback, activation readback, rollback):** `_readback` uses the release's recorded `projection_checks`, requires a recognized set, and reads back exactly that set's tables. Recorded checksums are never rewritten.
- **New candidates (`validate_candidate`, `_check_projection_scope`, `stage_release`):** require exactly `charts_v1` and the `team_chart_reconciliation` verification check; `core_v1` candidates are refused at staging.

**Web.**
- Split the registry into `CORE_RELEASE_TABLES` (unchanged 18) and `CHART_RELEASE_TABLES` (`teamSeasonRoster`, `teamGameStats`, `teamAdjustedEpa`). The resolver probes only core relations (existing behavior unchanged).
- `SeasonReleaseContext` gains `chartsAvailable` = all chart relations exist **and** the active release's `projection_checks` keys equal `charts_v1` (read in the same resolver query that pins the release).
- `seasonReleaseDb(db, releaseId, { charts })` adds the chart CTEs (same `season_release_<name> WHERE release_id = …` pattern, same request-pinned `releaseId`) only when `charts` is true. Chart queries are built only from a release-scoped db with charts enabled; with no active release or `chartsAvailable = false` they are not executed (never fall back to live tables).

**Tests.**
- Web unit: CTE builder emits chart CTEs only with `charts: true` and binds the same release id (extend `season-release.test.ts`); resolver sets `chartsAvailable` false for a `core_v1` release or missing relations.
- Postgres (disposable cluster): live chart tables seeded with deliberately different values than release projections → chart queries return release values. Stage+activate a `charts_v1` release over the active `core_v1` release; owner rollback to the `core_v1` release passes readback and core page queries return the old release's rows with `chartsAvailable = false`; return to the chart release via the authorized rollback path (it is `rolled_back`, so ordinary activation refuses it) and verify readback. Staging a `core_v1` or partial-set candidate fails. Resolver on a database without migration 0026 serves core pages with `chartsAvailable = false`.

## 4. Builders and schema

### `team_season_roster` (published FBS roster)
`season, team, conference`. Natural key `(season, team)`. Source: pinned Silver `teams` with FBS classification (same source as `_fbs_teams`, `season/projection_football.py:291`), conference from `normalize_teams` (`data/silver/builders.py:592`). Always non-empty for a `charts_v1` candidate. This is the authoritative "all FBS teams" list and the only conference source for charts.

### `team_game_stats` (one row per team per game)
`season, week, game_id, team, opponent, site ('home'|'away'|'neutral'), points_for, points_against`, and for `off_`/`def_`: `plays` (eligible), `success_n`, `success_sum`, `epa_n`, `epa_sum`. Natural key `(season, game_id, team)`, sorted by key. Weeks: completed weeks `< active_week`. Every `team` and `opponent` must be in the roster.

### `team_adjusted_epa` (per as_of_week, team, role)
`season, as_of_week, team, role, raw_epa_per_play, venue_correction, neutral_epa_per_play, opponent_adjustment, adjusted_epa_per_play, venue_coefficient, venue_identified, epa_n, games, adjusted_rank, cohort_size, adjustment_method ('iterative_4pass_venue_v1')`. Natural key `(season, as_of_week, team, role)`. Rows exactly for `(as_of_week, team, role)` combinations of roster teams whose role-specific cumulative `epa_n > 0` in the window; a team may have an offense row without a defense row or vice versa.

### Schema and wiring
- Migration `contracts/migrations/0026_team_chart_tables.sql`: live + `season_release_*` copies with `release_id` in PK, immutability trigger, REVOKE/GRANT per 0025.
- Update canonical `contracts/schema.sql` and `contracts/schema.ts`, then `web/src/lib/schema.ts`; `make contracts-check`.
- `season/projection_football.py`: builders in `FOOTBALL_KEYS`, `ROW_KEYS`, `INTEGER_COLUMNS`, `_columns`; deterministic values/sort per `projection_common.py:1-99`. `release.PROJECTION_KEYS` gains the three keys.
- Non-empty requirements: roster always; `team_game_stats` when `active_week > 0`; `team_adjusted_epa` only when `active_week ≥ 3`. None added to the unconditional list.

## 5. Verification

New check `team_chart_reconciliation` (in both `REQUIRED_PROJECTION_CHECKS` and `_PROJECTION_CHECKS`, `season/verification.py`), required for `charts_v1` candidates:
- **Roster:** unique teams; every `team_game_stats` team/opponent and every adjusted team in the roster.
- **Game rows:** exactly two rows per game; team A's `off_*` equals team B's `def_*` field-for-field; points and sites mirrored (home↔away, neutral↔neutral).
- **Cumulative reconciliation:** for each `as_of_week` in `team_season_stats`, window sums reproduce `success_rate`, `ppa_per_play`, their `n`, and `games` (tol 1e-9; null where n = 0).
- **Adjusted recomputation:** for each expected window (`as_of_week` 3..`active_week`), reconstruct observations from `team_game_stats`, recompute `h`/identification, neutralization, the unchanged four-pass adjustment, ranks and cohort sizes using the same `src/cks_picks_cfb/charts/adjusted_epa.py` entry point, and compare every stored column (floats tol 1e-9; ranks, cohort sizes, `games`, `epa_n`, `venue_identified` exact).
- **Coverage:** stored `(as_of_week, team, role)` set equals the expected set: for each expected window, the roster team/role combinations whose role-specific cumulative `epa_n > 0`. Each role is required only where observed; no extra or missing windows.

## 6. Web

### Route, data, navigation
- `/charts?chart=net-success|efficiency|adjusted&side=offense|defense&week=N`. Async server page (pattern `web/src/app/ratings/page.tsx`, `revalidate = 300`); test-mode fixture under `src/test/fixtures/`.
- States: `chartsAvailable = false` → "Charts arrive with the next weekly release"; supported release with an empty window → that week is not offered; query error → unavailable card. Default: latest available week per chart.
- "Charts" added to `SiteNav.tsx` (`items`, `NavIcon`, mobile `grid-cols-5`). `containerClass` (`SiteNav.tsx:94-96`) treats `/charts` as `sm:max-w-6xl`, and the page wrapper uses `max-w-6xl` so nav and chart widths line up.
- Week coercion (in the page, using a pure helper in `charts.ts`): if the requested `week` is not available for the selected chart (for example, switching from net-success Week 0 to efficiency), use the nearest available week for that chart, or the latest if none is near. Tab links carry the coerced week.
- `WeekNav.tsx` gains a serializable `labelMode: "week" | "through-week"` prop (default `"week"`); URLs keep `week=N`.
- Queries (`web/src/lib/queries.ts`, cache-wrapped, release-scoped with charts enabled): `getTeamSeasonRoster(season)`, `getTeamGameStats(season)` (~1.5k rows), `getTeamAdjustedEpa(season, asOfWeek)`.

### Pure transforms (`web/src/lib/charts.ts`)
- `netSuccessBars(rows, week)`: one bar per game; winner = higher points (equal points → "not charted" list as a data error). Value = winner off SR − loser off SR; either SR null → "not charted". Negative bars below zero; zero rendered as a hairline. Sort by value asc, then `game_id`.
- `efficiencyPoints(roster, rows, throughWeek, side)`: team SR/EPA from window sums; FBS averages from pooled sums. Unavailable teams = roster minus plotted teams (no eligible games or null metric), listed under the chart.
- `adjustedPoints(roster, rows)`: a point only when both offense and defense adjusted values exist; play-weighted means, diagonal iso-net lines clipped to domain; unavailable teams = roster minus plotted teams (including teams with only one role).
- Conference filter from roster; P4 = ACC, Big Ten, Big 12, SEC plus Notre Dame. Tick/domain helpers; deterministic ordering throughout.

### Rendering (`web/src/components/charts/`)
- Hand-written SVG, no new dependency: `ChartsView` (client: tabs, side toggle, conference filter, search), shared `ScatterChart` (axis inversion, mean lines, optional diagonals), `NetSuccessChart`.
- Markers: `<image href={logoSrc(...)}>` (`web/src/lib/team-logos.ts`) with initials fallback; filtered teams at 15% opacity; searched team enlarged with ring.
- Accessibility: each marker/bar focusable (`tabIndex=0`, `role="img"`, `aria-label` with team and values); tooltip on hover, focus and tap; arrow keys move between points in sort order; "Show as table" toggle renders a sortable data table of the same rows.
- Mobile: scatters scale via `viewBox`; net-success becomes horizontal bars below `sm`.
- Tokens from `globals.css`; bar fill = team primary color with contrast fallback.
- PNG export follows `matchup/ShareButton.tsx`'s off-screen card and `html-to-image` flow, with a chart-specific settle step: `ShareButton`'s `settle()` (`ShareButton.tsx:34`) only queries HTML `img`, and `SVGImageElement` has no `decode()`. The chart settle step collects every `href` from SVG `image` elements (plus any `img`), preloads each through `new Image()` + `decode()` (errors ignored), and waits for `document.fonts.ready` before capture. Logos are same-origin (`/logos/v2/`), so `html-to-image` can inline them. Keep the Safari double-render. Scatters 2000×1125; net-success width `max(2000, 140 + 30·games)`. Subtitle e.g. "Offense | 2026 | FBS vs FBS | Through Week N"; footnote with definitions and "reconstructed from this release's data".

### Team metadata
Extend `web/scripts/build-team-logos.mjs`/`team-logos-lib.mjs` to keep CFBD `abbreviation`, `color`, `alt_color` in `team-logos.generated.ts`; add `teamAbbr(name)`, `teamColor(name)` to `team-logos.ts` with fallbacks. Display metadata only; conference never comes from here.

## Ordered tasks
1. Metric/adjustment module `src/cks_picks_cfb/charts/` (definitions, roster, venue estimator, adjustment) with unit tests.
2. Release compatibility: projection sets, recorded-set readback, `charts_v1`-only staging; web registry split, `chartsAvailable`, chart CTEs; unit tests.
3. Migration 0026, canonical `schema.sql`/`schema.ts`, web schema copy; projection wiring; Postgres compatibility and rollback tests.
4. Verification check `team_chart_reconciliation` with negative tests.
5. Web: team metadata, `charts.ts` + tests, queries, components, page, nav, WeekNav `labelMode`, fixtures.
6. Playwright `/charts` spec; add `/charts` to `e2e/logos.spec.ts`.
7. Docs: methodology section, measurement catalog entries, runbook note (apply 0026 to Preview then Production before staging; staging now requires `charts_v1`).
8. Operational rehearsal (owner-gated, whenever ready): next weekly prepare → Preview stage/activate → inspect `/charts` → Production per runbook.

## Validation
- Python unit tests:
  - Definitions: garbage excluded; FBS-only; `ppa_missing` and missing success counted independently (fixture with `epa_n ≠ success_n ≠ plays`); zero-observation metric null; mirrored rows; neutral site; roster includes a team with no completed games.
  - Venue estimator: unequal teams on an unbalanced schedule with known `o`, `d`, `h` recovers `h` (noiseless, tol 1e-9) while the naive home-minus-away average differs on the same fixture; all-neutral window → `h = 0, identified = false`; disconnected schedules → outcome asserted against the rank condition only; a near-collinear fixture exercises `RCOND`; the weighting test asserts row-wise √w scaling of `X` and `y` (no column scaling).
  - Raw vs neutral: with a nonzero `h`, stored `raw_epa_per_play` equals the un-neutralized `Σepa_sum/Σepa_n` and differs from `neutral_epa_per_play`.
  - Adjustment: equals `adjust_possession_history` on the neutralized baseline; decomposition identity; `h = 0` path equals plain adjustment of raw.
  - One-role coverage: fixture team with valid offensive EPA but no valid defensive EPA (and the reverse) gets only the observed role's row, passes coverage verification, and appears in the web unavailable list rather than as a scatter point (also covered in `charts.test.ts`).
  - **Model isolation:** for identical pinned inputs, ratings and forecast numeric outputs (V5 rating snapshots, rating components, predictions) are identical before vs after the change, with release identity/provenance fields (code commit, release IDs, created-at/provenance hashes) explicitly excluded and listed. A fixed-identity builder test additionally requires byte-identical existing (`core_v1`) projection payloads.
  - Verification negatives: broken mirror, cumulative mismatch, perturbed adjusted value, wrong rank, missing/extra window or team each fail.
- Postgres suites (Section 3 tests) on a disposable cluster.
- `make contracts-check`, `make quality-check`, Ruff, `git diff --check`, `uv run mkdocs build --strict`.
- Web (`web/`): `npm run lint`, `npm run typecheck`, `npm run test:publication` (add `charts.test.ts`), `npm run test:ui` (charts render, week switch, "Through Week N" label, filter dims, keyboard tooltip, table toggle, unavailable-teams list, unsupported-release placeholder, no broken logos, week coercion when switching tabs from a net-success Week 0/1 URL, full-slate PNG export width with logos present in the captured image), `npm run build`. `charts.test.ts` covers the week-coercion helper.
- Preview rehearsal: spot-check several teams' cumulative SR/EPA against Ratings/matchup values for the same week.

## Risks and gates
- Prepare requires a clean tree and no commit between prepare and release; charts ship with whichever weekly release first follows a committed, validated implementation.
- Once merged, staging requires `charts_v1`, so 0026 must be applied in Preview and Production before the next staged release. If the implementation merges before a weekly update but 0026 cannot be applied in time, that week's release is staged from the pre-merge commit instead, still under the full runbook: clean checkout, independent Preview rehearsal, and owner-approved Production activation.
- Logo density in scatter centers: mitigated by filter, search and table view, not collision layout.

## Amendments (implementation, 2026-10-16)

Safe deviations from the approved text, each narrower than or equal to the contract's intent:

1. **Chart builders live in `season/projection_charts.py`, not `projection_football.py`.** `FOOTBALL_KEYS`, `ROW_KEYS`, `INTEGER_COLUMNS` and `_columns` of the existing builder are untouched, which makes the byte-identical `core_v1` payload requirement trivially checkable. `projection.build_projections` runs the serving, football and chart builders; `release.PROJECTION_KEYS` still gains the three keys.
2. **Chart queries live in `web/src/lib/chart-queries.ts`, not `queries.ts`.** An existing publication test requires `queries.ts` to never mention adjusted-value columns (the matchup raw-only contract). Same release-scoped, cache-wrapped queries and signatures.
3. **`_check_chart_scope` is a separate function** called after `_check_projection_scope` at staging, so tests can stage a retained `core_v1` release the way pre-charts code did.
4. **`team_adjusted_epa.games`** is the number of games that contributed EPA observations for that role (`epa_n > 0`), which equals the team's game count except for the one-role edge cases.
5. **Week coercion tie rule:** nearest available week, the later one on a tie; the latest when no week is requested or the value is invalid.
6. **Test-mode fixtures** are selected with `?fixture=unsupported|error|slate` (only when `CFB_UI_TEST_MODE=1`) to exercise the arrival notice, the unavailable card and a full 69-game Week 0 slate export (2210 px wide).
7. **Postgres chart-query tests run the SQL drizzle generates** (a short `node` call from `web/`) and skip when `web/node_modules` is absent.
8. **Display metadata** (`TEAM_DISPLAY`) was refreshed with the new `--metadata-only` mode of `build-team-logos.mjs` (one read-only CFBD `/teams/fbs` call, no image downloads; it aborts if the teams or ids differ from `public/logos/v2/manifest.json`). CFBD names the alternate color `alternateColor`.
9. **Verification check count** in the runbook and `.agent/CONTEXT.md` is now 23 (15 projection + 8 prepare).
10. **Closeout review (2026-10-16).** A five-lens review of the complete diff found no blocking issue. Fixed: an adjusted-window query error now shows the unavailable card; `team_chart_reconciliation` additionally requires every `team_game_stats` row to agree with the release's own `games` (teams, week, site) and `game_results` (points); the live chart tables are revoked from every role except the owner; `numpy>=2.0` is declared (rank/`rtol` API); `--metadata-only` refuses fewer than 100 teams or an empty manifest and writes atomically; added tests (rank ties, JSON round trip, one-role coverage in both directions, concrete disconnected-schedule outcomes, tie week coercion, adjusted-error page state). Deferred, non-blocking: refactor of duplicated tooltip/mark code and `ChartExportButton`/`ShareButton` shared helpers, caching chart queries by release id (`revalidate` is inert with `searchParams`, the repo-wide pattern), derive Week lists without fetching all rows on the adjusted tab, a one-way cumulative check from stats to game rows, an optional foreign key from chart rows to release games.

11. **Week 7 revision manifest amended to pin the score-reconciliation exceptions (2026-10-16, owner-authorized).** The committed `revision_manifest_w7_v1.json` predated the prepare safeguard of `2807e087` and did not pin `conf/season/2026/score_reconciliation_exceptions.json`, so `make season-prepare WEEK=7 RECONSTRUCT=1` failed with 42 unlisted `score reconciliation differs` errors (the Weeks 0-6 chart rehearsal, task 8). The only change is one added top-level key, `score_reconciliation_exceptions`, with `uri` `conf/season/2026/score_reconciliation_exceptions.json` and `sha256` `939ec41c62731ce9fe846c100100e61ec8f2a6bf94823e105f32140fd0bea8cb`. The exceptions file, every pinned input, both cutoff maps and every other key are byte-for-byte unchanged (verified against `HEAD`). Validation: `validate_revision` passes, and `load_inputs` through Week 6 against the pinned R2 inputs succeeds, which requires every mismatching team-game to be declared and every declared entry to be used: the 42 mismatches equal the 42 declared entries exactly, none missing or unused. The amended manifest has a new SHA-256, so releases prepared from it carry a new revision identity.

## Confirmed results (local, tasks 1-7)

- Full Python suite on the implementation: exit code 0, 3300 passed, 33 skipped (skip count unchanged from the earlier run; no chart test is skipped). After the closeout fixes, the affected suites (charts, reconciliation, verification, release, prepare, projection, documentation authority, contracts, and the Postgres release suite including the node-driven chart-query tests, 9 chart tests passed with 0 skipped) passed: 405 passed. `ruff check .`, `make contracts-check`, `make quality-check`, `git diff --check`, `mkdocs build --strict` clean.
- Web: `npm run lint` (0 errors, 1 existing warning), `typecheck`, `test:publication` (183 passed), `test:ui` (65 passed), `build` clean.
- **Isolation golden** (`tests/isolation_golden.json`) was generated on the unmodified baseline before any implementation edit and independently re-derived on a pristine checkout of `a08bf6f3` during closeout: identical (16 digests). It was never regenerated to match the implementation.
- **Pinned `teams` input (verified read-only on 2026-10-16):** `lake/silver/dataset=teams/version=590e986596436aa001ff77b7/data.parquet` matches its pinned SHA-256, has `team`, `classification` and `conference`, 138 FBS rows with no missing conference, and the same 138 names as the pinned schedule. No re-pin is needed. See the implementation log for the Preview preflight (database identity, migration state 0025 with 0026 pending, active release `d0272a48...` as `core_v1`).

## Status

Tasks 1–7 are committed. Migration 0026 is applied to Preview, and the chart release was activated from clean commit `749ee12c`. All 23 checks passed; parity against all 18 existing projection tables and the real-data chart coverage/interaction checks passed. The initial saved bar and adjusted-scatter PNGs exposed keyboard-focus outlines. The follow-up implementation omits focus-ring elements from noninteractive exports while retaining live keyboard focus; focused export regressions pass and a saved 138-team real-data efficiency PNG was visually verified without rings. All 67 browser tests, publication tests, typecheck and build pass. Chart/week controls and team filters/actions are now grouped responsively. The owner committed and fast-forwarded the presentation fixes into `dev`, then pushed `b2335ae5`; no model, projection payload or database state changed in the follow-up. Production migration, deployment and activation remain separately owner-gated. Live release identity is in [current status](../../status.md); evidence is in `session_logs/2026-10-16/03-preview-chart-rehearsal.md` and `session_logs/2026-10-16/04-chart-navigation-and-export-polish.md`.

### Amendment 12: chart organization and export polish

The owner requested design/organization followed by implementation after reporting a missing Charts button. The missing navigation entry was caused by the primary `dev` checkout still being at the pre-chart baseline; the chart worktree already has Charts beside Ratings. This localized presentation follow-up preserves that top-level navigation, groups chart tabs with a compact optional WeekNav, labels the efficiency side selector, separates team filters from display/export actions and improves narrow-screen controls. WeekNav's default appearance and URL handling remain unchanged. Static export rings are omitted rather than depending on capture preserving CSS opacity. No dependencies, schema, query, model, cutoff or release semantics changed. The correct chart-enabled local development server is on port 3200 from the worktree; the older primary checkout was not mutated or merged.

### Amendment 13: losing-team logo at the zero baseline

The owner requested moving the losing team's logo closer to the x-axis. Net-success charts now anchor that logo near zero on the side opposite the bar, rather than mirroring the bar's full magnitude. A follow-up request adds six SVG units of clear space between the zero line and the closest logo edge (`logo / 2 + 6` center offset). Winner logos remain at the bar tip. The shared renderer applies the same rule to vertical charts, horizontal mobile rows and exports, including negative and zero bars. No values, sorting, scale, data or release state change. Live Week 6 positive/negative examples were checked in both orientations; the Illinois/Michigan State example confirms six units of edge clearance. Evidence: `session_logs/2026-10-16/05-net-success-loser-logo-baseline.md`.
