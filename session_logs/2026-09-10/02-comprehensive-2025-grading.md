# Session: Comprehensive 2025 Replay Grading

## TL;DR
- **Worked On:** Graded the 125 ungraded 2025 replay totals (below-threshold No-Bet games, e.g. week 2 Texas vs San Jose State).
- **Outcome:** Every 2025 replay prediction now has spread and total grades in Preview and Production. Final 2025 record: spread 380-366-16, total 398-359-5.
- **Plan Contract:** `docs/plans/2026-09-09/2025-v4-operational-replay.md` (Amendment 5)
- **Approval / Status:** User-requested follow-up; implemented and validated.
- **Blockers:** None
- **Next:** Commit contract amendment + log; the pending web deploy (session 04/05 files) remains the path to showing 2025 in production.

## Context and Decisions
- The operational scorer grades only above-threshold bets; 125 totals with
  |edge| < 1.5 were ungraded. The user requested a comprehensive 2025 win rate.
- Kept the identical frozen-line rule (`frozen_line_v2`), never overwriting
  existing grades. Live 2026 bets-only semantics intentionally unchanged.
- Weeks 1-15 replay totals now match the prior backfill exactly (398-358-5);
  the single delta is Army-Navy's total loss (certified artifact excluded it).

## Work Completed
- New `scripts/pipeline/backfill_replay_grades.py` (env-gated, dry-run,
  preview-first) + `tests/test_backfill_replay_grades.py` (7 tests).
- Ran Preview (125 grades, stats refreshed), verified per-week parity with the
  prior backfill, committed, ran Production (`--confirm-production`).
- Verified Texas-SJSU now graded (spread win, total loss); zero predictions
  without grades; `system_stats` 2025 refreshed.

## Files Modified
- `scripts/pipeline/backfill_replay_grades.py` - new (committed)
- `tests/test_backfill_replay_grades.py` - new (committed)
- `docs/plans/2026-09-09/2025-v4-operational-replay.md` - Amendment 5

## Validation
- [x] 7 new tests pass; full suite green before session work (822 passed)
- [x] Dry-run found exactly the 125-row gap
- [x] Per-week totals match prior backfill for all 15 weeks
- [x] `git diff --check`

## Handoff Notes
- **Resume at:** Commit Amendment 5 + this log.
- **Watch out for:** 2026 live grading stays bets-only by design.

**tags:** ["replay", "2025-season", "grading", "production"]
