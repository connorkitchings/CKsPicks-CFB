# Session: Phase 3 v2 Sealed Score-Model Tournament

## TL;DR

- **Worked On:** Implemented the isolated linear-versus-NB2 team-score
  tournament and its Preview-only artifact CLI.
- **Outcome:** Local implementation and repository validation pass. No R2
  parents were read and no Preview artifacts were written because the contract
  requires a user-controlled commit before outcome joins or external writes.
- **Plan Contract:** `docs/plans/2026-08-25/phase3-score-model-tournament-v2.md`
- **Approval / Status:** User explicitly authorized implementation; `In Progress`
  pending committed-code materialization and gates.
- **Blockers:** None; commit identity is an intentional required gate.
- **Next:** Commit the tracked implementation, then run the sealed Preview
  tournament with a new UTC cutoff/run ID. Record only diagnostics if either
  family fails selection or the winner fails locked 2025; otherwise rerun the
  same stamp byte-identically and close Phase 3.

## Context and Decisions

- Phase 3 v1 is immutable failed research, now marked `Superseded`; its
  historical report is not input to v2 tuning.
- v2 uses a shared pregame two-side score frame and selects one complete family
  for both derived targets. It preserves V4 as an unchanged, paired benchmark
  and preserves `source_kind` through evaluation.
- The 2026 output is explicitly a post-cutoff dry run. Any actual fields are
  cleared before prediction serialization, so it is not prospective evidence.

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

None. The commit-before-materialization gate is deliberate and not a blocker.

## Handoff Notes

- **Resume at:** Create the user-controlled commit, use its full SHA as
  `--expected-code-sha`, then run the v2 CLI against the exact certified
  Preview refs.
- **Watch out for:** Do not invoke production storage; do not alter the frozen
  equations, inputs, gates, or candidate rule after seeing tournament results;
  never treat the 2026 dry run as protected prospective evidence.

**tags:** ["ratings", "phase3", "nb2", "research", "preview"]
