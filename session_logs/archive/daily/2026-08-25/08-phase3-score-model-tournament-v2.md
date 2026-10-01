# Session: Phase 3 v2 Sealed Score-Model Tournament

## TL;DR

- **Worked On:** Implemented the isolated linear-versus-NB2 team-score
  tournament and its Preview-only artifact CLI.
- **Outcome:** The committed sealed selection produced only an immutable
  diagnostic report; neither complete score family passed every frozen gate.
- **Plan Contract:** `docs/plans/2026-08-25/phase3-score-model-tournament-v2.md`
- **Approval / Status:** User explicitly authorized implementation; `In Progress`
  after the frozen historical gate failure.
- **Blockers:** Frozen historical gates failed; Phase 4 is blocked.
- **Next:** A future, separately approved Phase 3 candidate identity is
  required. Do not tune or retry v1/v2 after their outcome reports.

## Context and Decisions

- Phase 3 v1 is immutable failed research, now marked `Superseded`; its
  historical report is not input to v2 tuning.
- v2 uses a shared pregame two-side score frame and selects one complete family
  for both derived targets. It preserves V4 as an unchanged, paired benchmark
  and preserves `source_kind` through evaluation.
- The 2026 output would have been a post-cutoff dry run, with any actual fields
  cleared before serialization. No such output was published.

## Work Completed

- Added direct SciPy runtime dependency and locked it.
- Added the pinned `rating-score-v2` configuration.
- Added constrained symmetric linear and NB2 score fitting, covariance and
  interval derivation, sealed expanding selection, locked confirmation, and
  model-record serialization.
- Added the commit-identity-gated Preview-only materialization CLI. Failed
  selection/confirmation writes only the immutable tournament diagnostic.
- Added regression coverage for score algebra, covariance PSD, intervals,
  side symmetry, venue treatment, signs, NB2 fitting, fold isolation,
  deterministic selection/tie-break, locked-2025 confirmation, and Preview
  write boundaries.
- Created the v2 implementation contract and updated rating roadmap,
  requirements, and plan index authority.
- Committed the implementation as `a7c9cc5c8093b7d4db4399a7337e69f368cf1bf4`.
- The first materialization detected a mechanical defect: fitting checked
  frozen signs after optimization rather than constraining them. Added a
  regression test, committed bounded optimization as
  `ea0d3ac65261c72b5c0ee325c3b22ee2aab9a144`, and used a fresh run ID.
- The corrected sealed selection report is
  `artifacts/research/rating-successor/score-tournament-v2/9131f094dd90f2acc902fd8d0b972cd47c0e08263b769f425942b09d331331af/runs/2026-08-26T0322Z-phase3-score-v2/tournament.json`
  (SHA-256 `0e391d8c2d48b3252bd9a7b2e13c184a75ca2bd1457d0a9cded632339edb620c`).
  Linear failed total bias/standardized-residual mean; NB2 failed required
  margin and total uncertainty/calibration gates. No winner was selected, so
  locked 2025, final refit, dry run, model, prediction, and candidate writes
  did not occur.

## Files Modified

- `pyproject.toml`, `uv.lock` — direct SciPy runtime dependency.
- `conf/ratings/score_model_tournament_v2.yaml` — frozen v2 configuration and
  certified parent pins.
- `src/cks_picks_cfb/ratings/predictions.py` — shared score-frame state and
  outcome columns.
- `src/cks_picks_cfb/ratings/score_models.py` — sealed score-family logic.
- `scripts/pipeline/build_rating_score_tournament.py` — Preview materializer.
- `tests/ratings/test_score_models.py` — v2 regression coverage.
- `docs/plans/2026-08-25/*`, `docs/planning/roadmap.md`,
  `docs/modeling/rating_system_requirements.md`, `docs/plans/index.md` —
  authority closure and v2 handoff.

## Validation

- [x] Focused v2 score-model and prediction tests: 13 passed.
- [x] Complete ratings tests: 93 passed.
- [x] Full Python suite: 507 passed, 2 skipped.
- [x] Scoped Ruff format/check.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --strict`.
- [x] `git diff --check`.

## Amendments and Blockers

The bounded-fit correction was a mechanical contract remediation. It preserved
the frozen equations, inputs, thresholds, and selection rule.

## Handoff Notes

- **Resume at:** Return to Sol planning for a new candidate identity only if
  separately authorized.
- **Watch out for:** Do not invoke production storage; do not alter or retry
  v1/v2 after seeing their outcome reports; Phase 4 remains blocked and no
  2026 protected evidence was consumed.

**tags:** ["ratings", "phase3", "nb2", "research", "preview"]
