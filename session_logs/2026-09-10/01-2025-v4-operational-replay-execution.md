# Session: 2025 V4 Operational Replay Execution + Promotion

## TL;DR
- **Worked On:** Executed the approved 2025 week-by-week V4 operational replay (plan `docs/plans/2026-09-09/2025-v4-operational-replay.md`), Preview-first then Production.
- **Outcome:** 16/16 weeks replayed in both databases with the selection-time bundle `v4-locked-test-replay-20260909b`; honest labeling; Army-Navy included; final YTD spread **380-366-16**, total **340-292-5**. Live `current_week` restored.
- **Plan Contract:** `docs/plans/2026-09-09/2025-v4-operational-replay.md` (Implemented)
- **Approval / Status:** Each gate approved by user (plan, pre-write commit, production promotion). Promotion complete; web renders from replay runs.
- **Blockers:** None remaining
- **Next:** Commit this session's remaining docs; the pending session-04/05 web commit stays separate.

## Context and Decisions

- The production `-r2` bundle is in-sample for 2025 (trained 2021-2025), so the
  replay rebuilt the selection-time design (2021-2024) from frozen lineage.
- First rebuild (Ridge-approximation baselines) failed the parity gate on
  baseline routes; investigation showed the frozen design reads frame OOF
  columns. `--baseline-source frame_columns` emits exact pass-through/blend
  models without touching production inference code. Parity max |delta|
  7.1e-15 across all 1,522 certified rows.
- Backfill runs remain `scored` (no `superseded` state exists in the schema);
  web resolution is latest-wins and verified for all 16 weeks.
- Replay grades only bet games (8 week-1 totals below the 1.5 edge threshold
  are No-Bet, ungraded) — operational convention, unlike the backfill which
  graded every game.

## Work Completed

- Phase 0: verified 2025 line coverage (762/762, incl. Army-Navy w16), Silver
  games `1e3ca7f7` exact frame match, frozen selection refs.
- Phase 1: rebuilt bundle `v4-locked-test-replay-20260909b` (manifest SHA
  `f1bb1f0a...`); added `--train-years` and `--baseline-source` to
  `refit_game_ordinal_bundle.py`; added `allow_locked_test_window` opt-in to
  `load_model_bundle_v3` + config threading.
- Phase 2: `replay_season_v4.py` orchestrator (5-step loop, explicit refs,
  deterministic market build, production support with `--confirm-production`),
  `conf/weekly_bets/v4_2025_replay.yaml`, market datasets
  (`market_snapshots e4061aab`, `market_quotes 32db239e`), 13 tests.
- Phase 3: 16 weeks replayed in Preview; waivers recorded; parity + coverage
  validated.
- Phase 4: 16 weeks replayed in Production (deterministic; week-7 predictions
  byte-identical to Preview); `current_week` snapshotted and restored to live
  2026/2; 762 games re-attributed; `system_stats` 2025 refreshed.
- Phase 5: contract marked Implemented with amendments; runbook replay note;
  this log.

## Files Modified

- `scripts/pipeline/refit_game_ordinal_bundle.py` — `--train-years` override, `--baseline-source`, manifest fields
- `src/cks_picks_cfb/model_bundle_v3.py` — locked-test-window opt-in
- `scripts/pipeline/generate_weekly_bets.py` — thread the opt-in flag
- `scripts/pipeline/replay_season_v4.py` — new orchestrator
- `conf/weekly_bets/v4_2025_replay.yaml` — new replay config
- `tests/test_replay_season_v4.py`, `tests/test_model_bundle_v3.py` — new/changed tests
- `docs/plans/2026-09-09/2025-v4-operational-replay.md` — Implemented + amendments
- `docs/plans/index.md` — replay entry (plan index change ships with this work)
- `docs/ops/weekly_pipeline.md` — historical replay runbook note

## Validation

- [x] Full suite: 812 passed, 2 skipped (re-run at end)
- [x] Parity gate PASS (max |delta| 7.1e-15, n=1,522)
- [x] Preview: 16 scored runs, 762 predictions, spread 380-366-16 / total 340-292-5, 16 waivers
- [x] Production: same; web resolution picks replay runs for all 16 weeks; live current_week restored
- [x] `git diff --check`
- [x] R2 immutable artifacts exist at all recorded run URIs

## Amendments and Blockers

- Plan amendments recorded in the contract (bundle id, column semantics,
  direct-frame gold, quotes lineage, leave-scored, current_week restore).
- Noted pre-existing unrelated dirty files (`scripts/research/run_data_first_phase3_v2.py`,
  `session_logs/2026-09-09/03-*.md`) — left untouched.

## Handoff Notes

- **Resume at:** Commit remaining docs (`docs/plans/index.md`,
  `docs/ops/weekly_pipeline.md`, contract amendment, this log).
- **Watch out for:** The session-04/05 web + docs changes are still uncommitted
  and separate from this work; the 2026 rebuild plan is untouched.

**tags:** ["replay", "2025-season", "v4", "production", "implementation"]
