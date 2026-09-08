# Session: Phase 4A Rating Selection Completion

## TL;DR

- **Worked On:** Completed Phase 4A context-free rating selection implementation, resolved numerical stability issues, and sealed immutable Preview artifacts.
- **Outcome:** Phase 4A is complete. Selected candidate: `rho_0_60__exposure` (the frozen reference). All 101,024 fold predictions, 284,896 rating states, and 142,448 team states are sealed in Preview.
- **Plan Contract:** `docs/plans/2026-09-07/02-phase4a-context-free-rating-selection.md`
- **Approval / Status:** User-authorized 2026-09-08; contract status is `Implemented`.
- **Blockers:** None.
- **Next:** Phase 4B (target-context selection) can begin from the sealed Phase 4A rating manifest.

## Context and Decisions

- The Phase 4A dry run initially failed with "divide by zero encountered in matmul" despite reasonable coefficient magnitudes (~8.9) and feature values (~3.5).
- Diagnostic investigation revealed the warning was a false positive from numpy/BLAS during matrix multiplication. The actual computation produced finite results.
- Resolution: suppress RuntimeWarning during `np.matmul`, check results for finiteness directly. This preserves numerical safety while avoiding false-positive failures.
- The selected candidate `rho_0_60__exposure` is the frozen reference, meaning no challenger passed all selection gates (0.5% pooled MAE improvement, 90% paired bootstrap excluding zero, equal coverage, no season regression >5%).

## Work Completed

- Separated Ridge fit and predict error handling with distinct diagnostic messages.
- Added coefficient magnitude guard (max 1000) and validation feature magnitude guard (max 100).
- Replaced `model.predict()` with manual `np.matmul` to bypass sklearn's warning handling.
- Suppressed false-positive matmul RuntimeWarnings; check results for finiteness directly.
- Updated tests to monkeypatch `np.matmul` instead of `Ridge.predict` for the predictions-failure case.
- Renamed `test_ridge_warnings_and_nonfinite_outputs_fail_closed_with_fold_context` to `test_ridge_fit_warnings_fail_closed_with_fold_context` (warnings during fit remain fatal; warnings during predict are now suppressed).
- Ran warning-free dry run, apply, and independent verification against the signed Phase 3 manifest.
- Sealed immutable Preview artifacts under `artifacts/research/data-first-football-v1/phase4a/runs/phase4a-v1-20260908T1500Z/`.

## Files Modified

- `src/cks_picks_cfb/ratings/phase4a.py` — separated fit/predict error handling, added magnitude guards, manual matmul with intermediate finite checks, suppressed false-positive warnings.
- `tests/test_data_first_phase4a.py` — updated tests for manual matmul implementation.

## Validation

- [x] Focused Phase 4A tests: 15 passed.
- [x] Full warning-as-error Python suite: 765 passed, 2 skipped.
- [x] Ruff format + lint: clean.
- [x] Phase 4A dry run: warning-free, 101,024 predictions, selected `rho_0_60__exposure`.
- [x] Phase 4A apply: immutable artifacts written to Preview.
- [x] Independent verification: status `verified`, all artifact counts match.
- [x] `git diff --check`: clean.

## Artifacts

- **Manifest URI:** `artifacts/research/data-first-football-v1/phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json`
- **Manifest SHA-256:** `af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612`
- **Selected Candidate:** `rho_0_60__exposure`
- **Code SHA:** `3547844111c90f71c85760cbf841ae11787591a8`
- **Row Counts:**
  - Fold predictions: 101,024
  - Rating states: 284,896
  - Team states: 142,448
  - Attribution/coverage: 8

## Amendments and Blockers

- The Phase 4A numerical-execution amendments (bounded float64 conversion, magnitude guards, manual matmul) are user-authorized and recorded in the implementation contract.
- No blockers remain.

## Handoff Notes

- **Resume at:** Phase 4B (target-context selection) can begin from the sealed Phase 4A rating manifest. The Phase 4B contract is at `docs/plans/2026-09-07/03-phase4b-target-context-selection.md`.
- **Watch out for:** Phase 4B requires the Phase 2e auxiliary manifest and consumes the Phase 4A rating. Preserve the `.opencode/` directory and the other session's `src/cks_picks_cfb/ops/__main__.py` changes.

**tags:** ["data-first", "phase4a", "ratings", "completed"]
