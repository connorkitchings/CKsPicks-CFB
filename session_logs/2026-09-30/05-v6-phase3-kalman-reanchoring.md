# Session: V6 Ratings Lab Phase 3 — Multi-Factor Exposure Kalman Engine & Retrospective Re-anchoring

## TL;DR
- **Worked On:** Implemented Phase 3 of the V6 Ratings Laboratory: exposure-weighted 1D Kalman state filters, FCS composite anchor node, and retrospective schedule graph re-anchoring with early-season shrinkage and batch re-filtering.
- **Outcome:** Full contract implementation complete, tested (41/41 ratings lab tests passing), and verified with quality gates.
- **Plan Contract:** `docs/plans/2026-09-30/05-v6-phase3-kalman-reanchoring.md` (Status: `Implemented`)
- **Approval / Status:** Approved in Sol-to-Terra review, executed in Terra build mode.
- **Blockers:** None.
- **Next:** User git commit and Phase 4 planning/contract review (non-linear bridge & candidate tournament).

## Context and Decisions
- **Exposure-Weighted Kalman State Space:** 6 independent 1D filters (per 4-factor measurement ID) where measurement noise scales inversely with factor-specific play exposure ($R_t = \sigma^2 / \max(n_t, 1)$). FCS games receive strict 4x noise penalty ($R_t = \sigma^2 / (0.25 \cdot \max(n_t, 1))$) and an innovation cap $|\nu_t| \le 1.5$.
- **Process Drift & Missing Data:** State variance expands per game-step by $q$ ($\sigma^2_{t|t-1} = \sigma^2_{t-1} + q$). Bye weeks incur zero update (no drift, no step). Missing observations skip measurement updates while keeping expanded variance, avoiding zero-imputation.
- **FCS Composite Anchor:** All non-FBS opponents map to `FCS_COMPOSITE` with pinned prior $\text{Rating}(-2.0, 0.5)$, never updated from game outcomes, excluded from league center calculations.
- **Schedule Graph Opponent Adjustment:** 4-pass iterative schedule adjustment across completed games with cohort-specific league means (offense and defense), signed defensive quality, damped fixed-point iterations, and early-season shrinkage ($w_t = T / (T + k)$ for $T \in \{1, 2\}$, $w_t = 1.0$ for $T \ge 3$).
- **Drive-by Fix Verified:** Preserved legacy unsigned defense for raw PPP carryover reference in `scripts/research/ratings_lab.py` (`signed_defense=(args.measurement_id not in {"ppp", "raw_points_per_possession"})`).

## Work Completed
- Implemented `KalmanExposureFilter` and `KalmanExposureDesign` in `src/cks_picks_cfb/ratings_lab/kalman.py`.
- Implemented `filter_cutoff_games`, `reanchor_schedule_graph`, and `batch_refilter_states` in `src/cks_picks_cfb/ratings_lab/reanchoring.py`.
- Registered `kalman_exposure` updater factory in `src/cks_picks_cfb/ratings_lab/updaters.py` and exported symbols in `src/cks_picks_cfb/ratings_lab/__init__.py`.
- Added candidate config `conf/research/candidates/kalman_exposure_v1.yaml`.
- Created comprehensive test suite `tests/ratings_lab/test_kalman.py` (9 tests covering exposure scaling, noise weighting, FCS capping, pinned FCS node, causality filtering, 4-pass schedule adjustment & shrinkage, batch re-filtering, replay integration, and YAML candidate parsing).
- Updated documentation in `docs/research/ratings-lab-v1.md` and contract status in `docs/plans/2026-09-30/05-v6-phase3-kalman-reanchoring.md`.

## Files Modified
- `src/cks_picks_cfb/ratings_lab/kalman.py` - New: Exposure-weighted Kalman filter & FCS composite node
- `src/cks_picks_cfb/ratings_lab/reanchoring.py` - New: Schedule graph re-anchoring, early-season shrinkage, batch re-filtering
- `src/cks_picks_cfb/ratings_lab/updaters.py` - Added `kalman_exposure` parser to `load_candidate_configs`
- `src/cks_picks_cfb/ratings_lab/__init__.py` - Exported Kalman and re-anchoring classes and helpers
- `conf/research/candidates/kalman_exposure_v1.yaml` - New: YAML candidate config for Kalman exposure model
- `tests/ratings_lab/test_kalman.py` - New: Test suite for Kalman filter, FCS anchor, and schedule re-anchoring
- `scripts/research/ratings_lab.py` - Drive-by fix: signed defense preserved for 4-factors, unsigned for PPP
- `docs/plans/2026-09-30/05-v6-phase3-kalman-reanchoring.md` - Marked status as `Implemented`
- `docs/research/ratings-lab-v1.md` - Added Phase 3 architecture and mathematical specifications

## Validation
- [x] `uv run pytest tests/ratings_lab/ -v` (41/41 passed in 1.26s)
- [x] `uv run ruff check src/cks_picks_cfb/ratings_lab/ tests/ratings_lab/` (Clean, 0 errors)
- [x] `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ tests/ratings_lab/` (All 18 files formatted)
- [x] `uv run mkdocs build --quiet` (Clean, exit code 0)
- [x] `git diff --check` (No whitespace or patch errors)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** User executes manual git commit for Phase 3; then initiate Phase 4 planning.
- **Watch out for:** Research code remains completely isolated to `ratings_lab/`; zero changes to production or Neon DB.

**tags:** ["research", "ratings_lab", "v6", "kalman", "reanchoring", "fcs_anchor"]
