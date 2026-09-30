# Session: V6 Ratings Lab Phase 2 — Preseason Continuity Prior Engine

## TL;DR
- **Worked On:** V6 Ratings Lab Phase 2 implementation of the Preseason Continuity Prior Engine.
- **Outcome:** Generalized terminal standardization seeds with single-point defensive negation; ingested and standardized preseason continuity features (returning production, recruiting, coaching changes) with fail-closed 2020 rejection and post-kickoff timestamp enforcement; implemented `PreseasonPrior` supporting flexible $\rho$ (broadcast float or family/ID dict); integrated seamlessly into `replay()` via `fixed_priors` and neutral fallback keys; comprehensive unit tests covering all 5 tasks pass cleanly.
- **Plan Contract:** `docs/plans/2026-09-30/03-v6-phase2-preseason-prior.md`
- **Approval / Status:** Implemented
- **Blockers:** None
- **Next:** Phase 3: Multi-Factor Exposure Kalman Engine & Re-anchoring.

## Context and Decisions
- **Defensive Polarity:** Negation lives strictly at the standardization seed step (`value_signed = -value` for `defense`). Standardized ratings represent quality (higher = better unit) across both offense and defense, allowing plain differentials $(\text{Off} - \text{Def})$ at bridge time without ad-hoc sign flips.
- **Rho Typing:** Supports both broadcast `float` and `dict[str, float]`. Dictionaries accept family keys (`{"SR", "Expl"}`) or exact measurement IDs; exact IDs take precedence. Unknown keys or non-finite/out-of-bounds values are rejected fail-closed.
- **Prior Blend Formula:**
  $$\text{prior\_mean} = \rho_f^g \cdot \text{terminal\_signed} + 0.25 \cdot \text{ret\_std} + 0.20 \cdot \text{rec\_std} - 0.15 \cdot \text{new\_coach\_flag}$$
  $$\text{prior\_variance} = 1.0$$
- **Uniformity Across Six IDs:** All six 4-factor IDs (`rush_success_rate`, `rush_explosiveness`, `pass_success_rate`, `pass_explosiveness`, `rush_explosiveness_margin`, `pass_explosiveness_margin`) emit priors uniformly.
- **Fail-Closed Constraints:** Season 2020 is rejected across all inputs; preseason inputs timestamped after kickoff raise a `ValueError`; 2019 $\to$ 2021 gap uses $g = 2$ ($\rho_f^2$); missing terminals or teams fall back gracefully to neutral $\text{Rating}(0.0, 1.0)$ with explicit missing reasons.

## Work Completed
- **Task 1 (Seed Generalization):** Implemented `compute_terminal_seeds` in `src/cks_picks_cfb/ratings_lab/priors.py` and updated `terminal_standardized_seeds` in `measurements.py` to support multi-factor IDs and defensive negation.
- **Task 2 (Continuity Ingestion):** Implemented `ContinuityTable` with `from_dataframe()` supporting per-season standardization of returning production and recruiting, new coach flags, 2020 rejection, and post-kickoff timestamp validation.
- **Task 3 (`PreseasonPrior` Engine):** Implemented `PreseasonPrior` class with strict validation of $\rho$, formula blending, gap decay, and neutral fallbacks.
- **Task 4 (Replay Integration):** Wired into `replay()` via `build_fixed_priors()`, returning `(fixed_priors, neutral_fallback_keys)` with zero modifications required to `replay.py`.
- **Task 5 (Tests & Docs):** Added 11 new tests in `tests/ratings_lab/test_priors.py` (total 32 passing in suite); updated `docs/research/ratings-lab-v1.md`.
- **Review Dispositions:**
  1. *Legacy PPP Carryover Sign:* Pinned `signed_defense=(args.measurement_id != "raw_points_per_possession")` in `scripts/research/ratings_lab.py` so the legacy PPP carryover reference retains its exact pre-Phase-2 unsigned baseline.
  2. *Fail-Closed Kickoff Validation:* `ContinuityTable.from_dataframe()` now raises `ValueError` if `effective_at` timestamps exist without supplying `games` or `earliest_kickoffs` (eliminates vacuous pass).
  3. *Standard Deviation Convention:* Unified on population standard deviation (`ddof=0`) across both seed generation and continuity feature standardization.
  4. *Terminal-Only Prior Reason:* In non-neutral fallback mode (`fallback_to_neutral=False`), missing continuity now returns `reason="terminal_only"` to enable clean downstream attribution.

## Files Modified
- `src/cks_picks_cfb/ratings_lab/priors.py` - Created Preseason Continuity Prior Engine (`compute_terminal_seeds`, `ContinuityTable`, `PreseasonPrior`, `TeamContinuity`).
- `src/cks_picks_cfb/ratings_lab/measurements.py` - Delegated `terminal_standardized_seeds` to `compute_terminal_seeds` with defensive negation and `measurement_id` support.
- `src/cks_picks_cfb/ratings_lab/__init__.py` - Exported `PreseasonPrior`, `ContinuityTable`, `TeamContinuity`, and `compute_terminal_seeds`.
- `scripts/research/ratings_lab.py` - Pinned unsigned defense for legacy raw PPP carryover reference.
- `tests/ratings_lab/test_priors.py` - Created 11 unit and dry-run tests for Phase 2.
- `docs/plans/2026-09-30/03-v6-phase2-preseason-prior.md` - Plan contract created and marked `Implemented`.
- `docs/research/ratings-lab-v1.md` - Documented Phase 2 Preseason Continuity Prior Engine specifications.

## Validation
- [x] `uv run pytest tests/ratings_lab/ -v` (32/32 passed)
- [x] `uv run ruff check src/cks_picks_cfb/ratings_lab/ tests/ratings_lab/` (All checks passed)
- [x] `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ tests/ratings_lab/` (All formatted)
- [x] `uv run mkdocs build --quiet` (Clean exit code 0)
- [x] `git diff --check` (Clean exit code 0)

## Handoff Notes
- **Resume at:** Phase 3 planning contract: Multi-Factor Exposure Kalman Engine & Retrospective Re-anchoring.
- **Watch out for:** Research remains strictly isolated in `ratings_lab/`; production pipeline and V5 runners untouched.

**tags:** ["v6", "ratings_lab", "preseason_prior", "continuity", "4factor"]
