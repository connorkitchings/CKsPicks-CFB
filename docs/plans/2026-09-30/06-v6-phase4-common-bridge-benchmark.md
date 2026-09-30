# Implementation Contract: V6 Ratings Lab Phase 4 — Multi-Factor Forecast Bridges & Historical Benchmark Tournament

- **Status:** Implemented
- **Date:** 2026-09-30
- **Authors:** Sol (Planning) / Terra (Implementation)
- **Scope:** Private research laboratory (`src/cks_picks_cfb/ratings_lab/`, `src/cks_picks_cfb/forecast/`)
- **Preceding Contracts:**
  - `docs/plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md` (Implemented)
  - `docs/plans/2026-09-30/02-v6-phase1-measurement-recipe.md` (Implemented)
  - `docs/plans/2026-09-30/03-v6-phase2-preseason-prior.md` (Implemented)
  - `docs/plans/2026-09-30/05-v6-phase3-kalman-reanchoring.md` (Implemented)

---

## 1. Goal & Architectural Role

Phase 4 completes the V6 Ratings Laboratory research lifecycle by connecting the Phase 1–3 multi-factor rating system to headline forecasting evaluation.

It delivers three capabilities:
1. **Multi-Factor Feature Frame Assembly:** Ingests the 4-factor pregame rating state stages (Rush SR, Rush Expl, Pass SR, Pass Expl) across home and away offensive and defensive units without mutating immutable V5 baselines.
2. **Dual Forecast Bridge Architectures (Tournament Competition):**
   - **Bridge A (`alpha10_direct18`):** Direct 16-feature Ridge regression (4 factors $\times$ 2 teams $\times$ 2 roles) + 2 venue indicators (`home_host`, `venue_unknown`).
   - **Bridge B (`alpha10_differentials`):** Domain-structured compact bridge using 4 net factor differentials $\Delta_k$ for Spread and 4 factor sums $\Sigma_k$ for Total + venue indicators.
3. **Historical Benchmark Tournament & Statistical Attribution:**
   - Evaluates across the sealed 2022–2025 headline test window (3,659 games, 7,318 paired prediction rows).
   - Computes 2,000 paired block-bootstrap replicates clustered by `(season, week)` against the accepted V5 baseline (`v5-common` / `v5_common_alpha10_v1`).
   - Generates scorecards reporting MAE, RMSE, Bias, Gaussian CRPS, and 90% interval coverage/width across pooled samples, individual seasons, and completed-game stages (0, 1, 2, 3, 4+).
   - Pre-registers a strict primary promotion endpoint.

---

## 2. Locked Specifications & Decisions

### A. Additive Fitter Extension (`forecast/heads.py`)
To allow multi-factor frames with 18 or 6 features while preserving 100% bit-identical V5 behavior:
- `_design(train, test, *, floor=1e-6, features: tuple[str, ...] = FEATURES)`: Add additive `features` parameter defaulting to `FEATURES`.
- `_fit_one(train, test, *, target: str, alpha=10.0, floor=1e-6, features: tuple[str, ...] = FEATURES)`: Add additive `features` parameter defaulting to `FEATURES`.
- Existing V5 calls without `features` are guaranteed unchanged. Existing unit tests prove non-regression.

### B. Evaluate CLI Multi-Stage Ingestion (`ratings_lab.py`)
- The `evaluate` CLI command accepts repeated `--stage-key` arguments (`nargs="+"`), taking four ratings stage keys (one per core 4-factor ID).
- For single-stage runs (e.g. `v5-common`, `frozen-v5`, or single-factor candidates), single `--stage-key` behavior is preserved.
- When 4 stage keys are provided, `evaluate` reads each stage manifest, verifies parentage against the corpus, identifies each stage's `measurement_id` from its config or explanation, and passes the 4 stages to `frame_with_multifactor_states()`.

### C. Multi-Factor Feature Frame Assembly (`ratings_lab/evaluation.py`)
In `frame_with_multifactor_states(corpus, stages_or_states)`:
- Identifies `measurement_id` either per-stage (from stage manifest/config) or from `state.explanation["measurement_id"]`.
- The duplicate validation checks `(season, game_id, team, role, measurement_id)`, eliminating false collisions across factors.
- Formats column names per factor:
  - `{side}_{role}__{mid}` (e.g. `home_offense__rush_success_rate`, `away_defense__pass_explosiveness`).
- Verifies that all 8,935 eligible games in `corpus.v5_features` receive complete 4-factor ratings. Fails closed on any missing value.
- Retains `frame_with_candidate_states()` for single-factor backwards compatibility.

### D. Dual Bridge Mathematics

#### 1. Bridge A: Direct 18-Feature Ridge (`alpha10_direct18`)
- **Features (18 total):**
  - Home Offense (4 factors): `home_offense__rush_success_rate`, `home_offense__rush_explosiveness`, `home_offense__pass_success_rate`, `home_offense__pass_explosiveness`
  - Home Defense (4 factors): `home_defense__rush_success_rate`, `home_defense__rush_explosiveness`, `home_defense__pass_success_rate`, `home_defense__pass_explosiveness`
  - Away Offense (4 factors): `away_offense__rush_success_rate`, `away_offense__rush_explosiveness`, `away_offense__pass_success_rate`, `away_offense__pass_explosiveness`
  - Away Defense (4 factors): `away_defense__rush_success_rate`, `away_defense__rush_explosiveness`, `away_defense__pass_success_rate`, `away_defense__pass_explosiveness`
  - Venue: `home_host`, `venue_unknown`
- **Fit:** Expanding Ridge regression with fixed $\alpha=10.0$ trained on strictly earlier seasons ($s < \text{validation}$).

#### 2. Bridge B: Domain Differentials & Sums (`alpha10_differentials`)
- **Spread Target (`margin`):**
  For each factor $k \in \{\text{rush\_sr}, \text{rush\_expl}, \text{pass\_sr}, \text{pass\_expl}\}$:
  $$\Delta_k = (\text{home\_off}_k - \text{away\_def}_k) - (\text{away\_off}_k - \text{home\_def}_k)$$
  Features: $\Delta_{\text{rush\_sr}}, \Delta_{\text{rush\_expl}}, \Delta_{\text{pass\_sr}}, \Delta_{\text{pass\_expl}}, \text{home\_host}, \text{venue\_unknown}$ (6 features).
- **Total Target (`total`):**
  For each factor $k \in \{\text{rush\_sr}, \text{rush\_expl}, \text{pass\_sr}, \text{pass\_expl}\}$:
  $$\Sigma_k = (\text{home\_off}_k + \text{away\_def}_k) + (\text{away\_off}_k + \text{home\_def}_k)$$
  Features: $\Sigma_{\text{rush\_sr}}, \Sigma_{\text{rush\_expl}}, \Sigma_{\text{pass\_sr}}, \Sigma_{\text{pass\_expl}}, \text{home\_host}, \text{venue\_unknown}$ (6 features).
- **Fit:** Expanding Ridge regression with fixed $\alpha=10.0$ on strictly earlier seasons.

### E. Same-Bridge Calibration Variance
- `_calibration_variance` is updated to fit using the candidate's exact feature set and bridge specification across historical rolling-origin folds.
- Guarantees Gaussian CRPS and 90% prediction intervals reflect candidate-specific residual distributions, preventing miscalibration from cross-bridge variance contamination.

### F. Pre-Registered Primary Promotion Gate & Expectations
- **Primary Endpoint:** **Pooled-Spread MAE gain lower-90% bootstrap bound $> 0.0$** against `v5-common` (statistically significant spread forecasting improvement across 2022–2025).
- **Secondary Endpoints (Diagnostic):**
  - Pooled Total MAE gain and CRPS.
  - Per-season and per-stage MAE.
- **Totals Pace Expectation:** As established in Phase 1 review, without a dedicated pace/tempo module, total forecasts are not expected to show significant gains over V5. A neutral or slightly trailing result on Totals is expected and does not invalidate rating quality.

---

## 3. Ordered Implementation Tasks

1. **Additive Fitter Parameters (`forecast/heads.py`):**
   - Add `features: tuple[str, ...] = FEATURES` to `_design()` and `_fit_one()`.
   - Verify all existing V5 tests pass unchanged.
2. **Multi-Factor State Frame Assembly (`ratings_lab/evaluation.py`):**
   - Implement `frame_with_multifactor_states()` with duplicate check on `(season, game_id, team, role, measurement_id)`.
   - Implement differential and sum feature engineering for Bridge B.
   - Update `_calibration_variance()` to compute residuals on candidate-specific feature subsets.
3. **Bridge Registry & Evaluation (`ratings_lab/evaluation.py`):**
   - Support `bridge="alpha10_direct18"` and `bridge="alpha10_differentials"` in `common_bridge_predictions()`.
4. **CLI Multi-Stage Evaluation (`scripts/research/ratings_lab.py`):**
   - Update `evaluate` argument parser to accept multiple `--stage-key` inputs (`nargs="+"`).
   - Wire multi-stage loading, frame assembly, dual bridge execution, and scorecard generation.
5. **Unit & Integration Test Suite (`tests/ratings_lab/test_evaluation.py`):**
   - Test additive `features` parameter in `_fit_one`.
   - Test `frame_with_multifactor_states()` dimension validation and collision prevention.
   - Test differential and sum math against known values.
   - Test candidate-specific `_calibration_variance` calculation.
6. **Documentation & Benchmarks (`docs/research/ratings-lab-v1.md`):**
   - Document Phase 4 bridge equations, multi-stage CLI commands, and promotion criteria.

---

## 4. Definition of Done & Quality Gates

- [x] All 43 existing ratings lab tests pass + new Phase 4 tests pass (`uv run pytest tests/ratings_lab/ -v`).
- [x] Additive `features=` in `forecast/heads.py` maintains bit-identical V5 test suite pass.
- [x] Multi-factor feature frame strictly matches the 8,935-game historical schedule with zero missing values.
- [x] Both bridges (`alpha10_direct18` and `alpha10_differentials`) generate 7,318 paired predictions matching `v5-common` keys.
- [x] Candidate-specific calibration variance generates non-zero Gaussian CRPS and 90% intervals.
- [x] Paired bootstrap scorecard against `v5-common` completes with 2,000 replicates.
- [x] `uv run ruff check` and `uv run ruff format --check` pass cleanly.
- [x] `uv run mkdocs build --quiet` exits with code 0.
- [x] `git diff --check` passes cleanly.
