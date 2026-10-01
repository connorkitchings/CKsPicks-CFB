# Session: Phase 3 Structured Prediction Implementation

## TL;DR

- **Worked On:** Implemented the isolated Phase 3 OLS margin/total baseline,
  immutable artifact contracts, Preview-only CLI, and focused tests.
- **Outcome:** Local implementation and regression gates pass. Preview
  materialization remains intentionally blocked until this exact code and
  configuration are committed, as required by the Phase 3 contract.
- **Plan Contract:**
  `docs/plans/2026-08-25/phase3-structured-margin-total-baseline.md`
- **Approval / Status:** User authorized implementation on 2026-08-25; Phase
  3 remains `In Progress` pending immutable Preview evaluation.
- **Blockers:** Required pre-materialization commit.
- **Next:** Commit the listed Phase 3 files, then run the Preview CLI against
  only the certified parent refs and record the gate disposition.

## Work Completed

- Added the frozen `rating_prediction_baseline_v1` configuration, pinned to
  the passing foundation review, Phase 1 measurement snapshots, Phase 2
  pregame states, and recovered V4 benchmark identity.
- Added unregularized expanding OLS for direct margin and total predictions,
  deterministic pace fallback, Normal predictive uncertainty, intervals, and
  outcome-only paired V4 evaluation.
- Added a Preview-only, commit-identity-gated CLI. It rejects production,
  uncertified parents, incomplete state coverage, missing neutral-site
  status, non-passing historical gates, and writes no successful refs until
  the historical gates pass.
- Added focused tests for OLS signs/chronology/uncertainty, paired V4 source
  lineage, neutral-site rejection, and current-pregame pace/outcome handling.

## Validation

- [x] `uv run pytest tests/ratings/test_predictions.py -q` — 5 passed.
- [x] `uv run pytest tests/ratings -q` — 85 passed.
- [x] `uv run pytest -q` — 499 passed, 2 skipped.
- [x] Scoped Ruff format/check, contracts validation, contracts sync, strict
  MkDocs, and `git diff --check`.
- [ ] Preview materialization and byte-identical rerun — requires committed
  code/configuration before any outcome read or artifact write.

## Handoff Notes

- **Resume at:** Commit the new Phase 3 implementation, then invoke
  `scripts/pipeline/build_rating_predictions.py --environment preview` with
  the recovered certified games, outcomes, and V4 ref URIs.
- **Watch out for:** The CLI accepts only Phase 1 audit parent refs; do not
  substitute newer schedule/outcome data, register Neon metadata, inspect
  markets, modify V4, or start Phase 4.

**tags:** ["ratings", "phase3", "ols", "preview", "lineage"]
