# Parity gate evidence (Phase 1, section 1f)

**Result: PASS.** I ran the release-path builder on the pinned Week 7 revision and passed its output through the web transforms. For Through Weeks 2–6 the values match `web/src/lib/explosiveness-data.generated.ts` on every field of all 1,380 team-window entries, and on all 10 per-window/side `EXPLOSIVENESS_AVERAGES`, at the file's serialized precision under the file's own rounding rule (Python `round`, ties to even). No mismatches.

## Inputs

| Item | Value |
|---|---|
| Revision manifest | `conf/season/2026/revision_manifest_w7_v1.json`, SHA-256 `208a4a5b7b070360e78909c78f3d6ed2efcf255ce8b5d8628110e939612040f6` |
| Model manifest (needed by `load_inputs`) | `conf/season/2026/model_manifest_v1.json`, SHA-256 `a46fa768b45dd9b274b12f4a7efe52ac01ae749f005998aa0c4992e2cd836605` |
| Pinned byplay | `lake/silver/dataset=byplay/version=f31827642be9f7439b40b876/data.parquet`, SHA-256 `828c90a3432a8b37ed4e10942355a0428dfed4d85104d5394d3a591233c04fbe` |
| Storage | Preview R2, read-only (`ReadOnlyStorage`); `read_ref` checked each SHA-256 before Parquet decoding |
| Identity | season 2026, `through_week` 6, `active_week` 7 |
| Static file | `web/src/lib/explosiveness-data.generated.ts`, SHA-256 `4095695972a5d68174c0110fb316f29704b11fa04f94db469f9425225f3c59f4` |
| Code | HEAD `23621eb3` plus the uncommitted Phase 1 working tree; `team_game_yardage.py` `ba40df3e…23c6`, `projection_charts.py` `ce900b82…4b99`, `web/src/lib/charts.ts` `bc76b329…bcca` |

## Method

1. `season.inputs.load_inputs(reader, model, revision, 6)` is the prepare path's input loader. `projection_charts.build_charts(..., identity={"active_week": 7})` built the release's `team_season_roster`, `team_game_stats` and `team_game_yardage` rows from it. `build_yardage_rows(inputs, 7)` (the recomputation used by the `chart_yardage_recomputed` prepare check) returned rows identical to `build_charts`'s `team_game_yardage`. Its key set equals `team_game_stats`.
2. I joined the rows by `(game_id, team)` into camelCase `TeamGameRow`s. Then the real web code (`efficiencyPoints` and `scatterRanks` from `web/src/lib/charts.ts`, run with `tsx`) computed every Through Week N (2–6) × side:
   - `er` is the y value of metric `explosive_rate` (Σ`explosive_n` / Σ`yards_n`), and `ys` is the y value of `yards_per_success` (Σ`success_yards_sum` / Σ`success_yards_n`).
   - `sr` is x (from `team_game_stats` success sums), and `ppa` is the y value of metric `ppa` (`epa_sum` / `epa_n`).
   - `n` is Σ`yards_n`.
   - `erRank` and `ysRank` are the `scatterRanks` y competition ranks over the full plotted population. Defense ranks with lower values better.
   - The averages are the pooled `average` of each metric's scatter.
3. Comparison against the static file: `n` and the ranks must be exact. `er` (5 decimals), `ys` (3), `sr` (5) and `ppa` (4) must equal the file after rounding to that precision. Nulls must match nulls.

Population checks: 138 roster teams; 329 eligible games; 658 team-game rows (`team_game_stats` = `team_game_yardage`); 40,461 eligible plays, and Σ`off_yards_n` is also 40,461. These figures agree with the research report. The canonical SHA-256 of the `team_game_yardage` rows is `931aac3242b65e9dd7cc437b02d5347b97ba9c4b823b2eca11908b579d6f93ca`.

## Results

| Field | Match | Mismatch | Max unrounded \|built − file\| |
|---|---|---|---|
| `er` | 1380 | 0 | 5.0e-6 |
| `ys` | 1380 | 0 | 5.0e-4 |
| `sr` | 1380 | 0 | 5.0e-6 |
| `ppa` | 1380 | 0 | 5.0e-5 |
| `n` | 1380 | 0 | 0 |
| `erRank` | 1380 | 0 | 0 |
| `ysRank` | 1380 | 0 | 0 |
| `EXPLOSIVENESS_AVERAGES` `er` / `ys` / `sr` | 10 / 10 / 10 | 0 | — |

- **Key sets.** Both sides have exactly the same 1,380 keys (138 teams × 5 windows × 2 sides).
- **Nulls.** The only nulls are `2:offense:Northwestern` and `2:defense:Northwestern`: no eligible games through Week 2, so `n` = 0 and every metric and rank is null. The builder produces the same.
- **Averages.** Offense and defense are identical in every window, as expected for FBS-vs-FBS pooling. The values run from `er` 0.06522, `ys` 12.276, `sr` 0.41313 (Week 2) to 0.06742, 12.244, 0.42098 (Week 6).
- **Rounding mode.** 30 built values sit exactly on a binary halfway point at the serialized precision, for example `2:defense:Clemson` `sr` 0.390625 → file 0.39062 and `2:offense:UConn` `ys` 13.1875 → file 13.188. The file resolves all 30 ties to even, which is Python `round`. A first pass that used JavaScript `Number(x.toFixed(d))` (ties away from zero) reported 14 apparent mismatches: `er` 2, `ys` 9, `sr` 3. Every one was an exact tie, and every one resolves under ties-to-even. So these are artifacts of the comparison's rounding, not data differences. Under the file's own rounding, all 30 ties match.

## Reproduction

The scratch scripts sit outside the repo, in `/private/tmp/claude-501/-Users-connorkitchings-Desktop-Repositories-ckspicks-cfb/a7a7f7f1-4c01-48de-a90d-ff7d6ed3cdc7/scratchpad/`:

1. `uv run --offline --no-sync python …/scratchpad/parity_dump.py …/scratchpad/release_rows.json` (from the worktree root; loads Preview R2 credentials from the owner's local `.env` without logging them).
2. `./node_modules/.bin/tsx …/scratchpad/parity_compare.ts …/scratchpad/release_rows.json …/scratchpad/parity_result.json` (from `web/`).
3. `uv run --offline --no-sync python …/scratchpad/parity_halfeven.py …/scratchpad/parity_result.json` (ties-to-even recheck plus the list of exact ties).
