# Session: Week 1 Freeze and R2 Prior Tournament

## TL;DR

- **Worked On:** Froze the 2026 Week 1 production run, then executed the remaining R2 between-season prior tournament task of the early-week contract, including two lineage repairs.
- **Outcome:** Run `2026w1-b2c739321e5d` is frozen (43/43/43, no waiver). The R2 tournament completed at `artifacts/research/rating-successor-v2/r2-prior-20260904-4c6e610/` with winner `continuity_ridge_alpha_0_1` (all gates passed) and the cross-report decision memo is published.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md` (now Implemented)
- **Approval / Status:** User approved freeze + research continuation in opencode on 2026-09-04; user executed the two repair commits.
- **Blockers:** None.
- **Next:** Close Week 1 on Tuesday 2026-09-08 (`make close-week YEAR=2026 WEEK=1 AS_OF=<ts> ENV=production`), then the Week 2 cycle. Research: R3 within-season updates (Preview-isolated); investigate the non-finite state rows behind the R2 matmul warnings first.

## Context and Decisions

- The Week 1 slate's first kickoff (Thu 2026-09-03 22:00 UTC) passed before freeze; freeze still correctly locks the validated Sept 2 snapshot for the remaining ~40 games. No waiver was required.
- The R2 runner had two schema-contract defects versus the R1 artifact layout, fixed by user-executed commits:
  - `278120a` — outcome-ref path doubled the `foundation/` segment, so every season hit `NoSuchKey` and all folds skipped.
  - `4c6e610` — R1 `game_outcomes` lacks home/away labels (merged from foundation `games.json` on `game_id`) and R1 states key games as float `as_of_game_id` (normalized to nullable `Int64` `game_id` for the head's key matching).
- Repairs were pre-flighted read-only (head fit + per-fold join coverage 85.9–86.7% of completed games; unmatched are FCS-involved) before each bound run; the failed run prefixes stayed empty, preserving immutability.
- R2 result interpretation: the four `continuity_ridge_alpha_*` variants span only 0.15% primary MAE, so the lift is mostly the continuity structure, not strong context coefficients; the simpler tie rule selected `alpha_0_1`. All evidence is reconstructed and activation-ineligible.

## Work Completed

- Froze production Week 1 (`2026w1-b2c739321e5d`; pipeline run `a8c031f028284dd59d21cd8647a9848f`; verified via health endpoint and `prediction_runs`).
- Repaired and executed the R2 tournament (11 candidates, folds 2018/2019/2022/2023/2024) with `--allow-reconstructed-context` from the certified R1 foundation plus the admitted context pair.
- Wrote the cross-report decision memo and updated the contract, roadmap, plans index, and AGENTS.md status.

## Files Modified

- `scripts/pipeline/build_r2_prior_tournament.py` — the two lineage repairs (committed by user as `278120a`, `4c6e610`).
- `docs/research/2026-09-04-early-week-context-cross-report.md` — new cross-report decision memo.
- `docs/plans/2026-09-02/early-week-strength-prior-research.md` — R2 amendment, DoD checks, status → Implemented.
- `docs/plans/index.md` — contract status updated.
- `docs/planning/roadmap.md` — R2 outcome recorded; R3 next.
- `AGENTS.md` — ratings-research status bullet refreshed.

## Validation

- [x] Freeze verified: health endpoint `state: frozen`; DB `frozen_at = 2026-09-04 15:22:59 UTC`.
- [x] R2 gates: `all_checks_passed: true`; selection report SHA `d617f576d656e90ea1f2a94bd6ea167304fbf7c8c454b5f1dade1b68e28e0ca1`.
- [x] `uv run ruff check` / `ruff format --check` on the repaired script.
- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check` — run immediately before the user commit.

## Amendments and Blockers

- R2 run emitted non-fatal NumPy warnings (divide-by-zero/overflow/invalid in head matmul) — recorded as follow-up (a) in the memo; investigate before R3.
- No production, V4, Neon, or publication state was altered by research work.

## Handoff Notes

- **Resume at:** User commits docs + session log; then Tuesday close-week for Week 1.
- **Watch out for:** Do not consume any reconstructed report in strict/locked/refit/publication flows; keep R3 Preview-isolated; Week 2 needs `prepare-week` in Preview first.

**tags:** ["ops", "production", "freeze", "ratings", "research", "r2"]
