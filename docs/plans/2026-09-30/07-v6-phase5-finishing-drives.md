# Implementation Contract: V6 Phase 5 Finishing Drives Factor Expansion

- **Status:** Implemented (V6 closed `RETAINED_AS_BENCHMARK`, 2026-09-30)
- **Contract Path:** `docs/plans/2026-09-30/07-v6-phase5-finishing-drives.md`
- **Context:** Empirical diagnostic confirmed that the residual spread deficit (-0.31 overall) is heavily concentrated in close games (<= 7 pts, -0.62 MAE deficit) where red-zone points-conversion efficiency decides outcomes. Blowouts (> 17 pts) and mature stages (Stage 4+) are already at parity with V5 (-0.08 and -0.07).
- **Objective:** Extend the modular state-space Kalman architecture to 5 factors by ingesting Finishing Drives (`finish_points_per_opp`), then re-adjudicate the frozen promotion gate.

---

## 1. Mathematical & Architectural Specification

### 1.1 Factor Definition & Scaffolding
- **Measurement ID:** `finish_points_per_opp` (single ID across both roles; role ∈ `{"offense", "defense"}`).
- **Scoring Opportunity Definition:** Any offensive drive reaching the opponent 40-yard line (`start_yards_to_goal <= 40` or any play within drive reaching `yards_to_goal <= 40`).
  - **Grain:** Exactly one opportunity per qualifying drive (drive-level deduplication).
  - **Filter Invariants:** Regulation quarters only (Q1–Q4; overtime excluded); 2020 season excluded; inherited garbage-time, non-offensive scoring, and special-teams exclusions apply per Phase 1 standards.
- **Points Attribution:** Net offensive points scored on the qualifying drive:
  - Touchdown = 7 (standardizes away extra point and two-point conversion variance).
  - Field Goal = 3.
  - Turnover, turnover on downs, missed field goal, blocked field goal = 0.
  - Safety conceded = 0 (counted as failed opportunity).
- **Exposure:** Opportunity count $n_t$ (integer count of qualifying drives in game).
  - If $n_t = 0$: `exposure = 0`, value = NaN/None, `missing_reason = "zero_opportunities"`. Kalman measurement update is skipped cleanly; variance expands via process drift $v_{t|t-1} = v_{t-1} + q$.
- **Polarity:**
  - Observation / filter space: tracks raw points allowed/scored ($y \in [0.0, 7.0]$).
  - Frame assembly: `{side}_defense__finish_points_per_opp` is negated into quality space ($y_{\text{quality}} = -y_{\text{allowed}}$), matching all existing defensive columns.

### 1.2 Pre-Registered Constants & Architecture Mapping
- **Recipe ID:** `v6_5factor_game_v1` (additive; `v6_4factor_game_v1` remains registered and untouched for backward compatibility). Emits the 6 Phase 1 IDs plus `finish_points_per_opp` across offense and defense.
- **Family Map:** Register `finish_points_per_opp` under a dedicated `Finish` family key in `FAMILY_MAP` in both `kalman.py` and `priors.py`.
- **Pre-Registered Constants (Fixed, No Test-Window Tuning):**
  - Prior inter-season persistence: $\rho_{\text{Finish}} = 0.55$.
  - Weekly process drift: $q_{\text{Finish}} = 0.03$.
  - Observation noise variance: $\sigma^2_{\text{Finish}} = 1.00$.
  - *Sanity-check instruction:* Terra reports the empirical cohort variance $s_c^2$ alongside and flags if $> 2\times$ divergent from 1.00, but does not tune the pre-registered parameter.
- **FCS Opponent Handling:** Inherits 25% exposure weighting (`fcs_exposure_weight = 0.25`), 1.5 innovation capping (`fcs_innovation_cap = 1.5`), and pinned composite rating at $\text{mean} \mp 2\sigma$.
- **Preseason Prior:** Ingests continuity table (returning production, recruiting, coaching changes) using identical $\beta$ coefficients. Observation-unit priors parameterize as $\mu_0 = m_c \pm s_c \cdot z_{\text{blend}}$, $\sigma_0^2 = s_c^2$.

### 1.3 Bridge Models & Features
- **Core Factor IDs (5):** `rush_success_rate`, `pass_success_rate`, `rush_explosiveness`, `pass_explosiveness`, `finish_points_per_opp`.
- **Bridge A (`alpha10_direct22`):** Direct Ridge regression on 22 features:
  - 20 factor rating states ($5 \text{ factors} \times 2 \text{ roles} \times 2 \text{ teams (home/away)}$).
  - 2 venue indicators (`is_neutral`, `home_field_advantage`).
  - Fixed $\alpha = 10.0$.
- **Bridge B (`alpha10_differentials`):** Domain differentials and sums with 7 features per target (5 factor terms + 2 venue terms):
  - **Spread:** $\Delta_k = (h_{\text{off}} - a_{\text{def}}) - (a_{\text{off}} - h_{\text{def}})$ across all 5 factors + venue.
  - **Totals:** $\Sigma_k = (h_{\text{off}} - a_{\text{def}}) + (a_{\text{off}} - h_{\text{def}})$ across all 5 factors + venue (using the corrected quality-space minus-defense formulation).
  - Fixed $\alpha = 10.0$.

### 1.4 Frozen Evaluation Protocol & Promotion Gate
- **Population:** Exact same 7,318 paired prediction rows (3,659 games across expanding temporal folds 2022–2025).
- **Bootstrap:** 2,000 block-bootstrap resamples with locked seed `20260928`.
- **Promotion Gate:** $\text{margin\_lower\_90} > 0.0$ against `v5-common`.
  - Gate remains strictly frozen; no post-hoc promotion on Totals.

---

## 2. Implementation Tasks (Terra Work Order)

1. **Measurement Recipe (`v6_5factor_game_v1`):**
   - In `src/cks_picks_cfb/ratings_lab/measurements.py`:
     - Add `v6_5factor_game_v1` recipe.
     - Implement drive opportunity detection (drives with play `yards_to_goal <= 40` or start $\le 40$).
     - Calculate net drive points (TD=7, FG=3, Turn/Downs/Missed FG/Safety=0).
     - Emit `Observation` records with `measurement_id="finish_points_per_opp"`, `role="offense"` and `"defense"`, `exposure=opportunity_count`.
     - Unit tests in `tests/ratings_lab/test_measurements.py`: verify opportunity counting, zero-opportunity missingness, goal-line edge cases, and that existing 6 IDs are bit-identical.

2. **Family Mapping & Constants:**
   - In `src/cks_picks_cfb/ratings_lab/kalman.py` & `priors.py`:
     - Add `finish_points_per_opp` $\to$ `"Finish"` in `FAMILY_MAP`.
     - Register `DEFAULT_Q_BY_FAMILY["Finish"] = 0.03`, `DEFAULT_SIGMA2_BY_FAMILY["Finish"] = 1.00`, and default $\rho_{\text{Finish}} = 0.55$.
     - Update `conf/research/candidates/kalman_exposure_v1.yaml` with family `Finish: q=0.03, sigma2=1.00`.

3. **Evaluation Frame & Bridge Extensions:**
   - In `src/cks_picks_cfb/ratings_lab/evaluation.py`:
     - Extend `FIVE_FACTOR_CORE_IDS = (*FOUR_FACTOR_CORE_IDS, "finish_points_per_opp")`.
     - Update feature assembly to 22 direct columns and 5 differentials/sums.
     - Ensure `defense__finish_points_per_opp` is negated into quality space.

4. **Tournament Execution & Adjudication:**
   - Run `scripts/research/run_v6_tournament.py` with `v6_5factor_game_v1`.
   - Report empirical cohort variance $s_c^2$ for Finishing Drives vs 1.00.
   - Run dual bridge evaluation (Bridge A direct-22 and Bridge B differentials-7) and 2,000 paired bootstraps.
   - Adjudicate promotion gate ($\text{margin\_lower\_90} > 0.0$).

---

## 3. Quality & Safety Gates

- [ ] Scoped unit tests: `uv run pytest tests/ratings_lab/ tests/test_data_first_forecasts.py` passes 100%.
- [ ] Recipe backward compatibility: `v6_4factor_game_v1` outputs remain bit-identical.
- [ ] Linter & Types: `uv run ruff check .` passes with zero errors.
- [ ] Clean Worktree: `git diff --check` passes with zero whitespace/formatting defects.
- [ ] Data Guardrails: Zero writes to repo `./data/`; durable research artifacts in `$HOME/cfb_ratings_lab_v6/output`.
