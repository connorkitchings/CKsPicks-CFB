# V6 Ratings Architecture & Methodology Design

## Status & Lineage
- **Status:** Conceptual Design Document
- **Created:** 2026-09-30
- **Scope:** Private research architecture for V6 team ratings successor in `ratings_lab/`
- **Context:** Builds on the V5 conceptual foundation while transitioning from scalar PPP to a multi-factor, dynamic state-space rating system.

---

## 1. Core Architectural Pillars

| Pillar | V5 Approach | V6 Target Architecture | Rationale |
| :--- | :--- | :--- | :--- |
| **Unit Decomposition** | Separate Offense & Defense | **Separate Offense & Defense** | Preserves independent matchup granularity and enables accurate over/under totals modeling. |
| **State Representation** | Single scalar rating per unit (PPP efficiency) | **Multi-Factor Profile (4 Core Factors)** | Separates play type (Rush vs. Pass) and down-to-down consistency vs. big-play ability (Success Rate vs. Explosiveness). |
| **State Update** | Static Bayesian Normal Conjugate with fixed $k=8.0$ | **Exposure-Weighted Dynamic State Space (Kalman)** | Scales measurement variance inversely with exposure ($R_t = \sigma^2 / n_t$) while process drift ($Q$) prevents late-season rigidity. |
| **Opponent Adjustment** | Game-adjusted $z$-scores at cutoff | **Point-in-Time Retrospective Re-anchoring** | Re-evaluates earlier games using best current knowledge of opponents as of week $T$, eliminating stale early-season narratives without leaking future data. |
| **Forecast Bridge** | Expanding Ridge regression ($\alpha=10$) | **Decoupled Empirical Bridge (Ridge/Regression baseline)** | Isolates rating quality from bridge complexity. Simulation/pace engines deferred to a dedicated downstream track. |

---

## 2. Multi-Factor Metric Specification

### The Core 4-Factor Profile
Each team maintains an 8-dimensional state vector (4 offensive dimensions, 4 defensive dimensions):

$$\boldsymbol{\theta}_{\text{off}} = \begin{bmatrix} \text{Rush Success Rate} \\ \text{Rush Explosiveness} \\ \text{Pass Success Rate} \\ \text{Pass Explosiveness} \end{bmatrix}, \quad \boldsymbol{\theta}_{\text{def}} = \begin{bmatrix} \text{Def Rush Success Rate} \\ \text{Def Rush Explosiveness} \\ \text{Def Pass Success Rate} \\ \text{Def Pass Explosiveness} \end{bmatrix}$$

1. **Rush Success Rate:** Percentage of rushing plays that stay on schedule:
   - 1st Down: $\ge 50\%$ of needed yards.
   - 2nd Down: $\ge 70\%$ of needed yards.
   - 3rd & 4th Down: $100\%$ of needed yards (first down converted).
2. **Rush Explosiveness:** EPA or IsoPPP on successful run plays (measures chunk-play capability and big runs).
3. **Pass Success Rate:** Percentage of pass attempts staying on schedule / converting downs.
4. **Pass Explosiveness:** EPA or IsoPPP on successful pass completions (measures downfield passing and chunk gains).

### Additional Modular Factors Under Consideration
Beyond the core 4 factors, the multi-factor vector can be extended modularly:

1. **Havoc / Disruption Rate:**
   - **Defense:** Percentage of opponent plays resulting in a tackle for loss (TFL), sack, forced fumble, interception, or pass break-up (PBU).
   - **Offense (Havoc Allowed):** Susceptibility to defensive penetration and turnovers.
   - *Value:* Highly predictive of sudden momentum shifts and game-altering defensive scores.
2. **Finishing Drives (Points per Opportunity):**
   - Average points scored per drive that reaches the opponent 40-yard line.
   - *Value:* Separates "between-the-20s yards accumulation" from red zone finishing / bend-don't-break defense.
3. **Down & Distance Context (Standard Downs vs. Passing Downs):**
   - Standard downs (1st & 10, 2nd & 7 or less) vs. Passing downs (2nd & 8+, 3rd & 5+).
   - *Value:* Isolates true drop-back pass protection and third-down conversion capability from run-threat disguise.
4. **Pace & Tempo (Critical for Totals):**
   - Seconds per play and plays per game in non-garbage time.
   - *Value:* Teams range from ~20s/play (ultra-tempo) to 30+s/play (huddle/service academies). Independent tempo ratings dramatically improve game total precision.

---

## 3. Mathematical Update Engine: Dynamic State Space (Kalman + Exposure)

### Time Update (Prior Drift between Weeks)
Between games $t-1$ and $t$, team states drift slightly due to real-world evolution (player development, injuries, tactical adjustments):
$$\boldsymbol{\mu}_{t|t-1} = \boldsymbol{\mu}_{t-1}$$
$$\boldsymbol{\Sigma}_{t|t-1} = \boldsymbol{\Sigma}_{t-1} + \mathbf{Q}$$
where $\mathbf{Q} = \text{diag}(q_1, q_2, \dots, q_k)$ is the process noise matrix.

### Measurement Update (Exposure-Weighted Observation)
Let $\mathbf{y}_t$ be the observed multi-factor performance in game $t$, and $n_t$ be the exposure (number of plays or possessions):
$$\mathbf{R}_t = \frac{\boldsymbol{\Sigma}_{\text{noise}}}{n_t}$$
The Kalman Gain $\mathbf{K}_t$ weights the innovation based on exposure:
$$\mathbf{K}_t = \boldsymbol{\Sigma}_{t|t-1} (\boldsymbol{\Sigma}_{t|t-1} + \mathbf{R}_t)^{-1}$$
$$\boldsymbol{\mu}_t = \boldsymbol{\mu}_{t|t-1} + \mathbf{K}_t (\mathbf{y}_t - \hat{\mathbf{y}}_t)$$
$$\boldsymbol{\Sigma}_t = (\mathbf{I} - \mathbf{K}_t) \boldsymbol{\Sigma}_{t|t-1}$$

*Key Behavior:*
- **Sample size dominance:** When $n_t$ is large, $\mathbf{R}_t$ is small $\to$ the new game strongly informs the update. In low-play/rain games, $\mathbf{R}_t$ is large $\to$ beliefs move very little.
- **Continuous responsiveness:** $\mathbf{Q}$ prevents $\boldsymbol{\Sigma}_t$ from degenerating to 0 late in the season, allowing the model to adapt to true late-season trajectory changes.

---

## 4. Opponent Adjustment: Point-in-Time Retrospective Re-anchoring

### Concept
To avoid locking in naive early-season narratives (e.g., treating an early-September close win as impressive when the opponent later turns out to be 1–11), all games up to prediction cutoff $T$ are jointly evaluated.

### Execution Policy
1. Standing at cutoff week $T$, collect all games $1 \dots T$.
2. Re-anchor opponent adjustments across the connected schedule graph using the full sample of evidence known as of week $T$.
3. Compute the resulting team rating states $\boldsymbol{\theta}_T$.
4. Freeze $\boldsymbol{\theta}_T$ for week $T+1$ predictions.
5. Strict temporal isolation: zero information from after cutoff $T$ is used.

---

## 5. Forecast Bridge & Decoupling Strategy

1. **Initial Benchmark Bridge:** Expanding Ridge regression on strictly earlier seasons (2015–2019, 2021–current), mapping multi-factor differentials to Spread and multi-factor sums to Total.
2. **Independent Bridge Research (Track 2):**
   - Possession & tempo simulation.
   - Non-linear matchup interaction effects (e.g. extreme mismatch penalty).
   - Derivative pricing (1st half, alternate lines, win probabilities).

---

## 6. High-Level Modeling Invariants & Policy Decisions

1. **Garbage Time Filtering:**
   - Retain V5 play-eligibility filtering (`garbage == 0`), which removes blowout plays (Q3 lead $\ge 35$, Q4 lead $\ge 27$).
   - Hyperparameter exploration may evaluate tighter thresholds (e.g. Q2 lead $\ge 38$, Q4 lead $\ge 21$) in future iterations.
2. **FCS Games (Option B Anchor):**
   - Treat all non-FBS opponents as a single composite entity (`FCS_COMPOSITE`) with a fixed baseline prior (e.g. $\mu \approx -2.0\sigma$).
   - Update FBS team game counts and exposure, but cap the allowable rating delta from FCS games so blowouts do not distort FBS ratings.
3. **Turnover & Volatility Philosophy:**
   - Rather than ad-hoc stripping of turnovers, rely on down-by-down Success Rate and Explosiveness to naturally down-weight non-predictive turnover bounces (e.g. 50/50 fumble recoveries) while capturing true offensive/defensive down-to-down efficiency.
4. **Preseason Priors & Continuity:**
   - Replace pure scalar carryover decay ($\rho = 0.60$) with a multi-signal preseason prior combining:
     - Previous season terminal rating state
     - Returning production percentage (roster continuity)
     - Multi-year recruiting composite talent base
     - Head coaching / coordinator stability flags.
5. **EPA Model Dependency:**
   - Defer external or custom CFB-specific EPA modeling to a dedicated future project.
   - Core V6 factors will be calculated purely from deterministic down, distance, play type, and yards gained data.

---

## 7. Deterministic 4-Factor Measurement Recipes

All metrics are calculated on eligible non-garbage plays from the immutable play-by-play corpus:

### A. Success Definition
A play is successful ($S = 1$) if it meets standard down-and-distance thresholds:
- **1st Down:** Yards gained $\ge 0.50 \times \text{Yards to First}$ (or to Goal)
- **2nd Down:** Yards gained $\ge 0.70 \times \text{Yards to First}$ (or to Goal)
- **3rd & 4th Down:** Yards gained $\ge 1.00 \times \text{Yards to First}$ (or to Goal)

### B. The Four Factors
1. **Rush Success Rate:**
   $$\text{Rush SR} = \frac{\sum_{i \in \text{Rushes}} S_i}{N_{\text{rush}}}$$
2. **Rush Explosiveness (IsoPPP / Yards per Successful Rush):**
   $$\text{Rush Expl} = \frac{\sum_{i \in \text{Rushes}, S_i=1} \text{Yards}_i}{\sum_{i \in \text{Rushes}} S_i}$$
3. **Pass Success Rate:**
   $$\text{Pass SR} = \frac{\sum_{i \in \text{Passes}} S_i}{N_{\text{pass}}}$$
4. **Pass Explosiveness (Yards per Successful Pass):**
   $$\text{Pass Expl} = \frac{\sum_{i \in \text{Passes}, S_i=1} \text{Yards}_i}{\sum_{i \in \text{Passes}} S_i}$$

---

## 8. V6 Implementation Roadmap (Research Phases)

The execution in `ratings_lab/` follows four sequential phases:

```
[Phase 1: Deterministic 4-Factor Recipe]
  ├── Implement MeasurementRecipe for the 4 factors in measurements.py
  ├── Aggregate game-level observations from non-garbage play-by-play data
  └── Register recipe with version ID: v6_4factor_game_v1

[Phase 2: Preseason Continuity Prior Engine]
  ├── Ingest returning production, recruiting, and coaching stability context
  └── Blend with prior-season terminal ratings into initialized team priors

[Phase 3: Multi-Factor Exposure Kalman Engine & Re-anchoring]
  ├── Implement multivariate Exposure-Weighted Kalman Filter updater
  ├── Implement FCS Composite anchor (Option B)
  └── Implement retrospective schedule re-anchoring across weekly cutoffs T

[Phase 4: Common Bridge Historical Benchmark]
  ├── Evaluate across 2022-2025 headline test seasons under alpha-10 Ridge bridge
  ├── Benchmark paired bootstrap against V5 baseline (MAE, RMSE, CRPS)
  └── Document results and determine prospective eligibility
```

