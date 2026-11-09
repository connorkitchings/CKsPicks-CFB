# Net success rate includes overtime

- **Status:** Approved
- **Created:** 2026-11-09
- **Planner:** Sol
- **Approval source:** Owner decision in the session of 2026-11-09: the Net success rate chart should not drop overtime (original scope also kept garbage time; narrowed, see Amendments); no other chart, rating or forecast changes. Owner chose "build and verify, then release to Preview".
- **Implementation log:** `session_logs/2026-11-09/06-nsr-keep-garbage-time-impl.md`
- **Commit policy:** Commit with implementation (owner pre-authorised commit, push and PR to `dev`; owner merges; never `main`)

## Goal and acceptance

The Net success rate chart (`/stats?chart=net-success`) compares each game's winner and loser using offensive success rate over scrimmage plays, including overtime (garbage time stays dropped). Fleming's Week 10 chart disagrees with ours mainly on blowouts (UGA 42-7: his about +0.465, ours +0.160); the investigation showed this is not explained by garbage time (Amendment 1).

Acceptance:
- The chart's per-game bars use success counts that include overtime scrimmage plays. All other exclusions stay (garbage time, special teams, penalties, two-point tries, dead plays, kicking plays, non-FBS games).
- No other consumer changes: `off_success_n`/`off_success_sum` and every other existing column keep their values byte for byte, so Efficiency vs explosiveness, Game log, Possession, ratings and forecasts do not move.
- The chart's copy, methodology doc and "About this chart" text say plainly that overtime is included for this chart only and garbage time is still dropped.
- A recompute of Week 10 from the raw plays reproduces the chart's values for the two overtime games and shows every other game unchanged, recorded in the session log next to Fleming's approximate values.

Out of scope: changing `scrimmage_play_mask` or `eligible_play`, any rating or forecast input, the weekly release itself (phase 2, after PR #26 for the CFBD retrospective lines is merged).

## Baseline and constraints

- `src/cks_picks_cfb/charts/team_game_stats.py` builds the `team_game_stats` projection from `scrimmage_play_mask` plays (regulation only; garbage time excluded). The web reads it through `season_release_team_game_stats` (`web/src/lib/schema.ts`, `chart-queries.ts`, `charts.ts` `netSuccessBars`).
- The projection column list is spelled in `src/cks_picks_cfb/season/projection_charts.py` and mirrored in the web row guard and DB schema/migrations; keep all in step and keep the contracts check green.
- Branch is off `origin/dev` (581645a5) and does not contain the CFBD retrospective revision manifest (PR #26). A release built from this branch alone would drop those three grades, so the Preview release waits for #26 to merge and this branch to be rebased on it.

## Ordered changes

1. Builder: add `off_success_ot_n`, `off_success_ot_sum` (and the defense-side equivalents only if the existing column symmetry requires them) computed over scrimmage plays with overtime kept. Use a mask built from the same rules as `scrimmage_play_mask` with only the regulation-only period rule relaxed; do not change `scrimmage_play_mask` itself.
2. Projection spec, DB schema and migration, web schema, row guard and loader for the new columns; existing columns unchanged.
3. Chart: `netSuccessBars` uses the new columns; copy and methodology updated.
4. Tests: unit tests of the builder (overtime plays counted in the new columns, not in the old; garbage-time plays counted in neither; a game with no overtime gives equal columns), of `netSuccessBars`, the row guard, and the contracts check; update e2e fixtures and assertions for the chart.
5. Verification: read-only recompute for Week 10 (see acceptance) and a table comparing old chart values, new chart values and Fleming's approximate values.
6. Docs: `docs/modeling/team_charts_methodology.md`, `docs/modeling/measurement_catalog.md` if it lists the column, and a decision-log entry.

## Validation

```bash
make check
make web-e2e
git diff --check
```

Phase 2 (after #26 merges): rebase, prepare and release to Preview per the weekly runbook; parity must show the old columns identical and only the new ones added; the three retrospective grades must still be present; verify the chart on a local Preview server. Production is not touched.

## Handoff/amendments

Phase 1 by one worker-large subagent; the orchestrator validates. Amendments: see below.

### Amendment 1 (2026-11-09): scope narrowed to overtime only

- **Previous:** keep garbage time and overtime plays in the Net success rate counts (columns `off_success_all_n`, `off_success_all_sum`).
- **Now:** include overtime plays only; garbage time stays dropped; columns are `off_success_ot_n` and `off_success_ot_sum`; the play-filter keyword is `keep_overtime`.
- **Reason:** the investigation showed our data is sound and that garbage-time exclusion tracks Fleming's ordering better (rank agreement 0.966 dropped against 0.952 kept), so it does not explain the gap. Our chart stays winner offensive success rate minus the loser's and differs from his published chart, whose method we could not reproduce (largest magnitude difference on UGA 42-7).
- **Impact:** only games with overtime plays change. Week 10 has two: Buffalo 34-31 Miami (OH) (game 401866454, old -0.059, new -0.057) and Massachusetts 31-30 Ball State (game 401866455, old +0.101, new +0.092). Nothing else moves.
- **Superseded recompute:** the first Week 10 table (garbage time kept) is recorded in the session log only as history.
