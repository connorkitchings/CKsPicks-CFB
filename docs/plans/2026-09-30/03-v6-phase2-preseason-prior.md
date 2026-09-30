# Implementation Contract: V6 Ratings Lab Phase 2 — Preseason Continuity Prior Engine

- **Status:** Implemented
- **Date:** 2026-09-30
- **Authors:** Sol (Planning) / Terra (Implementation)
- **Scope:** Private research laboratory (`src/cks_picks_cfb/ratings_lab/`)
- **Preceding Contracts:**
  - `docs/plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md` (Implemented)
  - `docs/plans/2026-09-30/02-v6-phase1-measurement-recipe.md` (Implemented)

---

## 1. Goal & Architectural Role

Replace scalar $\rho = 0.60$ carryover with a multi-signal preseason prior engine across all six 4-factor IDs (`rush_success_rate`, `rush_explosiveness`, `pass_success_rate`, `pass_explosiveness`, `rush_explosiveness_margin`, `pass_explosiveness_margin`).

The engine blends:
1. Prior-season terminal rating (signed for defense, decayed by $\rho_f^g$)
2. Returning production percentage ($\beta_{\text{ret}} = 0.25$)
3. Multi-year recruiting composite ($\beta_{\text{rec}} = 0.20$)
4. Coaching stability flag ($\beta_{\text{coach}} = -0.15$ for new HC/coordinator)

This implementation delivers priors strictly within `ratings_lab/` without modifying production pipelines, V5 runners, replay chronology, or the fixed $\alpha=10$ forecast bridge.

---

## 2. Locked Specifications & Decisions

### A. Blend Formula
For team $T$, role $R \in \{\text{offense}, \text{defense}\}$, measurement ID $m$, and season $s$ with previous terminal season $p$ and gap $g = s - p$:

$$\text{prior\_mean} = \rho_f^g \cdot \text{terminal\_signed} + 0.25 \cdot \text{ret\_std} + 0.20 \cdot \text{rec\_std} - 0.15 \cdot \text{new\_coach\_flag}$$

$$\text{prior\_variance} = 1.0$$

- $\text{terminal\_signed}$: Standardized terminal rating from season $p$ for $(T, R, m)$, with defensive sign negated ($\text{value\_signed} = -\text{value}$ for $R = \text{"defense"}$). Higher is better for both units.
- $\text{ret\_std}$: Per-season standardized (mean 0, var 1) returning production percentage.
- $\text{rec\_std}$: Per-season standardized (mean 0, var 1) recruiting composite.
- $\text{new\_coach\_flag} \in \{0, 1\}$: 1 if HC or coordinator changed; 0 if staff is continuous (continuity contributes 0.0).
- Fallback: Missing terminal or missing continuity input falls back gracefully to neutral $\text{Rating}(0.0, 1.0)$ with explicit missing reason. Never propagate NaNs.

### B. Rho Typing & Key Resolution
- `rho: float | dict[str, float] = 0.60`
- If `float`: Broadcasts to all six measurement IDs.
- If `dict`: Keys may be family names (`{"SR", "Expl"}`) or exact measurement IDs.
  - Family mapping:
    - `rush_success_rate`, `pass_success_rate` $\to$ `SR`
    - `rush_explosiveness`, `pass_explosiveness`, `rush_explosiveness_margin`, `pass_explosiveness_margin` $\to$ `Expl`
  - Exact measurement ID keys take precedence over family keys if both are present.
  - Values must be finite and in $(0, 1]$, else raise `ValueError`.
  - Unknown keys raise `ValueError`.

### C. Six-ID Uniformity
All six 4-factor measurement IDs emit priors uniformly:
- No branching or special-case inheritance for margin IDs at bridge/replay time.
- Margin IDs share the Explosiveness family decay $\rho_{\text{Expl}}$.

### D. Single-Point Defensive Polarity
- Polarity is handled once during seed calculation and standardization:
  $\text{value\_signed} = -\text{value}$ for $R = \text{"defense"}$.
- Standardization centers and scales per $(s, R, m)$.
- The downstream bridge uses plain differentials $(\text{Off} - \text{Def})$ with zero additional sign adjustments.

### E. Temporal Integrity & Constraints
- All continuity inputs must have timestamps $\le$ kickoff of the first game of season $s$.
- 2020 is strictly excluded from all datasets and boundaries.
- The 2019 $\to$ 2021 gap uses $g = 2$, yielding $\rho_f^2$ carryover.
- Transfers and talent ratings remain excluded (admitted Preview lineage only).

---

## 3. Ordered Implementation Tasks

1. **Seed Standardization (`ratings_lab/priors.py`):**
   - Compute terminal seasonal states from observation history per $(s, R, m)$.
   - Apply defensive sign inversion: $-1 \times \text{value}$ for defense.
   - Standardize within $(s, R, m)$ to mean 0, variance 1.
2. **Continuity Ingestion (`ratings_lab/priors.py`):**
   - Ingest returning production, recruiting composite, and coaching changes via Preview-admitted data paths.
   - Standardize features per season.
   - Assert preseason timestamps $\le$ season kickoff; reject 2020.
3. **`PreseasonPrior` Engine (`ratings_lab/priors.py`):**
   - Implement `PreseasonPrior` class with validation on $\rho$ (broadcast float or family/ID dict).
   - Compute prior means and set unit variance `1.0`.
   - Provide structured `prior_index` or builder method returning `Rating(mean, variance=1.0)`.
4. **Replay Integration:**
   - Wire `PreseasonPrior` into `replay_ratings` via `fixed_priors` or `external_terminals`.
   - Verify gap-2 handling (2019 $\to$ 2021) and FCS neutral fallback.
5. **Test Suite & Documentation:**
   - Unit tests in `tests/ratings_lab/test_priors.py`.
   - Test $\rho$ broadcast vs dict, defensive sign inversion, missing input fallbacks, post-kickoff timestamp rejection, 2020 exclusion, gap-2 decay.
   - Update `docs/research/ratings-lab-v1.md`.

---

## 4. Quality Gates

- `uv run pytest tests/ratings_lab/ -v`
- `uv run ruff check src/cks_picks_cfb/ratings_lab/ tests/ratings_lab/`
- `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ tests/ratings_lab/`
- `uv run mkdocs build --quiet`
- `git diff --check`
