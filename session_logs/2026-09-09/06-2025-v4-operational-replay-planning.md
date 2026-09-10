# Session: Plan 2025 V4 Operational Replay

## TL;DR
- **Worked On:** Investigated the current 2025 prediction publication and designed a week-by-week operational replay plan on the current V4 model track.
- **Outcome:** Plan approved and saved at `docs/plans/2026-09-09/2025-v4-operational-replay.md`.
- **Plan Contract:** `docs/plans/2026-09-09/2025-v4-operational-replay.md`
- **Approval / Status:** Approved — user selected "Week-by-week operational replay", chose honest replay model_id labeling and conditional week-16 inclusion, then said "go".
- **Blockers:** None
- **Next:** Execute Phases 0-5 of the contract.

## Context and Decisions

- Current published 2025 runs (`v4-2025-w1..w15`) came from the certified
  `rating_v4_historical_predictions` artifact via an ad-hoc backfill: model_id
  mislabeled as the production `-r2` bundle (trained 2021-2025, in-sample for
  2025), recorded artifact URIs missing in R2, code_sha null, reconstructed
  market lines, week 16 (Army-Navy) excluded.
- The user confirmed the scope: genuine week-by-week operational replay with
  the selection-time V4 engine (trained 2021-2024) and authentic pre-kickoff
  provider lines — explicitly NOT the data-first transformation track and NOT
  the 2026 rebuild plan.
- Key feasibility findings: `replay_season.py` exists but needs explicit
  immutable refs for 2025 (catalog as-of resolution cannot work);
  `refit_game_ordinal_bundle.py` can rebuild the selection-time bundle from
  frozen selection lineage; the v5 frame `fe55e758` provides certified
  point-in-time features for all 2025 weeks; Bronze has 16 weeks of 2025
  CFBD betting lines.

## Validation
- [x] Storage config verified (R2 backend + both Neon URLs present, no secrets printed)
- [x] DB state inspected read-only
- [x] Plan saved with approval source

## Handoff Notes
- **Resume at:** Phase 0 (line coverage verification).
- **Watch out for:** parity gate in Phase 1 must pass before any pipeline runs;
  preserve the dirty worktree from sessions 04/05.

**tags:** ["planning", "replay", "2025-season", "v4", "current-model"]
