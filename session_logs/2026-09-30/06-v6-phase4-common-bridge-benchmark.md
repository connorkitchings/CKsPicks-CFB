# Session: V6 Ratings Lab Phase 4 — Multi-Factor Forecast Bridges & Historical Benchmark Tournament

## TL;DR
- **Worked On:** Implemented Phase 4 of the V6 Ratings Laboratory: additive fitter feature extension, multi-factor state frame assembly, dual forecast bridge architectures (`alpha10_direct18` and `alpha10_differentials`), candidate-specific calibration variance, multi-stage CLI ingestion, and comprehensive unit tests.
- **Outcome:** Phase 4 implementation complete, 49/49 ratings lab tests passing, 24/24 V5 forecast tests passing, documentation updated.
- **Plan Contract:** `docs/plans/2026-09-30/06-v6-phase4-common-bridge-benchmark.md` (Status: `Implemented`)
- **Approval / Status:** Plan approved with typo correction (§D.1 away defense features list) and fully implemented.
- **Blockers:** None.
- **Next:** Proceed with benchmark candidate replay across the 4 core factor stages and run the headline paired evaluation against V5.

## Context and Decisions
- **Fitter Extension:** Added `features: tuple[str, ...] = FEATURES` parameter to `_design()` and `_fit_one()` in `src/cks_picks_cfb/forecast/heads.py`. Preserves bit-identical V5 test suite passing while supporting 18- and 6-feature frames.
- **Dual Bridges:**
  - `alpha10_direct18`: 16 direct rating features (4 factors $\times$ 2 teams $\times$ 2 roles) + 2 venue indicators.
  - `alpha10_differentials`: 4 net factor differentials $\Delta_k$ for Spread (margin) and 4 factor sums $\Sigma_k$ for Total + 2 venue indicators (6 features each).
- **Candidate-Specific Calibration Variance:** Evaluates rolling residuals on candidate-specific active features on strictly earlier validation seasons, ensuring Gaussian CRPS and 90% prediction intervals match the candidate's residual distribution.
- **CLI Multi-Stage Ingestion:** Updated `evaluate` parser in `scripts/research/ratings_lab.py` to support `nargs="+"` for `--stage-key`, enabling simultaneous ingestion of all 4 core factor rating stages.

## Work Completed
- Corrected typo in §D.1 away defense list in `docs/plans/2026-09-30/06-v6-phase4-common-bridge-benchmark.md`.
- Implemented additive `features=` parameter in `_design()` and `_fit_one()` in `src/cks_picks_cfb/forecast/heads.py`.
- Implemented `FOUR_FACTOR_CORE_IDS`, `DIRECT18_FEATURES`, `DIFFERENTIAL_SPREAD_FEATURES`, `DIFFERENTIAL_TOTAL_FEATURES`, `frame_with_multifactor_states()`, and updated `_calibration_variance()` and `common_bridge_predictions()` in `src/cks_picks_cfb/ratings_lab/evaluation.py`.
- Exported new constants and functions in `src/cks_picks_cfb/ratings_lab/__init__.py`.
- Updated `scripts/research/ratings_lab.py` for multi-stage `--stage-key` inputs and dual bridge evaluation.
- Added comprehensive unit and integration tests in `tests/ratings_lab/test_evaluation.py`.
- Updated `docs/research/ratings-lab-v1.md` with Phase 4 documentation.
- Updated status to `Implemented` in `docs/plans/2026-09-30/06-v6-phase4-common-bridge-benchmark.md`.

## Files Modified
- `src/cks_picks_cfb/forecast/heads.py` - Additive `features=` parameter in `_design()` and `_fit_one()`
- `src/cks_picks_cfb/ratings_lab/evaluation.py` - Multi-factor state frame assembly, dual bridges, candidate-specific calibration variance
- `src/cks_picks_cfb/ratings_lab/__init__.py` - Export Phase 4 symbols
- `scripts/research/ratings_lab.py` - Multi-stage CLI evaluate argument parsing and execution
- `tests/ratings_lab/test_evaluation.py` - Unit and integration tests for Phase 4
- `docs/research/ratings-lab-v1.md` - Phase 4 architecture, bridge formulas, and promotion criteria
- `docs/plans/2026-09-30/06-v6-phase4-common-bridge-benchmark.md` - Phase 4 implementation contract (Status: Implemented)
- `session_logs/2026-09-30/06-v6-phase4-common-bridge-benchmark.md` - Phase 4 session log

## Validation
- [x] `uv run pytest tests/ratings_lab/ -v` (49/49 passed)
- [x] `uv run pytest tests/test_data_first_forecasts.py -v` (24/24 passed)
- [x] `uv run ruff check` (passed cleanly)
- [x] `uv run ruff format --check` (passed cleanly)
- [x] `uv run mkdocs build --quiet` (Clean, exit code 0)
- [x] `git diff --check` (No whitespace or patch errors)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Benchmark candidate replay across the 4 core factor stages using `scripts/research/ratings_lab.py evaluate --stage-key <sr_rush> <expl_rush> <sr_pass> <expl_pass> --bridge alpha10_direct18` and `--bridge alpha10_differentials`.
- **Watch out for:** Ensure all 4 factor rating stages have matching candidate names and complete schedule coverage.

**tags:** ["research", "ratings_lab", "v6", "phase4", "forecast_bridge", "tournament"]
