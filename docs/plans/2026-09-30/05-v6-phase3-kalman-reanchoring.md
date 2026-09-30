# Implementation Contract: V6 Ratings Lab Phase 3 — Multi-Factor Exposure Kalman Engine & Retrospective Re-anchoring

- **Status:** Implemented
- **Date:** 2026-09-30
- **Authors:** Sol (Planning) / Terra (Implementation)
- **Scope:** Private research laboratory (`src/cks_picks_cfb/ratings_lab/`)
- **Preceding Contracts:**
  - `docs/plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md` (Implemented)
  - `docs/plans/2026-09-30/02-v6-phase1-measurement-recipe.md` (Implemented)
  - `docs/plans/2026-09-30/03-v6-phase2-preseason-prior.md` (Implemented)

---

## 1. Goal & Architectural Role

Phase 3 introduces dynamic state-space estimation and schedule graph re-anchoring to replace static Bayesian conjugate updates.

It delivers two major components:
1. **Exposure-Weighted Dynamic State Space (Kalman Filter):** 6 independent 1D filters (one per 4-factor ID) where measurement variance scales inversely with each factor's true play exposure ($R_t = \sigma^2 / n_t$), and process drift ($q$) maintains continuous tracking without late-season rigidity.
2. **FCS Composite Anchor & Retrospective Re-anchoring:**
   - Non-FBS opponents are pinned to `FCS_COMPOSITE` at $\text{Rating}(-2.0, 0.5)$ with a 25% exposure down-weight and a 1.5 innovation cap.
   - At weekly prediction cutoffs $T$, a batch re-filter re-evaluates games $1 \dots T$ using evidence available through week $T$ without forward data leakage.

---

## 2. Locked Specifications & Decisions

### A. State Space & Kalman Update (6× Independent 1D Filters)
Each team maintains independent 1D state filters for each of the six 4-factor measurement IDs across both roles ($\text{offense}, \text{defense}$):
- `rush_success_rate` (SR family)
- `pass_success_rate` (SR family)
- `rush_explosiveness` (Expl family)
- `pass_explosiveness` (Expl family)
- `rush_explosiveness_margin` (Expl family)
- `pass_explosiveness_margin` (Expl family)

#### 1. Time Update (Process Drift)
Drift $q$ accrues per game-step (byes incur no game update):
$$\mu_{t|t-1} = \mu_{t-1}$$
$$\sigma^2_{t|t-1} = \sigma^2_{t-1} + q$$

#### 2. Exposure & Measurement Noise
$n_t$ is strictly defined as the observation's own exposure for that measurement ID (attempts for SR, successes for Explosiveness and margins).
- For FBS vs. FBS games:
  $$R_t = \frac{\sigma^2_{\text{noise}}}{\max(n_t, 1)}$$
- For FBS vs. FCS games:
  $$n_{\text{eff}} = 0.25 \cdot n_t$$
  $$R_t = \frac{\sigma^2_{\text{noise}}}{\max(n_{\text{eff}}, 1)}$$

#### 3. Measurement Update & Innovation Capping
For observation $y_t$ (post-opponent-adjustment):
- Predicted observation: $\hat{y}_t = \mu_{t|t-1}$.
- Innovation: $\nu_t = y_t - \hat{y}_t$.
- **FCS Cap:** On FCS games, innovation is capped:
  $$\nu_t^* = \operatorname{clip}(\nu_t, -1.5, 1.5)$$
  On FBS games, $\nu_t^* = \nu_t$ (uncapped to preserve breakout signal).
- Kalman Gain:
  $$K_t = \frac{\sigma^2_{t|t-1}}{\sigma^2_{t|t-1} + R_t}, \quad K_t \in [0, 1]$$
- Posterior State:
  $$\mu_t = \mu_{t|t-1} + K_t \cdot \nu_t^*$$
  $$\sigma^2_t = \max((1 - K_t) \cdot \sigma^2_{t|t-1}, 10^{-6})$$

#### 4. Missing Observations
If $y_t$ is `None` or $n_t = 0$:
- Skip measurement update: $\mu_t = \mu_{t|t-1}$, $\sigma^2_t = \sigma^2_{t|t-1} = \sigma^2_{t-1} + q$.
- Never impute $y_t = 0$.

#### 5. Constants Table (Customizable via Candidate Configs)
| Family | Default Drift $q$ | Default Noise $\sigma^2_{\text{noise}}$ | Rationale |
| :--- | :--- | :--- | :--- |
| **SR (Success Rate)** | $0.02$ | $0.25$ | Bernoulli trial variance ($\approx p(1-p)$) |
| **Expl (Explosiveness & Margins)** | $0.05$ | $4.00$ | Continuous yardage chunk variance |

---

### B. FCS Composite Anchor (Option B)
- All non-FBS opponents are identified and mapped to `FCS_COMPOSITE`.
- Pinned Prior: $\text{Rating}(\mu = -2.0, \sigma^2 = 0.5)$ across all six IDs.
- `FCS_COMPOSITE` state is never updated from game outcomes (remains fixed anchor).
- Excluded from league center and scaling calculations.
- FBS opponents playing FCS receive both the 25% exposure down-weight in $R_t$ and the 1.5 innovation cap.

---

### C. Retrospective Schedule Re-anchoring
- **Cutoff $T$ Causality:** At cutoff week $T$, only games with kickoff + 6h $\le$ cutoff timestamp are eligible. Zero evidence from after cutoff $T$ is admitted.
- **Opponent Adjustment Operator:** Iterative 4-pass adjustment across the completed schedule graph $1 \dots T$:
  $$\text{adj\_val}_{i, t} = \text{raw\_val}_{i, t} - \text{opp\_def\_rating}_t + \text{league\_mean}$$
- **Early-Season Shrinkage:** For weeks $T \in \{1, 2\}$, shrink opponent adjustment toward preseason prior to prevent noise distortion in sparse graphs.
- **Batch Re-filter:** Standing at week $T$, the Kalman filter is re-run from the preseason prior over all completed games $1 \dots T$ with re-anchored opponent adjustments.
- **Frozen State $\boldsymbol{\theta}_T$:** Records means, variances, and usable exposures for all 6 IDs $\times$ 2 roles for all FBS teams to serve week $T+1$ predictions.

---

## 3. Ordered Implementation Tasks

1. **Kalman State-Space Engine (`ratings_lab/kalman.py`):**
   - Implement `KalmanExposureFilter` and `KalmanExposureDesign` conforming to `RatingDesign` protocol (`candidate_id`, `mode="incremental"`, `initialize`, `estimate`).
   - Implement $n_t$ per-factor exposure scaling, drift $q$, variance floor ($10^{-6}$), gain clip, and missing-observation pass-through.
2. **FCS Composite Anchor:**
   - Add FCS team mapping to `FCS_COMPOSITE`.
   - Implement fixed anchor state $\text{Rating}(-2.0, 0.5)$, 25% exposure down-weight, and 1.5 innovation cap.
3. **Retrospective Re-anchoring Operator (`ratings_lab/reanchoring.py`):**
   - Implement 4-pass schedule graph opponent adjustment for games $1 \dots T$.
   - Add early-season prior shrinkage for weeks 1–2.
   - Implement batch re-filter emitting frozen pregame states $\boldsymbol{\theta}_T$.
4. **Replay & YAML Candidate Integration:**
   - Register `KalmanExposureDesign` in candidate registry and updater factories.
   - Add candidate YAML configs in `conf/research/candidates/` for Kalman configurations.
5. **Test Suite & Validation:**
   - Unit tests in `tests/ratings_lab/test_kalman.py` verifying mathematical stability, $n_t$ scaling, $q$ drift, missing obs handling, FCS cap/down-weight, and re-anchoring causality.
   - Update `docs/research/ratings-lab-v1.md`.

---

## 4. Quality Gates

- `uv run pytest tests/ratings_lab/ -v`
- `uv run ruff check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py tests/ratings_lab/`
- `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py tests/ratings_lab/`
- `uv run mkdocs build --quiet`
- `git diff --check`
