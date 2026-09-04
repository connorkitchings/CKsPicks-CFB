# Session: Market-Line Retention Implementation (Terra)

## TL;DR

- **Worked On:** Implemented the approved market-line-retention contract —
  Neon quote persistence, opt-in The Odds API live capture, snapshot-builder
  provider admission, docs, and the backfill exploration memo — then completed
  every operational step (migrations, retro-loads, live rehearsals).
- **Outcome:** All code + operational tasks complete. Production Neon now
  holds the full Weeks 0–1 quote lineage (118 quotes / 59 snapshots / 224
  links); preview verified first (220/110/422). Only user-gated item left:
  the backfill coverage probes and go/no-go.
- **Plan Contract:** `docs/plans/2026-09-03/market-line-retention.md` (Status:
  `In Progress` — see Amendment 1 and the single open DoD item)
- **Approval / Status:** Contract approved 2026-09-03 (interactive session);
  implementation and both 2-credit rehearsals explicitly authorized.
- **Blockers:** None code-side. Backfill probes await a user budget decision.
- **Next:** User decides on coverage probes (20 credits each); next week's
  publish-week exercises the full chain with quotes persistence natively.

## Context and Decisions

- Task 0 (verification, Neon/production): `catalog.dataset_versions` holds 5
  `market_quotes` versions (198 rows) and 5 `market_snapshots` versions (123
  rows); Neon `market_snapshots` has 59 rows; 2026 snapshot coverage is
  complete — W0 scored `2026w0-55de0317120d` 8/8, W0 published
  `2026w0-79ec2aebcb00` 8/8, W1 published `2026w1-b2c739321e5d` 43/43 with
  distinct snapshot IDs. R2 spot-check (completed 2026-09-03 after
  credentials were added to `.env`): all three production pipeline runs
  (`55de0317…`, `79ec2aeb…`, `b2c73932…`) hold checksum-verified frozen
  `market_quotes`/`market_snapshots` refs — W0 runs 16 quotes / 8 games /
  8 snapshots each; W1 run 134 quotes / 91 games / 91 snapshots (Bovada,
  DraftKings). W1 quotes beyond the 43 predicted games will be FK-skipped by
  the retro-loader and remain durable in R2. Task 0 is fully closed.
- `snapshot_week_inputs.py` now freezes the run's `market_quotes` ref into
  `input_refs.json` (entity `betting_lines_quotes`), which flows through
  `generate_weekly_bets` into the run manifest's `input_dataset_refs`, from
  which `publish_to_db` resolves it. Resume caveat (documented in the
  decision log): pipeline runs started before this change cannot resume —
  their frozen `input_refs.json`/definition SHA predates the new entry.
- Soft-fail semantics: the `ingest_market_quotes` ops step records
  `skipped` (flag off / key missing), `degraded` (provider failure — stderr +
  best-effort webhook warning, never raises), or `captured` statuses in the
  durable step outputs; its resume validator never re-issues the paid
  request.
- The user committed their in-flight research work as `83ddd03` mid-session.

## Work Completed

- Task 1: migration `0011_market_quote_payload.sql` (six additive
  price-payload columns); `contracts/schema.sql` + `schema.ts` +
  `web/src/lib/schema.ts` synced; migration fixture test extended.
- Task 2: `publish_to_db.py` writes `market_quotes` rows and derives
  `market_snapshot_quotes` links inside the publish transaction (ON CONFLICT
  DO NOTHING; fails closed when a snapshot-bearing run lacks a quotes ref);
  `scripts/pipeline/backfill_market_quotes_db.py` catalog-driven retro-loader
  (explicit refs or `--season`, `--dry-run`, FK-safe, idempotent).
- Task 3: `TheOddsAPIAdapter.fetch_live` (live board, ~2 credits,
  fetch-time `captured_at`, `quote_updated_at` from `last_update`).
- Task 4: `scripts/data/fetch_odds_api_market_quotes.py` (estimate-first,
  `--confirm` spend gate, strict event matching, Bronze + catalog capture as
  `provider=the_odds_api`, `entity=market_quotes`); ops step
  `ingest_market_quotes` (gated `CFB_ODDS_API_ENABLED` + `THE_ODDS_API_KEY`,
  soft-fail, resume-safe); `build_week_market_snapshot.py` admits
  `the_odds_api` captures under the unchanged `consensus_then_median_v1`
  policy.
- Task 5: `docs/experiments/odds-api-historical-backfill-2026.md` memo
  (estimator tables, probe protocol, go/no-go criteria); no spend committed.
- Docs: weekly_pipeline.md, production_runbook.md, QUICKSTART, .env.example,
  decision log entry 2026-09-03, experiments index.

## Files Modified

- `contracts/migrations/0011_market_quote_payload.sql` — new
- `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts` —
  market_quotes price-payload columns
- `scripts/pipeline/publish_to_db.py` — quote/link persistence in publish
- `scripts/pipeline/backfill_market_quotes_db.py` — new retro-loader
- `scripts/pipeline/snapshot_week_inputs.py` — freezes market_quotes ref
- `scripts/pipeline/build_week_market_snapshot.py` — multi-provider admission
- `scripts/data/fetch_odds_api_market_quotes.py` — new ingestion script
- `src/cks_picks_cfb/data/the_odds_api.py` — fetch_live + shared auth gate
- `src/cks_picks_cfb/ops/__main__.py` — soft-fail step + wiring
- `tests/test_publish_to_db.py`, `tests/test_the_odds_api.py`,
  `tests/test_odds_api_ops_step.py` (new), `tests/test_migration_integration.py`,
  `tests/test_ops_state_machine.py` — coverage for all of the above
- Docs: `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`,
  `.codex/QUICKSTART.md`, `.env.example`,
  `docs/decisions/decision_log.md`, `docs/experiments/index.md`,
  `docs/experiments/odds-api-historical-backfill-2026.md` (new)

## Operational Completion (2026-09-03, same session)

- **Migration 0011:** applied on preview via
  `zsh scripts/ops/with_preview_env.sh make migrate-db` (preview tables are
  owned by `cks_preview_migrator`; the Keychain wrapper supplies the owner
  connection — the `.env` `PREVIEW_DATABASE_URL` as `neondb_owner` cannot do
  DDL there) and on production via `make migrate-db` (rode along pending
  `0009`/`0010`, both additive). Re-runs are no-ops on both branches.
- **Retro-load preview:** catalog mode resolved 4 versions / 300 rows
  (204 persisted, 96 FK-skipped); explicit-ref repair pass across 5 preview
  runs persisted 220 quotes, upserted lineage on 110 snapshots, reconciled
  422 links. Final state: 110/110 snapshots with quote lineage.
- **Retro-load production:** explicit refs for the 3 published runs — 118
  quotes, 59 snapshots repaired, 224 links; every 2026 prediction's snapshot
  has links; zero misattributed targets; 48 W1 quotes for non-predicted games
  intentionally remain in R2 only.
- **Discovered + fixed (Amendment 1):** the inference market merge dropped
  `source_quote_ids`/`market_captured_at`/rules/counts (all Neon snapshots had
  degraded lineage), and The Odds API mascot names broke exact matching.
  Fixes: extended merge columns; retro-loader lineage upsert + snapshot FK
  guard; `allow_prefix` matching + `CFBD_NAME_EXPANSIONS`; hermetic auth
  tests (ambient `THE_ODDS_API_KEY` leaked into `api_key=""`).
- **Live rehearsals (user-approved, 4 credits total):** first capture exposed
  the name gap (0 matches); second validated the fix — 17/49 Week 2 games
  matched, entirely explained by unposted Week 2 lines (board's earliest
  quote: Sep 12), zero Week 2 name failures; isolated preview Bronze capture
  `e134dd22f01e41cdafe2387eaa2559c1` (31 quotes / 17 events, Bovada +
  DraftKings class books).
- **Backfill memo estimates (zero-network):** 2021–2025 sparse-cadence total
  27,980 credits (2021: 5,340 · 2022: 5,320 · 2023: 5,300 · 2024: 5,920 ·
  2025: 6,100). Coverage probes remain user-gated.

## Deviation Disclosure (worktree hygiene)

- A repo-wide `ruff format .` was run in error; 21 clean-at-HEAD files were
  restored immediately. Two files with genuine uncommitted user research
  edits (`scripts/pipeline/build_r2_prior_tournament.py`,
  `scripts/pipeline/materialize_offseason_context.py`) retain ruff
  formatting layered on those edits — content is preserved, formatting may
  differ from the user's editor output.
- One pre-existing HEAD lint error (unused import in
  `tests/test_successor_legacy_comparison_ref_set.py`, introduced by
  `83ddd03`) was auto-fixed to unblock the `ruff check` gate.

## Validation

- [x] `uv run pytest -q` — 658 passed, 2 skipped
- [x] `uv run ruff check .` — clean; changed Python files format-clean
- [x] `make contracts-check` — passed
- [x] `uv run mkdocs build --quiet` — ok
- [x] `git diff --check` — clean
- [x] `web` typecheck (`tsc --noEmit`) — clean
- [x] Migration 0011 on preview + production; idempotent on both
- [x] Retro-load Weeks 0–1 on preview then production; counts reconciled and
      verified (lineage coverage 100%, zero misattributed links)
- [x] R2 ref spot-check for Task 0 (all three production runs checksum-verified)
- [x] Live preview rehearsals with `THE_ODDS_API_KEY` (2× user-approved
      2-credit captures; matcher validated)
- [x] Backfill estimator tables completed in the memo (probes user-gated)
- [ ] Coverage probes + final go/no-go — pending user budget decision

## Amendments and Blockers

- None material. All deferred items were anticipated by the contract
  (credential/approval-gated steps); the plan remains `In Progress` until
  they close.

## Handoff Notes

- **Resume at (user shell, preview first):**
  1. `make migrate-db` with `DATABASE_URL` pointed at preview
     (`PREVIEW_DATABASE_URL`), then production.
  2. `PYTHONPATH=.:src uv run python scripts/pipeline/backfill_market_quotes_db.py --season 2026 --dry-run`
     then without `--dry-run` (preview, then production).
  3. Next `make publish-week ... ENV=preview` exercises the full chain
     (quotes ref freeze → quote/link writes; `ingest_market_quotes` records
     `skipped` while disabled).
- **Watch out for:** in-flight pipeline runs from before this change cannot
  resume (definition SHA / input-ref set changed) — start a new run. Enable
  `CFB_ODDS_API_ENABLED=1` only with `THE_ODDS_API_KEY` set; it is soft-fail,
  and disabling the flag is the documented unblock. Every paid Odds API call
  is estimate-first and requires `--confirm`/explicit approval.

**tags:** ["data", "markets", "neon", "ingestion", "ops"]
