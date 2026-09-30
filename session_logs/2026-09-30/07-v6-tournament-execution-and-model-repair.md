# Session: V6 Tournament Execution, Polarity Audit, and Three-Fix Model Repair

## TL;DR
- **Worked On:** Executed the complete V6 Ratings Laboratory tournament pipeline (`kalman_exposure_v1`), performed root-cause polarity and prior audit against the `v5-common` baseline (7,318 paired predictions over 2022–2025), and designed and implemented the approved 3-fix repair plan.
- **Outcome:** 
  - **Fix 1 (Single-Point Quality-Space Signing & Corrected Differential Formula):** Negated defensive columns into quality space at multi-factor feature assembly; corrected Bridge B total formula $\Sigma_k = (h_{\text{off}} - a_{\text{def}}) + (a_{\text{off}} - h_{\text{def}})$. Bridge B Margin MAE improved by +0.6570 immediately.
  - **Fix 2 (Observation-Unit Priors & Re-anchoring + Bug Fix):** Scaled preseason priors into observation space ($\mu_0 = m_c \pm s_c \cdot z_{\text{blend}}$, $\sigma_0^2 = s_c^2$) and updated iterative schedule re-anchoring to adjust observations natively. Fixed critical bug in `PreseasonPrior.build_fixed_priors` where `"terminal_only"` was treated as neutral fallback, ensuring terminal seeds are applied. Bridge A Margin MAE dropped from 15.0032 to 14.7238 (+0.2794 gain); Bridge B dropped from 15.8249 to 14.8474 (+0.9775 gain).
  - **Fix 3 (Continuity Table Sourcing):** Ingested the 1,448-record admitted continuity dataset (`early-week-context-20260904-786580ec-r2`) covering returning production, recruiting, and coaching. Bridge A Margin MAE reached **14.6343** (total MAE **13.5993**, beating V5's 13.6623 by +0.0630). Bridge B Margin MAE reached **14.7892** (total MAE **13.6085**, beating V5 by +0.0538).
  - **Tournament Adjudication:** Primary spread gate (`margin_lower_90 > 0.0`) remains negative for both bridges (Bridge A: `margin_lower_90 = -0.6326`, `margin_upper_90 = +0.0265`; Bridge B: `margin_lower_90 = -0.8084`), so candidate is formally `RETAINED_AS_BENCHMARK`. However, the 3 fixes closed **~54% of Bridge A's spread gap and ~79% of Bridge B's spread gap** while **outperforming V5 on Totals**.
- **Plan Contract:** V6 Ratings Laboratory Protocol (`conf/research/ratings_lab_v1/protocol.yaml`)
- **Approval / Status:** Authorized execution; all 76 unit tests pass; all stages persisted cleanly to local research storage.
- **Blockers:** None.
- **Next:** Investigate hyperparameter optimization of Kalman process drift ($q$) and observation noise ($\sigma^2$) across the 4 factors, or evaluate non-linear/ridge weighting on the observation space.

## Performance Progression

| Model State | Bridge A Margin MAE | Bridge A Lower 90% | Bridge A Total MAE | Bridge B Margin MAE | Bridge B Lower 90% | Bridge B Total MAE |
|---|---|---|---|---|---|---|
| Initial Dry-Run / First Apply | 15.0032 | -1.1443 | 13.8136 | 16.4819 | -2.5411 | 13.8584 |
| + Fix 1 (Defensive Signing) | 15.0032 | -1.1443 | 13.8136 | 15.8249 | -2.0411 | 13.8584 |
| + Fix 2 (Obs-Unit Priors + Bugfix) | 14.7238 | -0.7183 | 13.5963 (+0.066) | 14.8474 | -0.8551 | 13.6128 (+0.049) |
| + Fix 3 (Admitted Continuity Table) | **14.6343** | **-0.6326** | **13.5993** (+0.063) | **14.7892** | **-0.8084** | **13.6085** (+0.054) |
| *v5-common reference* | 14.3197 | 0.0000 | 13.6623 | 14.3197 | 0.0000 | 13.6623 |

## Files Modified
- `src/cks_picks_cfb/ratings_lab/artifacts.py`: Added local-output storage fallback with fail-closed `./data/` guard and credential mapping.
- `src/cks_picks_cfb/ratings_lab/measurements.py`: Aliased `yards_to_first` to `distance` for R2 play-by-play schema compatibility.
- `src/cks_picks_cfb/ratings_lab/evaluation.py`: Negated defensive factor states into quality space at frame assembly; updated Bridge B total sum formula.
- `src/cks_picks_cfb/ratings_lab/priors.py`: Implemented `compute_cohort_stats()`, observation-unit prior mapping, and fixed `build_fixed_priors` neutral fallback exclusion.
- `src/cks_picks_cfb/ratings_lab/reanchoring.py`: Added observation-space detection and schedule re-anchoring; set pinned FCS composite to $\text{mean} \mp 2\sigma$.
- `scripts/research/run_v6_tournament.py`: Standalone tournament runner supporting dry-run and apply, multi-factor loop, continuity lake loading, and dual bridge evaluation.
- `tests/ratings_lab/test_priors.py`: Added unit tests for observation-unit prior mapping and cohort statistics.
- `tests/ratings_lab/test_evaluation.py`: Verified multi-factor frame column layout and quality-space defensive polarity.
- `tests/ratings_lab/test_tournament_runner.py`: Verified standalone runner orchestration in dry-run mode.

## Validation
- [x] Scoped unit tests: `uv run pytest tests/ratings_lab/ tests/test_data_first_forecasts.py` (76/76 passed in 4.37s)
- [x] Linter: `uv run ruff check src/ scripts/ tests/` (All checks passed)
- [x] Worktree diff check: `git diff --check` (0 issues)
- [x] Immutable storage safety: No files written to `./data/` in repo root; all outputs isolated in `$HOME/cfb_ratings_lab_v6/output`.

## Handoff Notes
- **Resume at:** User may review the tournament comparison scorecard at `ratings-lab/v1/runs/311e3800c3bf7d85fac8172b/comparison.json`.
- **Git operations:** User executes manual git commit for the changes.

**tags:** ["ratings-lab", "v6", "kalman", "tournament", "priors", "continuity"]
