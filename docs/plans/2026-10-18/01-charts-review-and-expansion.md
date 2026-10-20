# Charts review and expansion: 3 → 6 charts (Revision 3)

**Status:** Complete as released: Charts ships hidden behind `CFB_CHARTS_ENABLED` (live `/charts` returns 404). Deep visual verification is deferred until Charts is slated to be un-hidden; that, and any Production un-hide, is a separate owner-gated decision. Migrations 0027/0028 and the `charts_v2` projections are applied and serving. Owner controls commits, merges, migrations, Preview rehearsal and Production.

- **Created:** 2026-10-18
- **Approval source:** Owner's explicit “PLEASE IMPLEMENT THIS PLAN” request for the completion plan in the recovery chat on 2026-10-18, naming this saved Revision 3 contract and existing worktree.
- **Implementation log:** `session_logs/2026-10-18/03-charts-expansion-recovery.md`
- **Planning context:** `session_logs/2026-10-18/02-charts-expansion-reconstructed-planning.md` (reconstructed after interruption; not an original planning-session receipt).
- **Commit policy:** Owner controls staging, commits, integration and pushes. Preserve the pre-existing staged static-file deletion; remaining changes may be committed together after local review and validation. No prepare/release from this dirty tree.

## Context

Charts (`/charts`) has three charts: **Did We Really Get Beat That Bad?** (net success bars), **Efficiency vs Explosiveness** (scatter) and **Opponent-adjusted PPA/play** (scatter). The owner asked for a critique, redesigns and corollary charts. Owner decisions: serve explosiveness through the release; add **Schedule adjustment**, **Team trajectory** and **Team game log** (six charts total); keep team colors on the net-success bars.

Routing: this touches schema/release projections plus multiple web subsystems, so it uses the repo's Sol → Terra flow. Terra implements in a git worktree on `connorkitchings/charts-expansion` off `dev`. The owner controls commits, merges, migrations, Preview rehearsal and Production.

## Critique of the existing charts (code plus live Week 6 screenshots)

- **Efficiency (critical).** The default metrics come from `web/src/lib/explosiveness-data.generated.ts`, a static research export from the Week 7 pinned revision covering only Through Weeks 2–6. `efficiencyPoints` ignores release rows for these metrics. A newer release would show stale research values for Weeks 2–6 and an empty chart for Week 7+. The export bypassed Revision 5's deferred `charts_v2` gate, and its footnote cites "Research comparison dataset".
- **Structure.** `ChartsView.tsx` (405 lines) holds every chart's labels, formatters, 8 caption variants and footnotes in nested ternaries; `ScatterChart` duplicates the captions as defaults. The highlight is client-only state that isn't in the URL and doesn't survive switching charts. The PPA efficiency branch can't be reached from the UI.
- **Net success.** The concept is sound. But the −55° labels at 59 games are hard to scan, nothing states how many winners were outplayed, and there's no tie to the scoreboard margin. Team colors, the amendment 13 logo placement and the no-team-finder rule stay.
- **Adjusted PPA.** The strongest chart. Its 3-decimal ticks add noise, the diagonals have no value labels, and the stored decomposition never appears (not even in the tooltip).

## Phases and merge/deploy rules

| Phase | Content | May merge to `dev` | May deploy |
|---|---|---|---|
| **1. Serving** | Frozen capabilities, `team_game_yardage`, `charts_v2`, static file deleted | Only when 0027 is already applied in Preview, or no release will be staged before it is (once merged, staging requires `charts_v2`) | Local review; Preview only under owner authorization. Retained `charts_v1` releases show release-backed PPA/play only. Charts Production approval is withheld. |
| **2. Charts** | Restructure, polish, three new charts | After Phase 1 is merged (it builds on the Phase 1 capability types) | Local/owner-authorized Preview only; release-backed on both `charts_v1` and `charts_v2`. Production approval is withheld. |

Production migration 0027, Production chart promotion and activation each need a separate owner decision. No intermediate state ever shows static research values: Phase 1 deletes the file in the same change that makes efficiency release-backed.

**Completion and owner gates.**
- **In Progress — code complete** when Phases 1–2 pass every local check in Verification (Python, Postgres, web unit/e2e/build, fixture screenshots, parity gate).
- **Implemented** only after the owner authorizes and completes the Preview rehearsal: 0027 applied to Preview, a `charts_v2` release prepared, staged and activated under the weekly runbook, and the real-data acceptance passing (readback, explosiveness Through Week 7, retained-release rollback compatibility, real-data screenshots).

Until that rehearsal happens the contract stays In Progress, whatever the state of the code. Production promotion stays outside this contract's acceptance.

## Phase 1 — serving explosiveness (`charts_v2`)

**1a. Builder.** New `src/cks_picks_cfb/charts/team_game_yardage.py`. It produces one row per `(season, game_id, team)` with exactly the key set of `team_game_stats` (same eligible games, `scrimmage_play_mask`, FBS-vs-FBS regular season, weeks `< active_week`). For `off_`/`def_`:
- `yards_n`: eligible plays with finite `yards_gained`
- `explosive_n`: plays among those with `yards_gained ≥ 20`
- `success_yards_n`, `success_yards_sum`: plays with `success == 1` and finite yardage

These match `scripts/research/compare_chart_explosiveness.py`. Zero exposure stores 0 counts; the web layer turns a zero denominator into null, never zero. `team_game_stats` and every `charts_v1` column stay byte-identical.

**1b. Schema.** `contracts/migrations/0027_team_game_yardage.sql`: live plus `season_release_team_game_yardage` (`release_id` in the PK), immutability trigger, and REVOKE/GRANT following 0026. Update `contracts/schema.{sql,ts}` and `web/src/lib/schema.ts`; `make contracts-check`.

**1c. Python projection sets.** In `season/projection_common.py`, `PROJECTION_SETS` gains `charts_v2 = (*charts_v1, "team_game_yardage")`; `charts_v1` stays frozen and `STAGING_PROJECTION_SET = "charts_v2"`. `recognized_projection_set` already exact-matches recorded keys, so retained `core_v1`/`charts_v1` releases read back, activate and roll back by their recorded set. Staging refuses `charts_v1`. Builder wiring lives in `projection_charts.py`, with `release.PROJECTION_KEYS` and the non-empty rule (yardage required when `active_week > 0`) in `release.py`.

**1d. Verification, split between prepare and staging.** The projection verifier (`derive_checks`, `season/verification.py:1024`) sees only serving rows and manifest context, with no play-level yardage. Adjusted PPA can be recomputed from `team_game_stats`; explosive counts cannot. So:
- **Prepare (play-level recomputation).** Add a new prepare check, `chart_yardage_recomputed`, to the hash-bound prepare checks (`derive_prepare_checks`, around `verification.py:1318`). It recomputes `team_game_yardage` from the checksum-verified pinned byplay frame that prepare already loads (`checksums_at_read` covers it), then compares every key and count/sum with the candidate projection (counts exact; `success_yards_sum` within 1e-9). Its evidence entry records the pinned byplay URI and SHA-256 from the revision manifest, the candidate's `team_game_yardage` projection SHA-256 and its row count. Any difference fails prepare.
- **Staging (structural checks plus evidence binding, no new R2 reads).** The yardage branch of `team_chart_reconciliation` checks that the key set equals `team_game_stats`, offense/defense values mirror field for field, and `explosive_n ≤ yards_n ≤ plays` and `success_yards_n ≤ success_n` hold. Staging then requires `chart_yardage_recomputed` to be present and passing, with its recorded projection SHA-256 equal to the candidate's `projection_checks["team_game_yardage"].sha256` and its byplay SHA-256 equal to the revision manifest's pinned byplay. `success_yards_sum` has no sign constraint, following the research definition (a finite-yardage sum over successful plays).
- **Version-aware required checks.** Replace the single `REQUIRED_CHECKS` with required check sets keyed by projection set: `core_v1` and `charts_v1` keep today's sets exactly, and `charts_v2` adds `chart_yardage_recomputed`. Readback, activation readback and rollback of retained releases validate against their recorded set's checks; new candidates must satisfy the `charts_v2` checks.

**1e. Web capabilities (frozen per version).**
- `season-release-query.ts`: keep `CORE_RELEASE_TABLES`. Replace the single `CHART_RELEASE_TABLES` with frozen `CHART_TABLE_SETS = { charts_v1: ["teamSeasonRoster","teamGameStats","teamAdjustedEpa"], charts_v2: [...charts_v1, "teamGameYardage"] } as const`. Derive `CHART_SET_KEYS[set]` (the sorted recorded `projection_checks` keys for core + that set) and `CHART_SET_PROJECTIONS[set]` (relation names). `CHARTS_V1_KEYS` stays equal to today's value.
- `seasonReleaseDb(db, releaseId, { chartSet })` adds CTEs for exactly that set's tables, so a `charts_v1` release never references `season_release_team_game_yardage`, before or after 0027 exists.
- `season-release-context.ts`: the resolver query returns recorded keys plus one relation-existence boolean per set. `SeasonReleaseContext` replaces `chartsAvailable: boolean` with `chartSet: "charts_v1" | "charts_v2" | null`. A set is chosen only when the recorded keys exactly equal that set's keys and all its relations exist; anything else gives `null`, and charts are unavailable. Exported helpers: `chartsAvailable = chartSet !== null` and `explosivenessAvailable = chartSet === "charts_v2"`.
- `season-release.ts`: the `chartsDbForRelease` cache key becomes `(releaseId, chartSet, season, environment)`. `getChartsDb` returns `{ db, chartSet }` from the request's single memoized context, so release id and capability are pinned together for the whole request.
- `chart-queries.ts`: new `getTeamGameYardage(season)`, executed only when `chartSet === "charts_v2"`, otherwise `null`. `page.tsx` joins yardage onto `TeamGameRow` by `(gameId, team)` as optional fields.
- `charts.ts`: `efficiencyPoints` computes 20+ rate (`Σexplosive_n/Σyards_n`) and yards/success (`Σsuccess_yards_sum/Σsuccess_yards_n`) from release window sums, with pooled averages, exactly like PPA. The metric toggle (20+ rate default, Yards/Success) renders only when explosiveness is available; otherwise the chart is Success Rate vs PPA/play with no toggle. Delete `explosiveness-data.generated.ts` and its import; the footnote returns to "Reconstructed from this release's data".

**1f. Parity gate (before deleting the static file).** Run the new builder on the same Week 7 pinned revision (manifest SHA-256 `208a4a5b…040f6`, per the research report) for Through Weeks 2–6 and compare with the static file at each field's serialized precision (measured from the file: `er` 5 decimals, `ys` 3, `sr` 5, `ppa` 4, rounded to the same shortest repr). `n` must match exactly, as must `erRank`/`ysRank` (competition ranks via `scatterRanks` semantics on the full population). `EXPLOSIVENESS_AVERAGES` `er`/`ys`/`sr` per window and side must match at the same precisions. Any mismatch blocks Phase 1 and gets reported. The evidence goes in the implementation log.

**1g. Ops docs.** Runbook note: apply 0027 to Preview before the first `charts_v2` staging, and to Production before any Production chart promotion. Retained releases stay readable without it.

## Phase 2 — restructure, polish and new charts (web only)

**2a. Restructure.** `web/src/lib/chart-config.ts` becomes a registry per kind/side/metric (title, tab label, group, axis labels, formatters, captions, footnote). A shared `ChartFrame.tsx` holds the header, controls, export, not-plotted list and footnote, and each chart gets its own view component. `ScatterChart` drops its default captions. Existing URLs and test ids are preserved.

**2b. Navigation.** A grouped picker: **Games** (Net success) · **Teams** (Efficiency, Adjusted PPA, Schedule adjustment, Trajectory) · **One team** (Game log), scrollable on mobile. A `team=` URL param seeds and persists the highlight on the scatters, Schedule adjustment, Trajectory and Game log (`router.replace` with no full navigation; an invalid or unknown team is ignored). `ChartKind` gains `schedule | trajectory | game-log`. Throughout, `as_of_week = N + 1` means "Through Week N".

**2c. Polish.**
- *Net success:* a summary line ("N of M winners had the lower success rate"); a subtle shaded band below zero labeled "Winner outplayed"; a **Sort: Success gap | Final margin** toggle (margin ties fall back to `gameId`); label size and rotation tuned for 59+ games. Colors, logo placement and the no-finder rule are unchanged.
- *Adjusted:* 2-decimal ticks; each diagonal labeled at the plot edge (`+0.20 net`). The tooltip adds raw, venue correction, opponent adjustment and adjusted values, plus `adjustedRank` of `cohortSize` per role.

**2d. Schedule adjustment** (`chart=schedule&side=offense|defense&week=N`, Through Week N, from `team_adjusted_epa`).
- **Isolate the opponent effect.** A dumbbell row per team runs from **venue-neutral** PPA (`neutral = raw − venueCorrection`) to **adjusted** PPA, because `raw − adjusted = venueCorrection + opponentAdjustment` (`adjusted_epa.py:169`). Venue correction and raw appear only in the tooltip and table.
- **Sign in better-is-positive units.** `scheduleEffect` is defined as offense `adjusted − neutral` (= `−opponentAdjustment`) and defense `neutral − adjusted` (= `+opponentAdjustment`). Positive means "raw understated: tougher opponents than average"; negative means "raw inflated: weaker opponents". Those are the only two labels used; never "helped/hurt".
- **Ordering.** Sorted by `scheduleEffect` descending, then team name.
- **Subset.** All FBS shows the first 15 and last 15 by that order, cut strictly at 15 (ties at the boundary resolve by name). A group of 30 or fewer teams, or one where the two sets would overlap, shows every team once. "Show all" lists the whole group.
- **Highlight.** A highlighted team outside the shown set appears as a separate row below a divider, labeled with its position (e.g. "41 of 138").
- **Defense** plots allowed values with the axis inverted (better is right) and says so.

**2e. Team trajectory** (`chart=trajectory&metric=net|offense|defense`).
- **Axes and population.** x = Through Week N for every stored window (`as_of_week − 1`, from 2 to latest); y = adjusted PPA/play; net = offense − defense allowed. The defense axis is inverted.
- **Reference line.** The weekly play-weighted national average (the same formula as `adjustedPoints`) is drawn as a dashed line per window for every metric. There is no zero line, because adjusted means aren't zero.
- **Missing data.** A team with no row in a window (for net, missing either role) gets a gap there with no interpolation. A one-window segment is drawn as a dot.
- **Display.** All teams are faint gray. A conference filter draws its teams in `chartColor` with end-of-line logos. The highlighted team is bold and labeled.
- **Data.** New `getTeamAdjustedEpaAll(season)` (about 2k rows by Week 8) and the pure `trajectorySeries` in `charts.ts`. There is no week selector.

**2f. Team game log** (`chart=game-log&team=…&metric=success|ppa|explosive_rate`, with `explosive_rate` only when explosiveness is available).
- **Scope.** The whole release: every `team_game_stats` row for the team, meaning completed FBS-vs-FBS regular-season games in weeks before the active week. A caption says "FBS opponents only".
- **Header.** Season-to-date values through the release's latest charted week, plus national competition ranks over roster teams for the same window, computed with the same functions as Efficiency Through Week (latest). There is no week cutoff selector.
- **Layout.** Offense and Defense-allowed panels (defense inverted). One bar per game, ordered by week then `gameId`. Under each bar: the opponent logo and `W 31-10`/`L 10-31`. A dashed per-week FBS average is pooled over all FBS team-games of that week.
- **Missing values.** When a metric has zero denominator, the bar is omitted and the game labeled "n/a"; the game itself stays.
- **Default team.** The top adjusted-net team in the latest window, with ties broken by name. The picker is `TeamHighlightCombobox`. The pure transform is `teamGameLog` in `charts.ts`.

All new charts reuse `TeamMark`, `useChartSelection`, `ChartTable`, `ChartExportButton`, `niceTicks`/`domainFor` and the conference filter, with accessible labels, a table view and PNG export. **Design guidance.** Before writing chart code, Terra loads whichever data-visualization skill its harness provides (in Claude Code, `dataviz`; otherwise any equivalent, or `web-design-guidelines` for UI review). If none is available, the explicit chart requirements in this contract are sufficient and authoritative: the axes, inversions, reference lines, missing-value rules, ordering, accessibility, table and export behavior above. A skill never overrides them.

## Acceptance criteria (both phases)

On identical pinned inputs and fixed release identity:
- V5 rating snapshots, rating components, predictions and prediction grades are numerically identical (the isolation golden `tests/isolation_golden.json` is unchanged and never regenerated).
- The 21 existing `charts_v1` projection table payloads are byte-identical.
- Retained releases' recorded `projection_checks` hashes are unchanged, and readback, activation readback and owner rollback pass for `core_v1` and `charts_v1`.

## Verification

- **Python:** new `tests/test_team_game_yardage.py` with *independent* formula tests. Expected counts are hand-computed from small play fixtures, never by the builder. The fixtures cover a 20-yard boundary (19/20/21), missing or non-finite yardage, missing success, zero successes, zero explosive plays, unequal exposures, mirrors, excluded garbage/special-teams plays and later-week exclusion. Prepare negatives: **both mirrored rows carry the same incorrect `explosive_n` (and separately `success_yards_n`) while satisfying every bound**. The staging-side structural checks pass on it (asserted), but `chart_yardage_recomputed` must reject it. Staging negatives: a broken mirror, a missing or extra key, `explosive_n > yards_n`, `success_yards_n > success_n`, a missing or failed prepare entry, a prepare entry whose projection SHA-256 or byplay SHA-256 doesn't match the candidate or manifest, and an assertion that staging performs no storage reads (storage client mocked to fail on any call). A negative `success_yards_sum` (a loss on a successful play) is accepted. Release tests: staging refuses `charts_v1`; `charts_v2` stage/activate/readback works; retained `charts_v1` readback, activation and rollback work. Plus the isolation tests above. Run `uv run pytest` for the chart, reconciliation, projection, release, verification and isolation suites; the Postgres release suite on a disposable cluster (including `charts_v1` rollback over `charts_v2` and back); `make contracts-check`, `make quality-check`, `uv run ruff check .`, `uv run mkdocs build --strict`, `git diff --check`.
- **Web unit** (`npm run test:publication`), covering the capability matrix:
  - a retained `charts_v1` release without 0027 gives charts on and explosiveness off, with no yardage CTE;
  - a retained `charts_v1` release after 0027 behaves the same (the recorded set governs);
  - `charts_v2` turns both on, with the yardage CTE bound to the same release id;
  - `charts_v2` recorded but the yardage relation missing gives `chartSet = null`;
  - unknown or partial recorded keys give `null`;
  - in request consistency, a context resolved once returns the same release id and `chartSet` even when a different release is activated between two queries in one request.

  It also covers the transforms: yardage `efficiencyPoints`, `trajectorySeries` gaps and averages, `teamGameLog` ordering/n-a/header ranks, `scheduleEffect` signs per role, top/bottom-15 boundary ties and overlap, highlighted-team extra row, net-success margin sort, diagonal labels, and `team` param coercion.
- **Web e2e and build:** `npm run test:ui` (each new chart renders, table toggle, keyboard tooltip, export width, `team` persists across charts, toggle hidden without explosiveness), `npm run lint`, `npm run typecheck`, `npm run build`.
- **Screenshots, as two separate runs:**
  1. A fixture run on its own port with `CFB_UI_TEST_MODE=1`, covering deterministic states (v1/v2 capability fixtures, unsupported, error, full slate).
  2. A real-data run without test mode against Preview's database: first with the active `charts_v1` release (PPA only, no toggle), then after the owner-gated `charts_v2` Preview activation (explosiveness Through Week 7).

  Both runs cover desktop and 390px widths in light and dark themes, plus exported PNGs.

## Critical files

- Pipeline: `src/cks_picks_cfb/charts/team_game_yardage.py` (new), `src/cks_picks_cfb/season/{projection_common,projection_charts,release,verification}.py`, `contracts/migrations/0027_team_game_yardage.sql`, `contracts/schema.{sql,ts}`.
- Web: `web/src/lib/{season-release-query,season-release-context,season-release,chart-queries,charts,chart-config,schema}.ts`, `web/src/app/charts/page.tsx`, `web/src/components/charts/*` (new `ChartFrame`, `ScheduleAdjustmentChart`, `TrajectoryChart`, `GameLogChart`), `web/src/test/fixtures/charts.ts`, `web/e2e/charts.spec.ts`. Delete `web/src/lib/explosiveness-data.generated.ts`.
- Docs: `docs/modeling/team_charts_methodology.md`, `docs/modeling/measurement_catalog.md`, `docs/ops/weekly_runbook.md`, `docs/plans/index.md`, and the Revision 5 contract (record the owner's metric selection and point to this contract for the deferred phase).

## Recovery amendments — 2026-10-18

The owner explicitly authorized the completion plan in the recovery chat. Preserve all interrupted work in `.claude/worktrees/connorkitchings-charts-expansion` on `connorkitchings/charts-expansion`, based on `23621eb3`. The primary checkout's modeling edits and Week 8 revision are outside scope.

1. **Highlight URL updates:** use `window.history.replaceState` with Next's search-parameter subscription instead of `router.replace`. This preserves the required shareable selection without server round-trips for every selection. Verify rapid changes, clearing, chart navigation, reload and browser history. URL shape and data-loading semantics are unchanged.
2. **Accessible tables:** the earlier UI commit removed the table toggle. The owner explicitly selected “Keep table toggle” in this review chat; all six chart views retain it.
3. **Revision evidence binding:** `stage_release` and `validate_candidate` receive required `revision_raw` bytes. The operational CLI and runner are included in scope so every caller supplies the sealed, checksum-verified revision. No new play-data reads occur during staging; existing candidate artifact loading and checksum checks remain mandatory.
4. **CI integration proof:** the database CI job installs locked web dependencies with Node 22. Web/database integration tests fail for missing dependencies in CI, while local runs may skip with an explicit reason.
5. **Presentation completion:** deterministic trajectory endpoint spacing and stronger Schedule adjustment fixtures/browser checks finish the approved charts without changing measurements. Remove the temporary machine-specific screenshot test; retain repeatable fixture screenshots and PNGs as ignored artifacts.
6. **Completion boundary:** owner-controlled Preview rehearsal remains pending. Retained-release rollback proof runs on disposable PostgreSQL, never by attempting unsupported Preview rollback. Local validation does not authorize a migration, release or Production action.


### Final local review corrections

Three cross-review findings were corrected within the approved interfaces and acceptance criteria:

- Freeze `core_v1`'s historical projection-check set without `team_chart_reconciliation`; derive checks using the recognized set. A retained-report regression failed before the fix and now validates `core_v1`, `charts_v1` and `charts_v2` reports without rewriting their hashes.
- Reset Efficiency and Game Log local metric state when the release's explosiveness capability changes. Client-navigation regressions cover moving from retained `charts_v1` to `charts_v2` and back.
- Reset the net-success table's initial sort when the owner changes Success gap / Final margin; verify both the selected sort semantics and displayed score order.

Game-log table order now uses the chronological transform order rather than combining week and real provider IDs arithmetically. Trajectory endpoint logos use deterministic spacing and leader lines; chart values are unchanged. The mobile geometry assertion waits for actual layout rather than reading before styles have settled. These are mechanical corrections, not changes to the selected model or chart formulas.


### Production separation — owner direction on 2026-10-18

The owner intends to promote Week 7 closure and Week 8 start independently, and explicitly withholds Charts Production approval pending substantial manual review. Local completion or Preview acceptance of this contract does not authorize Charts in Production. Do not deploy the Charts route/navigation, apply its serving migrations to Production, or activate a Charts candidate there under this contract.

Read-only branch inspection at recovery closeout found that `main` has no Charts route or navigation item, while `dev` already includes the original Charts implementation and now also the Week 8 operational commits. A full `dev` → `main` merge would violate the owner's current feature boundary. The future weekly Production task must review a charts-free source/release path and its dependencies separately; this session does not cherry-pick, rebase, merge, prepare or activate that path. The currently recorded Week 8 Preview candidate includes `charts_v1`; its rehearsal is not blanket authorization for Charts promotion.

The expansion worktree remains based on `23621eb3`. During the pause the primary `dev` advanced through `1e821052`, including the Week 8 revision and scoring/measurement fixes. Those commits were inspected but not integrated here. Any later owner integration must preserve the newer operational state and revalidate the combined code before a new Charts prepare. The old Week 7 parity receipt remains evidence for its exact pinned revision, not the newer Week 8 release.

### PNG visibility correction

Visual inspection identified a light-mode PNG defect despite successful image decoding: `html-to-image` deep-clones SVG descendants without their computed visibility, allowing the hidden dark logo to paint over the light logo. The temporary export card now materializes each SVG image's computed display before capture. Live logo selection and team-color policy remain unchanged. Saved-PNG pixel regressions pass for both themes; removing the fix makes the light-mode regression fail with zero red logo pixels. An independent reviewer confirmed the correction stays within the temporary export card and existing lifecycle.


### Local completion receipt

Local code, documentation and fixture QA are complete. Final checks: 104 browser tests passed (plus the separate opt-in visual capture); 231 publication tests passed with one existing skip; lint/typecheck and fixture production build passed. Release recovery passed 328 scoped Python tests, then 160 affected tests and 125 disposable PostgreSQL tests after the retained-report fix. Contracts, 32-check quality registry, Ruff and strict MkDocs passed. Existing isolation golden and existing chart payload bytes remain unchanged on fixed inputs/identity.

Final fixture review covers 32 screenshots and 12 PNG exports, including all six charts at desktop/390px in light/dark themes and dense trajectory endpoints. Detailed evidence and the charts-free weekly Production warning are in the implementation log. This receipt is not owner manual acceptance. Status remains **In Progress** until separate Charts Preview rehearsal and acceptance; Production remains withheld.
