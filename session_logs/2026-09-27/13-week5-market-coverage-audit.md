# Session: Week 5 market coverage and weekly checklist audit

## TL;DR

- **Worked On:** Traced the 22 unlined Week 5 games through the original CFBD capture, Silver, Preview, production, and a fresh read-only provider request; reviewed the recurring close/open/freeze guidance.
- **Outcome:** The 2026-09-27 15:48:32Z CFBD capture produced 34 Week 5 rows; Silver quotes and snapshots, Preview, and production each retained 34 games with both spread and total. No downstream loss was found. A fresh CFBD Week 5 request around 21:19Z returned both line types for all 56 production-scheduled games, including all 22 previously unlined games. The published production run is therefore a valid but now stale market snapshot.
- **Plan Contract:** N/A (read-only audit and localized operating-documentation fast path).
- **Approval / Status:** User asked to double-check Week 5 coverage and make future close/open/freeze plans comprehensive. No new capture, candidate, authorization, selection, or freeze was applied.
- **Blockers:** The sole production Week 5 exact authorization binds run `2026w5-d6366e59fd43` and its existing artifact. A refreshed production run requires a new exact release packet and authorization.
- **Next:** Commit this audit's documentation so the V5 operator's clean-checkout guard passes. Then capture current lines into a new immutable Week 5 candidate, reconcile 56/56 spread and total coverage in Preview, validate its exact production packet, obtain the separate decision for that run, then publish/select and freeze before the first kickoff gate.

## Context and Decisions

- Verified `.env` selects the R2 backend and has the required source and Preview R2 credential fields, without revealing values. Used restricted production and Preview database roles for read-only queries. No repository-local `./data/` fallback was used.
- Production run `2026w5-d6366e59fd43` remains `published`, expected/predicted/lined 56/56/34, `data_as_of` 2026-09-27 17:35Z. Its 22 unlined rows have neither spread, total, nor a market snapshot; the 34 lined rows have both line types.
- Preview capture `4c4fcd01aa9d44afb9aa16c318f043c0` requested CFBD regular-season provider Week 5 and canonical Week 5, with `require_full_coverage: false`. It recorded 34 rows. Silver `market_quotes` `b91e54fc0b3b538764ac8d30` and `market_snapshots` `3cf7cb6386ad848f363ac0fd` each contain 34 rows. Production holds 34 DraftKings quotes across 34 Week 5 games. This evidence shows capture and processing counts agree; it cannot prove exactly when CFBD first posted the remaining lines.
- A fresh read-only CFBD request returned 59 provider games, 56 matching the production FBS schedule, and a DraftKings spread and total for all 56. No The Odds API request was needed. The optional second provider was not used for the original 34-row capture.
- Production has one Week 5 run and one exact authorization, `v5-live-2026w5-79add6d7`, for that run only. A later capture must create a new immutable prediction artifact and release identity; existing authorization cannot cover it.
- On the user's subsequent instruction to proceed, rechecked the branch and operator guard. `src/cks_picks_cfb/ops/v5_cycle.py:_clean_committed` rejects `apply` while these five documentation edits and this log remain uncommitted. The repository policy assigns Git operations to the user, so the fresh capture/candidate waits for that commit; no production or Preview write was attempted in this continuation.

## Work Completed

- Added a persistent close/open/freeze checklist to the V5 operator and linked it from AGENTS, Quick Start, weekly pipeline, and production runbook. It requires source-to-Silver-to-serving reconciliation, per-target missing-game IDs, a fresh availability check before release/freeze, a follow-up refresh, and exact authorization for any new production run.
- Left the live run and all provider/catalog/R2 state unchanged.

## Files Modified

- `AGENTS.md` — route every weekly close/open/publish/freeze request to the full checklist.
- `.codex/QUICKSTART.md` — correct the current Week 5 live status and link the checklist.
- `docs/ops/v5_weekly_operator.md` — durable sequence and market-coverage gates.
- `docs/ops/weekly_pipeline.md` — clarify partial publication and stale-capture handling.
- `docs/ops/production_runbook.md` — require reconciliation and new exact authorization for refreshes.
- `session_logs/2026-09-27/13-week5-market-coverage-audit.md` — this evidence record.

## Validation

- [x] Read-only production and Preview run/capture/quote queries.
- [x] One read-only CFBD Week 5 availability query, reconciled by exact scheduled game IDs.
- [x] `uv run mkdocs build --quiet`.
- [x] `git diff --check`.
- [x] Rechecked `uv run mkdocs build --quiet` and `git diff --check` before the clean-checkout handoff.

## Amendments and Blockers

No production authorization or write was inferred from this audit. The published run accurately reflects its Sept. 27 capture but needs a new release cycle to reflect lines now available. No model, schema, or release-policy amendment was made.

## Handoff Notes

- **Resume at:** Follow the new checklist to build and review a fresh Week 5 candidate with complete line coverage. Production activation of that exact candidate still needs its own release decision.
- **Watch out for:** Do not freeze the 34-line run or waive games whose lines are now available. The first kickoff is 2026-10-02 00:00Z; the operator's tighter lead-time gate still applies.
- **Suggested commit message:** `docs: require market coverage reconciliation in weekly operations`

**tags:** ["v5", "week5", "market-lines", "weekly-ops", "audit"]
