# Session: V5 Market-Line Study Planning (Contract 02)

## TL;DR
- **Worked On:** Start-session review, V5 status assessment, investigation of 2025 market-line sources, and authoring the 2025 market-line diagnostic contract.
- **Outcome:** Contract `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md` authored and **Approved** (user: "proceed"). Investigation found no authentic timestamped 2025 pre-kickoff quotes in the lake; study uses replay provider-recorded lines (`market_snapshots` `e4061aab...`) as a labeled diagnostic, V5-only.
- **Plan Contract:** `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md` (`Approved`)
- **Approval / Status:** User approved direction ("2025 market line study first, then full contract 11", sub-contract decomposition) and the presented plan ("proceed").
- **Blockers:** None. Findings 001/003 closed; 002/004 remain full-Contract-11 scope.
- **Next:** Fresh Terra task executes 02 via `implement-plan`; afterwards, plan the Contract 11 sub-contract decomposition (11B ratings-from-r9, 11C bridge + through-2025 fit, 11D verification).

## Context and Decisions
- Reviewed AGENTS.md, QUICKSTART, CONTEXT, and session logs 2026-09-19 through 2026-09-21. `main` clean at `e226677`; R2 backend with all credential groups present (no secrets printed).
- 12A scorecard final: 2025 headline (n=934/target) margin MAE 14.382, total MAE 13.200, `conditional_historical_results_only`.
- Subagent investigation established: (1) no genuinely timestamped 2025 quotes exist — only post-season CFBD captures (`captured_at` = fetch time) plus quarantined replay Silver versions; (2) the replay's exact line source and `consensus_then_median_v1` snapshot policy; (3) allowed source identities and the catalog-quarantine state; (4) V5 forecast rows join on `game_id`; (5) `evaluation.md`/roadmap market-comparison boundaries.
- **Decisions confirmed by user:**
  1. Line source: replay lines now as a reconstructed diagnostic comparison (no Odds API spend yet; staged option preserved).
  2. V5-only (no V4 benchmark).
  3. Contract 11 follows as decomposed sub-contracts.
- Margin sign convention identified as the principal correctness risk; the contract forces fixture + correlation gates before any metric.

## Work Completed
- Start-session checklist (context, git, storage, routing).
- Delegated very-thorough codebase investigation of 2025 line sources and governance.
- Presented the decision-complete plan; recorded user decisions via structured questions.
- Saved `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md` (Approved).
- Updated `docs/plans/index.md` with the new contract row.

## Files Modified
- `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md` — created (Approved)
- `docs/plans/index.md` — new Contract 02 row (market-line study)
- `session_logs/2026-09-21/04-v5-market-line-study-planning.md` — this log

## Validation
- [x] `uv run python contracts/validation.py` — passed
- [x] `uv run mkdocs build --strict --quiet` — passed
- [x] `git diff --check` — clean

## Amendments and Blockers
- None. Planning/documentation session: no R2, Neon, production, or model artifact access.

## Handoff Notes
- **Resume at:** Fresh Terra task → `implement-plan` → `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md`. Terra must resolve the full `e4061aab` version SHA from immutable replay-run input refs during preflight (fail closed).
- **Watch out for:** 12A forbids market access, so the new contract is required (done). The quarantined Silver state must not be touched. Margin sign convention gates everything.
- After implementation: final Contract 11 decomposition planning (11B/11C/11D).

**tags:** ["v5", "planning", "market-diagnostic", "contracts"]
