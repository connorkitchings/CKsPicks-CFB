# Session: Market-Line Retention Planning (Sol)

> **Staging note:** plan-mode write rules blocked the canonical session-log path.
> Copy this file to `session_logs/2026-09-03/02-market-line-retention-planning.md`
> together with the contract copy to `docs/plans/2026-09-03/market-line-retention.md`.

## TL;DR

- **Worked On:** Investigated the betting-lines data architecture; determined why
  last year's lines are unavailable; planned durable 2026 line retention.
- **Outcome:** Approved plan contract covering Neon quote persistence, opt-in
  The Odds API wiring, retention-chain verification, and a budget-gated
  2021–2025 backfill exploration.
- **Plan Contract:** `.opencode/plans/market-line-retention.md` (staged; canonical
  target `docs/plans/2026-09-03/market-line-retention.md`)
- **Approval / Status:** User approved content decision-by-decision and approved
  persistence on 2026-09-03. Contract status: Approved.
- **Blockers:** None for planning. Plan-mode tooling blocked writes outside
  `.opencode/plans/` — canonical copy/commit is a manual step.
- **Next:** Copy contract + this log to canonical paths, commit, open Terra task.

## Context and Decisions

- **2025 "lost" lines were quarantined, not deleted:** 2021–2025 CFBD lines lack
  authentic quote timestamps (ingest-time only; postgame/backfill pulls) and were
  adjudicated 2026-08-09 into `legacy_market_references` — permanently barred
  from leans/grades/features/ROI. Unrecoverable from CFBD.
- **2026 retention is already sound at the R2 layer:** every publish/close writes
  immutable Bronze captures + Silver `market_quotes`/`market_snapshots` with
  authentic timestamps. Remaining gaps: dead Neon quote tables, dormant Odds API
  adapter, manual-only cadence.
- User-selected directions: populate Neon quote tables (full price parity, writes
  inside the publish transaction, W0–1 retro-load); wire The Odds API (live
  endpoint ~2 credits/call, opt-in via `CFB_ODDS_API_ENABLED`, soft-fail);
  verify the existing chain first; explore backfill with per-season estimates for
  all of 2021–2025. Scheduler/intra-week cadence explicitly out of scope.
- R2 credentials exist only in the user's interactive ops shell (not in `.env`,
  `.env.local`, or non-interactive shells); Phase 0 verification runs there.

## Work Completed

- Start-session skill executed: context, logs, git state, env verified (no
  secrets exposed).
- Explore-agent deep dive + first-hand verification of: Neon market tables
  (schema.sql:200-241, no inserts exist), publish transaction
  (publish_to_db.py:455-499), ops publish steps (ops/__main__.py:1778-1913),
  snapshot builder provider filter (build_week_market_snapshot.py:63-73),
  Odds API adapter (the_odds_api.py), Silver normalization quote_id derivation
  (builders.py:209-296), snapshot canonicalization (lake.py:501-569), migration
  numbering (next: 0011).
- Decision-complete contract produced and approved.

## Files Modified

- `.opencode/plans/market-line-retention.md` — staged approved plan contract
  (canonical target: `docs/plans/2026-09-03/market-line-retention.md`)

## Validation

- [x] Read-only investigation only; no implementation files touched.
- [x] `git diff --check` clean.
- [ ] Canonical copy + commit + `uv run mkdocs build --quiet` after plan mode
      is lifted.

## Amendments and Blockers

- Plan-mode permission rules denied writes to `docs/plans/` and
  `session_logs/`; both artifacts staged under `.opencode/plans/`. No material
  conflicts with the approved content.

## Handoff Notes

- **Resume at:** Copy both staged files to their canonical paths, run
  `uv run mkdocs build --quiet`, propose the plan commit, then open a fresh
  Terra task with the contract path.
- **Watch out for:** All R2-touching validation must run in the user's shell with
  `CFB_R2_*` exported; `THE_ODDS_API_KEY` must be provisioned by the user before
  any Odds API rehearsal; every paid provider call needs explicit approval per
  the contract.

**tags:** ["data", "markets", "neon", "ingestion", "planning"]
