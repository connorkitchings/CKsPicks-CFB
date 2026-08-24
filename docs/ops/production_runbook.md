# Production Runbook — 2026 Season

> **As-built operations for the live system** (deployed 2026-08-18).
> This runbook reflects production reality: Vercel + Neon + Cloudflare R2 with
> the V4 launch bundle. Superseded V2 deployment and rollback material is in
> the [documentation archive](../archive.md). The rating successor is
> shadow-only until separately promoted.
> Authoritative remaining-work tracker:
> [Week 0 Launch Contract](../plans/2026-08-18/week0-launch-execution.md).

## Production topology (as built)

| Component | Value |
|---|---|
| Site | https://c-ks-picks-cfb.vercel.app (Root Directory `web/`) |
| Publication mode | `CFB_PUBLICATION_MODE=predictions`, `CFB_PUBLICATION_SEASON=2026`, `CFB_PUBLICATION_WEEKS=0` |
| Database | Neon **production branch** (separate from `preview-2026`); migrations 0002–0008 applied |
| Web DB role | `cks_prod_web` — read-only LOGIN role used by Vercel (`DATABASE_URL`) |
| Catalog | Hydrated from Preview via COPY (7,163 source captures, 85 dataset versions); repopulates `quality_results` as production audits run |
| Object storage | R2 bucket `cks-picks-cfb-preview` — **shared with Preview** (immutable artifacts are checksummed, environment-neutral); separation is by Neon branch |
| Launch model | V4 ten-route bundle `week0-2026-v4-strict-20260818-r2` (design SHA `ae34ddc7…`, bundle SHA `72429375…`), config `conf/weekly_bets/v4_2026.yaml` |
| Fallback | V2 preview bundle (`week0-2026-preview-20260814`, frozen run `2026w0-a0edb9e72cb1`) — never mutated |
| Active run | Query `/api/health` or `current_week.active_run_id`; each progressive publish activates a new immutable run. |

Invariant: a failed or partial pipeline step never activates anything. Every
mutating command runs through `python -m cks_picks_cfb.ops` with an explicit
`ENV`.

## Weekly operating cycle (production)

### 1. Pregame publish (progressive, as lines arrive)

```bash
# AS_OF must be ~5 minutes AHEAD of the run so the market capture
# falls before the cutoff (fail-closed otherwise).
make publish-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DDTHH:MM:SSZ \
  ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml
```

- Each rerun creates a **new immutable run** (new R2 prefix, new `prediction_runs` row) and moves `current_week.active_run_id` on activation.
- Missing lines are allowed — the site shows the game without a lean ("Line unavailable—model prediction shown, no lean").
- During game week (e.g. Aug 25–28) rerun daily or as lines move; verify coverage each time (see Health).

### 2. Manual snapshot ledger and final freeze (before kickoff)

Every progressive publish is a durable timing observation, not a replacement
for an earlier one. After each successful manual publish, record the run ID,
prediction artifact checksum, market capture time, requested `AS_OF`, and
8/8/8 health coverage in the current session log or launch ledger. The public
site deliberately advances to the newest published run; the immutable R2
artifacts preserve the full captured history for later edge analysis.

The first public Week 0 snapshot is:

| Run | Prediction checksum | Market capture | `AS_OF` |
| --- | --- | --- | --- |
| `2026w0-55de0317120d` | `47dbbd55b62172d0c8cd52162c0070774afcf5ca829223b166298fb767398dc8` | `2026-08-20T13:17:39Z` | `2026-08-20T13:19:14Z` |

No scheduler is configured for Week 0. The timing record contains only
manually published captures; it must not be described as a continuous
best-time-to-bet feed.

Before kickoff, make one final progressive publish, review it, then freeze it:

```bash
# Final publish (Aug 28 pattern)
make publish-week YEAR=2026 WEEK=0 AS_OF=... ENV=production \
  CONFIG=conf/weekly_bets/v4_2026.yaml

# User reviews the run, then freeze:
make freeze-week YEAR=2026 WEEK=0 ENV=production
# Waiver for a genuine provider exception, if needed:
make freeze-week YEAR=2026 WEEK=0 ENV=production \
  WAIVER="provider did not list total for game 123"
```

Freeze requires predictions and both line types for every eligible game.
Frozen runs are immutable and are what scoring later resolves.

### 3. Public predictions reveal (completed 2026-08-21)

The reviewed `2026w0-55de0317120d` run is public in `predictions` mode while
its state remains `published`; it is not the final grading authority. The
homepage shows the latest immutable model-vs-market snapshot, numeric edges,
and the model-accuracy panel. `CFB_PUBLICATION_MODE` is fail-closed: only the
exact value `predictions` exposes model fields; every other value remains
market-only.

### 4. Postgame close (after finals)

```bash
make close-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=production
```

Scoring resolves the frozen run from Neon, verifies that run's immutable R2
artifact, writes run-specific `prediction_grades`, and derives
`system_stats`/records from them.

### 5. Optional: CFBD Model Pick'em

```bash
# Reconcile against the authenticated contest slate (needs CFBD_PREDICTION_TOKEN)
make export-pickem YEAR=2026 WEEK=0 VALIDATE=1
make export-pickem YEAR=2026 WEEK=0 DRY_RUN=1
# Submission only after explicit user approval of game IDs and margins:
make export-pickem YEAR=2026 WEEK=0 SUBMIT=1
```

Pass the exact frozen run CSV with `--input-csv`. The Pick'em token is
separate from `CFBD_API_KEY` and short-lived.

## Health checks

```bash
# Endpoint: schema version, active run/state, expected/predicted/lined
# coverage, artifact freshness, data cutoff, last successful publish
curl https://c-ks-picks-cfb.vercel.app/api/health

# Run inventory + active pointer
psql "$DATABASE_URL" -c "SELECT run_id, season, week, state, expected_games, predicted_games, lined_games FROM prediction_runs ORDER BY created_at DESC;"
psql "$DATABASE_URL" -c "SELECT season, week, active_run_id FROM current_week WHERE id = 1;"
```

Freshness expectations: predictions republish as lines arrive pregame; after
freeze the run must not change. Each publish/activation fires a signed
on-demand ISR revalidation (`CFB_REVALIDATION_URL` + `REVALIDATION_SECRET`,
configured 2026-08-20), so the homepage refreshes immediately; the five-minute
ISR remains the fallback if the signed call fails. `catalog.quality_results`
in production was truncated at hydration (preview-specific data) and
repopulates as production audits run — this is expected.

## Rollback / recovery

There is no MLflow/joblib rollback in this system. Runs are immutable; rollback = reselection:

1. Identify the last good frozen/scored run (`prediction_runs` query above).
2. Repoint `current_week.active_run_id` to it (single Neon transaction — the same activation mechanism the publisher uses; do not hand-edit prediction rows).
3. If a bad run was never activated, no action is needed — failed/partial steps activate nothing by design.
4. Resume an interrupted operation with the same `--pipeline-run-id` via the Python CLI; `make reconcile YEAR=2026 ENV=production` catalogs inactive/orphaned artifacts.

Never mutate a frozen run or its R2 artifacts. Create a new run instead.

## Failure modes

| Symptom | Meaning / action |
|---|---|
| Publish exits nonzero | Correct the failure and create a new run; never continue manually to activation |
| `AS_OF` before market capture | Build fails closed — set `AS_OF` ~5 min ahead and rerun |
| Game missing a line | Allowed; site shows no lean for it. Rerun publish later as lines arrive |
| Freeze blocked on missing line types | Record an explicit `WAIVER` only for genuine provider exceptions |
| Health shows stale run / low coverage | Rerun `publish-week`; check `prediction_runs` for a failed activation |
| Vercel upload file-count error | Root `.vercelignore` limits upload to `web/`; retry the deploy |
| Wrong-database guard trips | `CFB_RUNTIME_TARGET_RESOLVED` marks resolved envs for child steps; do not unset it when shelling into ops steps |

## Environment / credential notes

### Optional failed-step alerts

Set `CFB_OPS_ALERT_WEBHOOK_URL` to receive a best-effort JSON notification when
a `publish-week`, `freeze-week`, or `close-week` step fails after its failure is
recorded in Neon. `CFB_OPS_ALERT_TIMEOUT_SECONDS` defaults to `5`. Alert delivery
is observability only: a missing, slow, or failing webhook never changes the
pipeline's original failure or activation boundary.

- Production credentials live in `.env` / macOS Keychain per the preview pattern; never commit them.
- Preview operations use `zsh scripts/ops/with_preview_env.sh <cmd>` so legacy `.env` values cannot target the wrong branch. (The stale `PREVIEW_DATABASE_URL` entry pointing at the deleted `ep-delicate-sun` branch was removed from `.env` on 2026-08-20; duplicate lines were collapsed.)
- On-demand revalidation (2026-08-20): `REVALIDATION_SECRET` is set in Vercel (production) and `.env` (`CFB_REVALIDATION_URL=https://c-ks-picks-cfb.vercel.app/api/revalidate`); the route rejects missing/invalid signatures (401) and stale timestamps (>5 min). Rotating the secret requires updating both sides and redeploying.
- R2 source/destination separation guard still applies to import workflows; the shared preview/production artifact bucket is an explicit, approved exception (launch contract Amendment 2).

---

_Last Updated: 2026-08-19_
