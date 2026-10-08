# Production team-stats republish (as-of weeks 1-5): pre-apply evidence

Captured 2026-10-07 after the Track 1 promotion. The pre-apply evidence below is read-only. **The apply was run by the user at 2026-10-07 17:05:40Z; the agent made no Production write.** The post-apply verification is in the last section.

## What changes and why

Production `team_season_stats` was published 2026-10-02 15:25Z, before the punt-return fix (`5acd051`, on `main` since `0cd0a3c0`). Preview was republished 18:39Z with the fix. Republishing Production with the same inputs and the current code makes the two tables equal.

## Pinned inputs (all validated exactly once in the Production catalog)

| Dataset | Version |
|---|---|
| games | `31a337df6cf49f1578457ec6` |
| byplay | `443019a9a7b6a2454a4af4ac` |
| drives | `862815e2974a7fd6226841c1` |
| teams | `590e986596436aa001ff77b7` |
| game_outcomes | `d9a37cf473c63d2acc9f29cc` |

These are the versions every existing row's `source_versions` records. Unpinned, the publisher would take Production's newest `game_outcomes` (`d01d92ac…`, 2026-10-04), changing the inputs along with the code.

## Before payload (rollback source)

`before-production.json.gz`: 10,460 rows, all columns including `source_versions` and `updated_at`; payload SHA-256 `505de25760681b96…` (full value in `before-production.summary.json`). Identity `cks_prod_pipeline`, read-only transaction. `preview-target.json.gz` is Preview's current table (11,506 rows, SHA-256 `e82e6ab7468d8c13…`), which Production should equal after the apply (ignoring `updated_at`).

## Dry runs (`--weeks 1-5 --diff --dry-run`, pinned)

- **Preview** (`dry-run-preview.log`): would write 11,506 rows; compared 11,506; **0 changed, 0 only-old, 0 only-new**. The pinned build reproduces Preview's published values exactly.
- **Production** (`dry-run-production.log`): would write 11,506 rows; compared 10,460; **2,291 changed in value, 0 only-old, 1,046 only-new**.
  - New rows: the `ppa_per_play` metric, offense and defense, 523 team-weeks each.
  - Value changes: `conv_rate_3rd_4th` 810, `explosive_rate` 803, `turnover_rate` 678. Seven other metrics: 0 changes in value and rank.
  - Largest value moves: 3rd/4th-down rate up to 0.101, explosive rate up to 0.038, turnover rate up to 0.010.
  - Rank movement is material for display: explosive-rate ranks move up to 52 places (for example Navy defense week 5: 84 → 32), and 3rd/4th-down ranks up to 30.
- **Reconciliation of the counts** (Production dump against Preview dump, `shared rows`): of 2,923 shared rows that differ in any field, 2,291 differ in value, 479 differ only in rank (the dry run's "changed" counts value only, so these show up as rank movement), and 153 differ only in the play count `n` (value and rank equal). `games` and `cohort_size` never differ, and `source_versions` are equal on all 10,460 shared rows. This matches the 2026-10-07 audit.

All dry-run results are the expected ones; no stop condition was hit.

## Apply (user-run; writes to Production)

One transaction, five snapshots, upsert only (no deletes; no runs, predictions, selections or `current_week` touched). Paste exactly; the flags must be literal arguments:

```bash
PYTHONPATH=src:. zsh scripts/ops/with_production_pipeline_env.sh uv run python scripts/pipeline/publish_team_stats.py --season 2026 --weeks 1-5 --environment production --games-version 31a337df6cf49f1578457ec6 --byplay-version 443019a9a7b6a2454a4af4ac --drives-version 862815e2974a7fd6226841c1 --teams-version 590e986596436aa001ff77b7 --game-outcomes-version d9a37cf473c63d2acc9f29cc
```

Expected last line: `Upserted 11506 team_season_stats rows for weeks [1, 2, 3, 4, 5] (production).` The apply rewrites `updated_at` and `source_versions` on all 10,460 existing rows (unchanged content for the 7 untouched metrics).

## After the apply (agent, read-only)

Row-level equality with `preview-target.json.gz` on every column except `updated_at`; 11,506 rows; the CFBD sanity gate; unchanged fingerprints for everything else; the live matchup page (after the 5-minute revalidation).

## Rollback (not run)

The pipeline role cannot DELETE. Upserting the rows of `before-production.json.gz` restores the 10 older metrics' values, ranks and `source_versions`; the 1,046 `ppa_per_play` rows would remain (the page reads them; removing them needs the owner role and is a separate decision).

## Applied and verified (2026-10-07)

**Applied by the user** (terminal output pasted into the session): the command above ran once and ended with `Upserted 11506 team_season_stats rows for weeks [1, 2, 3, 4, 5] (production).` All 11,506 rows carry one `updated_at`, `2026-10-07 17:05:40.761325+00`, consistent with a single transaction.

**Agent verification (read-only, 17:06-17:09Z):**

- **Table equality:** Production now has 11,506 rows (`after-production.json.gz`, SHA-256 `1ee6c2a75ebfd25a…`); the key set equals Preview's, per-week counts match (352 / 2,068 / 3,014 / 3,036 / 3,036), and **0 rows differ from Preview in any column except `updated_at`** (including `source_versions`, `n`, `games`, `rank`, `cohort_size`).
- **Change set against the before payload:** exactly 2,923 pre-existing rows changed (2,291 in value, 479 rank-only, 153 play-count-only), plus the 1,046 new `ppa_per_play` rows; 7,537 pre-existing rows are unchanged in value, rank and `n`. This is the dry run's prediction.
- **Independent CFBD comparison** (`verify-production-asof5.log`, `…asof4.log`): all four gated metrics pass the 0.85 floor at both snapshots (as-of 5, like-for-like n=21: offense EPA/play 0.990, success rate 0.997; defense EPA/play 0.961, success rate 0.956; as-of 4, n=30: 0.980 / 0.991 / 0.984 / 0.983). The ungated explosiveness correlations are lower (as-of 5: 0.56 offense, 0.71 defense on like-for-like teams) and were not compared with the pre-fix values, so this check does not show the correction improved them.
- **Everything else unchanged:** re-running the fingerprint audit (`post-apply-*.json`) against the 16:07Z recapture shows no change in Production serving state, Week 5 grades, registrations, migration ledger, grants or venues; the only change is `team_season_stats_by_week` (which now matches Preview). Preview is unchanged.
- **Live page:** `https://c-ks-picks-cfb.vercel.app/matchup/401856819` (fetched about 2 minutes after the apply) now matches the Preview capture except the "Updated" run timestamp; the PPA/play dash cells went from 8 to 0 (`live-production-matchup-401856819-after.visible.txt`).

Not checked: other matchup pages, browser rendering, phone width. Rollback was not needed or performed.
