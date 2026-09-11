# Session: Phase 3 v2 Preflight Compact-Feature Repair

## TL;DR

- **Worked On:** Extended no-write Phase 3 v2 Preview preflight and corrected
  the compact builder's remaining legacy Python aggregation hotspot.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** User explicitly authorized Phase 3 execution on
  2026-09-10. Contract remains `In Progress`.
- **Outcome:** The prior no-write run progressed through cutoff admission and
  scalar history construction but was stopped in legacy candidate composite
  aggregation. The v2 compact builder now has a vectorized composite path that
  preserves legacy feature values and avoids changing the historical helper.
- **Blockers:** A new committed checkpoint is required before retrying the
  no-write preflight. No Preview evidence is accepted yet.
- **Next:** Commit this repair and retry the exact no-write preflight with the
  resulting SHA.

## Context and Decision

- The interrupted command did not include `--apply`; no R2, Neon, production,
  V4, or Phase 4–6 state changed.
- The active stack was `CompactTournamentFeatureBuilder.add_week()` calling the
  shared legacy `_game_features()` helper. Its candidate composite aggregation
  uses a Python uncertainty lambda for every candidate and weekly partition.
- Add a v2-local compact feature constructor. It uses the sealed candidate
  registry, component completeness rule, state-value mean, root-sum-square
  uncertainty divided by component count, and the same home/away offense/defense
  joins. The existing batch-equivalence test compares its retained compact rows
  with the unchanged legacy helper, preventing a semantic change.

## Files Modified

- `src/cks_picks_cfb/ratings/phase3_v2.py` - Vectorized candidate composite and
  game-feature construction used only by the compact v2 builder.
- `session_logs/2026-09-10/18-phase3-v2-preflight-compact-feature-repair.md` -
  execution record and retry handoff.

## Validation

- [x] `uv run pytest -q -W error tests/test_data_first_phase3_v2.py tests/test_data_lake.py` — 30 passed.
- [x] `uv run pytest -q -W error` — 833 passed, 2 skipped.
- [x] Ruff format check and lint for the changed Phase 3 files.
- [x] `git diff --check`.

## Handoff Notes

- **Resume at:** Commit the listed paths, then rerun the no-write preflight with
  the resulting full `git rev-parse HEAD` as `--expected-code-sha`.
- **Watch out for:** Do not apply until successful preflight output has been
  inspected and accepted; these interrupted attempts did not publish evidence.
- **Suggested commit:** `fix(research): vectorize phase3 compact features`

**tags:** ["phase3", "preview", "performance", "research", "lineage"]
