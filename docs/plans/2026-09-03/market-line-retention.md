# Durable Market-Line Retention: Neon Quote Persistence, The Odds API Wiring, and 2021–2025 Backfill Exploration

- **Status:** In Progress (code-complete 2026-09-03; credential-gated steps pending — see implementation log)
- **Created:** 2026-09-03
- **Planner:** Sol
- **Approval source:** User approval via interactive planning session 2026-09-03 (decisions D1–D8 reviewed and revised decision-by-decision; persistence explicitly approved)
- **Implementation log:** `session_logs/2026-09-03/03-market-line-retention-implementation.md`
- **Commit policy:** Separate plan commit recommended (touches Neon migrations and production ops behavior)

## Goal

Every betting line pulled during the 2026 season must be durably retained and easily
reusable in the future. Observable success criteria:

1. Neon `market_quotes` and `market_snapshot_quotes` are populated (currently dead
   tables — no `INSERT` exists anywhere), with full price parity, atomically with
   every `publish-week`, plus a one-time retro-load of the frozen Weeks 0–1 refs.
2. The dormant The Odds API adapter is wired into weekly ops as an **opt-in**
   second provider (live endpoint, soft-fail), adding per-book timestamped quotes
   with prices alongside CFBD captures.
3. The existing R2 Bronze/Silver retention chain is verified to have fired for
   2026 Weeks 0–1 before any code changes (Phase 0, read-only).
4. A budget-gated exploration determines whether authentic-timestamped lines for
   **2021–2025** can be recovered via The Odds API historical endpoint, ending in
   a go/no-go memo with no committed spend beyond explicitly approved probes.

## Current State

- **What happened to last year's lines:** the 2021–2025 CFBD lines were not
  deleted — they were adjudicated (2026-08-09, `docs/decisions/decision_log.md:117-133`)
  into the quarantined `legacy_market_references` Silver dataset stamped
  `timestamp_status=missing_authentic_timestamp`. They carry ingest-time
  timestamps only (many pulls were postgame or backfills), CFBD's endpoint exposes
  no per-quote market timestamps, and the compat partitions were overwrite-latest-wins.
  The timing metadata never existed and cannot be recovered from CFBD. Quarantine
  is permanent for those rows.
- **2026 chain (healthy):** CFBD `betting_lines` (authentic `captured_at` at fetch)
  → immutable Bronze (`lake/bronze/provider=cfbd/entity=betting_lines/...`, SHA-256
  content-addressed, catalog-registered) → immutable Silver `market_quotes` +
  `market_snapshots` (policy `consensus_then_median_v1`) → run-bound refs
  (`artifacts/<env>/pipeline-runs/<run>/market_quotes_ref.json` etc.) → predictions
  artifacts carry lineage → Neon `market_snapshots` + `predictions` (upserted at
  publish; `games.home_team_spread_line/total_line` mutable latest).
- **Gap 1 — dead Neon tables:** `contracts/schema.sql:200-241` defines
  `market_quotes` (quote_id, game_id, provider, captured_at, spread, total,
  source_capture_id) and `market_snapshot_quotes` (snapshot_id, quote_id, target);
  verified 2026-09-03 that nothing inserts into either. Quote-level history lives
  only in R2 Parquet.
- **Gap 2 — dormant Odds API path:** `src/cks_picks_cfb/data/the_odds_api.py`
  implements the historical NCAAF endpoint (20 credits/snapshot, regions=us ×
  spreads+totals), strict event matching (`match_odds_events_to_schedule`, lines
  44–89), and flatten with prices (`_flatten`, lines 183–242). Referenced only by
  tests and `scripts/data/estimate_historical_odds_backfill.py`. No
  `THE_ODDS_API_KEY` is configured anywhere in the repo.
- **Gap 3 — cadence:** captures occur only at manual `publish-week`/`close-week`
  invocations. Intra-week movement between runs is unobserved.
- Key mechanics verified: `normalize_market_quotes`
  (`src/cks_picks_cfb/data/silver/builders.py:209-296`) derives deterministic
  `quote_id` (sha256 of capture/game/provider/spread/total) when absent;
  `canonicalize_market_quotes_frame` (`src/cks_picks_cfb/data/lake.py:501-569`)
  emits flat `source_quote_ids` JSON per snapshot and CFBD-consensus-first
  selection; `build_week_market_snapshot.py:63-73` selects run-bound captures with
  `entity='betting_lines' AND provider='cfbd'`; publish transaction loop is
  `scripts/pipeline/publish_to_db.py:455-499`.
- Migrations `0002`–`0010` exist; next append-only migration is `0011`.
- R2 credentials are not present in any repo env file (`.env`, `.env.local`) nor
  in non-interactive shells — all R2-touching validation must run in the user's
  credentialed ops shell.

## Proposed Approach

Decisions (all user-reviewed 2026-09-03):

- **D1 — Quote persistence source:** the frozen per-run Silver `market_quotes`
  DatasetRef (full fidelity incl. prices), never the predictions CSV.
- **D2 — Migration `0011` (append-only):** `ALTER TABLE market_quotes ADD COLUMN
  IF NOT EXISTS` `home_spread_price`, `away_spread_price`, `over_price`,
  `under_price` (double precision), `quote_updated_at` (timestamptz),
  `source_event_id` (text). Existing columns and CHECK constraints unchanged.
  `contracts/schema.sql`, `contracts/schema.ts`, and `web/src/lib/schema.ts` stay
  in sync (`make contracts-check`).
- **D3 — Atomic publish writes:** quote upserts and snapshot-quote link rows are
  written **inside the existing `publish_week` transaction**
  (`INSERT … ON CONFLICT DO NOTHING`). Link targets derive from quote payloads:
  `spread` when `quote.spread` is non-null, `total` when `quote.total` is
  non-null (the snapshot's `source_quote_ids` is a flat list). Publish fails
  closed with an explicit error when predictions reference market snapshots but
  the `market_quotes` ref cannot be resolved or read.
- **D4 — Retro-load Weeks 0–1:** a small idempotent script replays the frozen
  `market_quotes`/`market_snapshots` refs for the published 2026 Week 0
  (`2026w0-55de0317120d`) and Week 1 runs into Neon — preview first, then
  production — so SQL history is complete from Week 0.
- **D5 — Odds API weekly wiring (opt-in, live endpoint, soft-fail):** new adapter
  method using `GET /v4/sports/americanfootball_ncaaf/odds`
  (regions=us, markets=spreads,totals, oddsFormat=american, dateFormat=iso;
  ~2 credits/call). Records carry `captured_at` = actual fetch time (same
  authenticity discipline as the CFBD path) and `quote_updated_at` from market
  `last_update`; flatten shape is identical to the historical method. New ops step
  `ingest_market_quotes` after `ingest_market`, gated on
  `CFB_ODDS_API_ENABLED=1` + `THE_ODDS_API_KEY`. The ingestion script is
  estimate-first (`--confirm` required for any spend) and logs unmatched events
  (never guesses; ambiguous matches raise). **Soft-fail:** when enabled and the
  provider errors, the step records a loud warning and publish proceeds
  CFBD-only — markets are evaluation-only and must not block publication. Default
  off ⇒ zero behavior change. The historical adapter method stays reserved for
  the Phase 3 backfill.
- **D6 — Builder admission:** `build_week_market_snapshot.py` also admits run-bound
  captures with `provider='the_odds_api' AND entity='market_quotes'`
  (ingestion_run_id `{pipeline_run_id}:market_quotes`), subject to the same
  AS_OF late-capture guard. Policy stays `consensus_then_median_v1`: CFBD
  consensus still wins when present; per-book quotes fill gaps and deepen medians.
  Snapshot IDs change only for consensus-less games (future weeks; documented and
  acceptable). If the odds step is enabled but failed, no odds captures exist and
  the builder proceeds CFBD-only naturally.
- **D7 — 2021–2025 backfill exploration (research, budget-gated):** (a) estimator
  run against the Silver games schedule for each season 2021–2025 (0 credits,
  2020 permanently excluded); (b) one probe snapshot per era uncertainty (20
  credits each, explicit user approval) verifying NCAAF historical coverage depth
  (does it reach back to 2021?) and event-match rate; (c) go/no-go memo with
  total cost. Backfilled quotes carry authentic provider snapshot timestamps and
  enter **canonical** `market_quotes` — never `legacy_market_references` — and
  must never alter any published/frozen artifact. 2025 replay/simulation research
  is the primary consumer; successor-v2 research may benefit.
- **D8 — Out of scope:** schedulers/intra-week capture cadence, model/feature
  changes (markets never enter features or selection), web UI changes beyond
  contract sync, quarantine changes, publication-mode changes.

## Scope

### Included

- Phase 0 read-only verification (Neon catalog/snapshot/coverage queries + R2 ref
  spot-checks in the user's credentialed shell) with a written verification note.
- Migration `0011` + contracts sync.
- `publish_to_db.py` quote/link persistence + Weeks 0–1 retro-load script.
- Live-odds adapter method + estimate-first ingestion script + opt-in ops step +
  snapshot-builder provider admission.
- Tests for all of the above; docs (ops, runbook, QUICKSTART, `.env.example`,
  decision log entry).

### Excluded

- Intra-week/scheduled captures (explicitly deferred this round).
- Any V4/model/feature/selection change; any web UI feature work.
- Changes to `legacy_market_references` or published/frozen artifacts.
- 2020 data (globally excluded); committed full backfill spend (probe/memo only).
- Neon population of backfilled historical quotes (deferred to the go/no-go
  decision).

## Affected Components and Contracts

- `contracts/migrations/0011_market_quote_payload.sql` (new; next number after 0010)
- `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts` (sync)
- `scripts/pipeline/publish_to_db.py` (quote/link writes in the activate transaction)
- `scripts/pipeline/backfill_market_quotes_db.py` (new retro-loader)
- `src/cks_picks_cfb/data/the_odds_api.py` (new live method)
- `scripts/data/fetch_odds_api_market_quotes.py` (new ingestion script)
- `src/cks_picks_cfb/ops/__main__.py` (optional `ingest_market_quotes` step, soft-fail semantics)
- `scripts/pipeline/build_week_market_snapshot.py` (provider admission)
- Tests under `tests/` (publication, silver, migrations, odds adapter)
- Docs: `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`,
  `.codex/QUICKSTART.md`, `.env.example`, `docs/decisions/decision_log.md`

## Implementation Tasks

### Task 0 — Verify the existing retention chain (read-only)

**Files:** none (verification note appended to the implementation log).

**Changes:**
- Query Neon (preview then production `DATABASE_URL`): `catalog.dataset_versions`
  rows for `market_quotes`/`market_snapshots` (2026); `market_snapshots` row
  counts; `predictions.market_snapshot_id` coverage for 2026 Weeks 0–1.
- In the user's credentialed ops shell: verify frozen refs
  `artifacts/{preview,production}/pipeline-runs/<run>/market_quotes_ref.json` +
  `market_snapshots_ref.json` exist and their Parquet reads with valid checksums
  for the Week 0 run `2026w0-55de0317120d` and the Week 1 run.

**Acceptance criteria:**
- Written counts for both environments; any gap (missing version, null snapshot
  coverage, unreadable ref) becomes a contract amendment before Task 1 proceeds.

**Validation:**
- Read-only SQL/`lake.read_source_capture`; no mutations.

### Task 1 — Migration 0011 and contracts sync

**Files:**
- `contracts/migrations/0011_market_quote_payload.sql`
- `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`

**Changes:**
- Append-only `ALTER TABLE market_quotes ADD COLUMN IF NOT EXISTS` for the six
  D2 columns; schema mirror updates stay byte-consistent (`make contracts-check`).

**Acceptance criteria:**
- Migration applies cleanly on preview; repeated application is a no-op; empty +
  legacy-schema migration fixtures pass; contracts check green.

**Validation:**
- `make contracts-check`; migration fixture tests; `make migrate-db ENV=preview`.

### Task 2 — Publish-time quote persistence + Weeks 0–1 retro-load

**Files:**
- `scripts/pipeline/publish_to_db.py`
- `scripts/pipeline/backfill_market_quotes_db.py` (new)

**Changes:**
- Resolve the run's frozen `market_quotes` DatasetRef from the pipeline-run
  artifacts; read the Silver Parquet via the lake; insert quote rows
  (`ON CONFLICT (quote_id) DO NOTHING`) and derive `market_snapshot_quotes` links
  per D3, inside the existing `publish_week` transaction. Fail closed when a
  snapshot-bearing run has no resolvable quotes ref.
- Retro-loader applies the same SQL from explicit refs (`--from-quotes-ref`,
  `--from-snapshots-ref`), idempotent, preview first then production.
- Do not alter frozen/scored-run immutability or the `market_captured_at` NaN
  fallback behavior beyond scoping it to snapshot inserts as-is today.

**Acceptance criteria:**
- A publish rehearsal on preview inserts quotes + links whose counts equal the
  Silver version row counts; rerun is a no-op; Weeks 0–1 rows exist in production
  Neon after the retro-load.

**Validation:**
- Publication contract tests (insert, idempotency, fail-closed missing ref,
  frozen-run immutability preserved); SQL count reconciliation.

### Task 3 — Live-odds adapter method

**Files:**
- `src/cks_picks_cfb/data/the_odds_api.py`

**Changes:**
- New `fetch_live` (or equivalent) method: live endpoint, same
  params/flatten/refusal-to-run-unauthenticated as the historical method; records
  carry `captured_at` = fetch time and `quote_updated_at` from `last_update`.

**Acceptance criteria:**
- Unit tests with fake `http_get` cover auth refusal, flatten parity (prices,
  per-book), and timestamp semantics.

**Validation:**
- `uv run pytest tests/` scoped to the adapter module.

### Task 4 — Opt-in ingestion script, ops step, builder admission

**Files:**
- `scripts/data/fetch_odds_api_market_quotes.py` (new)
- `src/cks_picks_cfb/ops/__main__.py`
- `scripts/pipeline/build_week_market_snapshot.py`

**Changes:**
- Ingestion script: load the week's Silver games schedule, match events strictly
  (ambiguous ⇒ error; unmatched ⇒ logged skip), estimate-first with `--confirm`
  required for spend, Bronze capture via the standard ingester path
  (`provider='the_odds_api'`, `entity='market_quotes'`).
- Ops: optional `ingest_market_quotes` step after `ingest_market`, gated on
  `CFB_ODDS_API_ENABLED` + `THE_ODDS_API_KEY`; **soft-fail** — provider errors
  record a loud warning (notifier) and the run proceeds CFBD-only; default off
  leaves all behavior identical.
- Builder: admit `provider='the_odds_api' AND entity='market_quotes'` run-bound
  captures under the same AS_OF late-capture guard; policy version unchanged.

**Acceptance criteria:**
- With the flag off, a full publish rehearsal is byte-identical to today's flow.
- With the flag on (preview), quotes from both providers coexist in one snapshot
  build; consensus-first selection is unchanged; a forced provider error emits a
  warning and completes the publish CFBD-only.

**Validation:**
- Unit tests (gating, soft-fail semantics, multi-provider builder admission,
  late-capture guard); one 2-credit live preview rehearsal only after explicit
  user approval with `THE_ODDS_API_KEY` provisioned.

### Task 5 — 2021–2025 backfill exploration (budget-gated memo)

**Files:**
- `scripts/data/estimate_historical_odds_backfill.py` (reuse; extend only if a
  per-season breakdown is needed)
- Research memo under `docs/experiments/` (location per `docs/experiments/index.md`)

**Changes:**
- Per-season estimator output (2021–2025) from the Silver games schedule (0 credits).
- Probe snapshots (20 credits each, explicit user approval per probe) to verify
  historical coverage depth and event-match rate for the eras in doubt.
- Go/no-go memo: cost, coverage, match rate, recommendation. No committed spend
  beyond approved probes; no Neon writes from historical data in this contract.

**Acceptance criteria:**
- Memo delivered with per-season estimates and probe evidence; the go/no-go
  decision is recorded (a "go" requires a new contract or amendment).

**Validation:**
- Estimator remains zero-network; probes run only after recorded approval.

## Testing Strategy

- Migration fixtures (empty + legacy schemas) extended for 0011.
- Publication contract tests: quote/link inserts, `ON CONFLICT DO NOTHING`
  idempotency, fail-closed missing quotes ref, frozen/scored-run immutability.
- Adapter tests: live + historical parity, auth refusal, timestamp semantics.
- Ingestion/ops tests: gating default-off equivalence, soft-fail warning path,
  strict event matching (ambiguous/unmatched), estimate-first confirm gate.
- Builder tests: multi-provider admission, late-capture guard, consensus-first
  policy stability.
- Gates: `make contracts-check`, scoped `uv run pytest`, `uv run ruff format . &&
  uv run ruff check .`, `uv run mkdocs build --quiet`, `make migrate-db
  ENV=preview` (user shell).

## Risks and Edge Cases

- **Credit spend:** every paid call is estimate-first with `--confirm`/explicit
  approval; weekly live capture ≈2 credits; default off.
- **Event-name mismatches:** strict matcher fails closed per event (ambiguous ⇒
  error); unmatched events are logged and skipped, never guessed.
- **Snapshot-ID drift:** adding per-book quotes changes `market_snapshot_id` only
  for consensus-less games, future weeks only; predictions FK the new ids
  naturally. Documented in the runbook.
- **Soft-fail step semantics:** must record warning state in the resumable run
  (not silent success); disabling the flag is the documented unblock path.
- **Neon volume:** trivial (hundreds of quote rows/week).
- **Append-only migration safety:** `ADD COLUMN IF NOT EXISTS` only; no data
  backfill inside the migration (retro-loader handles rows).
- **Frozen-artifact safety:** retro-loader and publish writes are
  `ON CONFLICT DO NOTHING`; no update/delete paths touch market rows.

## Definition of Done

- [x] Phase 0 verification note written (Neon + R2 both verified 2026-09-03).
- [x] Migration 0011 applied on preview (via `scripts/ops/with_preview_env.sh`)
      and production; contracts check green; re-application is a no-op.
- [x] Publish writes quotes + links atomically; Weeks 0–1 retro-loaded —
      preview: 220 quotes / 110 snapshots / 422 links; production: 118 quotes /
      59 snapshots / 224 links; every 2026 prediction's snapshot has links, zero
      misattributed targets; FK-foreign quotes (W1 games beyond the predicted
      set) intentionally remain in R2 only.
- [x] Live-odds path exists, default-off, preview-rehearsed with approval
      (two approved 2-credit captures; 17/49 Week 2 games matched because most
      Week 2 lines were not yet posted — matcher validated with zero Week 2
      name failures; isolated preview capture `e134dd22f01e41cdafe2387eaa2559c1`).
- [x] Backfill memo delivered with per-season estimates (27,980 credits total
      sparse cadence; 2025-only ~6,100); coverage probes remain a separately
      approved user decision — the go/no-go is deferred to that decision.
- [x] Docs + decision log updated; all gates pass.
- [ ] Coverage probes + final go/no-go recorded (user-gated; requires explicit
      approval per probe).

## Amendments

### Amendment 1 — Snapshot lineage repair and provider-name matching

**Reason:** Implementation surfaced two pre-existing gaps the contract's
acceptance criteria could not meet without repair: (a) the inference market
merge (`inference/weekly.py`) dropped `source_quote_ids`, `market_captured_at`,
rules, and provider counts, so Neon snapshot rows were persisted with degraded
lineage (publish-time timestamps, empty quote lists); (b) The Odds API mascot
names (e.g., "Texas Tech Red Raiders") never equal CFBD short names
("Texas Tech"), and a few CFBD abbreviations ("App State", "FIU", "FAU", "USF")
do not prefix-match either.

**Original approach:** quote/link persistence derived purely from frozen refs;
strict exact-name event matching.

**Revised approach:** the inference merge now carries the full market lineage
column set (future runs persist authentic lineage at publish time); the
retro-loader upserts snapshot lineage columns from the frozen Silver refs
(`ON CONFLICT (snapshot_id) DO UPDATE` limited to lineage columns — identity
columns never rewritten) and applies the same games-table FK guard as quotes;
`match_odds_events_to_schedule` gains an opt-in `allow_prefix` mode plus a
small `CFBD_NAME_EXPANSIONS` table, with ambiguity still raising loudly and
unmatched events logged and skipped.

**Impact:** Mechanical, no architecture, interface, or scope change. Neon is
derived serving state and R2 Silver remains the source of truth; already
published/frozen artifacts are untouched. First live rehearsal (2 credits)
exposed the name gap before any ops wiring; the second (2 credits) validated
the fix.
