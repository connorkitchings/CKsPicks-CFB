# Phase 4B: Target-Context Selection

> **Superseded 2026-09-08.** Same-game field-position, drive-length and turnover features invalidate pregame comparisons. The retained manifest is prohibited as a new forecasting parent.
> Use the approved [replacement contract](../2026-09-08/phase4b-pregame-context-selection-v2.md).
> Original implementation history below is preserved, not current authority.

- **Status:** Superseded
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** `session_logs/2026-09-08/03-phase4b-implementation-planning.md`, `session_logs/2026-09-08/04-phase4b-target-context-completion.md`
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.
- **Completed:** 2026-09-08. Selected `field_position` for margin, `no_context` for total. Manifest: `artifacts/research/data-first-football-v1/phase4b/runs/phase4b-v1-20260908T1600Z/retained-baseline-manifest.json`, SHA `dee8a668115af4f426d6080d8b139575ba35859fea9e7212cfd613b364779b4a`.

## Goal

Starting from the frozen Phase 4A rating, select at most one context family for
margin and at most one for total. Context remains outside the rating and is
evaluated through a frozen simple forecast bridge.

## Current State

This phase requires the signed Phase 4A rating, the signed Phase 3 retained
core, and the Phase 2e reconstructed-only manifest:

`artifacts/research/data-first-football-v1/phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json`

Its SHA-256 is
`d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad`. It is
research-only and activation-ineligible. Reconstructed market references are
excluded entirely.

## Parent Artifacts

Phase 4B requires three signed parents:

| Parent | URI | SHA-256 |
|---|---|---|
| Phase 4A retained rating | `phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json` | `af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612` |
| Phase 3 retained core | `phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json` | `c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234` |
| Phase 2e auxiliary eligibility | `phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json` | `d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad` |

## Context Families

### From Phase 3 context-only measurements (per-team-per-game, `adjustment_method="none"`)

| Family | Measurement IDs | Roles | Features per side |
|---|---|---|---|
| `field_position` | `average_start_field_position` | offense, defense | 2 |
| `pace` | `plays_per_drive` | offense only | 1 |
| `turnovers` | `turnover_rate` | offense, defense | 2 |

### From Phase 2e auxiliary datasets (per-team-per-season or per-team-per-week)

| Family | Source dataset | Columns | Features per side |
|---|---|---|---|
| `recruiting` | `phase2e_recruiting` | `recruiting_4yr`, `recruiting_current`, `recruiting_trend` | 3 |
| `returning_production` | `phase2e_returning_production` | 7 PPA/usage columns | 7 |
| `coaching` | `phase2e_coaching` | `coach_tenure`, `coach_new` | 2 |
| `roster_continuity` | `phase2e_roster_continuity` | `roster_size`, `roster_returning_share`, `roster_returning_qb_count` | 3 |
| `lagged_rankings` | `phase2e_lagged_rankings` | `lagged_ap_rank`, `lagged_coaches_rank`, `lagged_ranked_either` | 3 |

## Interfaces and Safeguards

- CLI inputs: `--phase4-rating-uri`, `--phase3-retained-uri`, `--auxiliary-eligibility-uri`; reject
  unsigned, wrong-role, checksum/code-SHA-mismatched, or activation-eligible
  claims.
- Freeze the Phase 4A Ridge `alpha=10` translation head as the canonical bridge.
- Publish version-1 target-context selection, prediction, attribution,
  coverage/fallback, and retained-baseline manifests in Preview only.
- Fit every transform, imputation, and replacement from the training fold only.
  Require `poll_week < game_week`, structural recruiting/roster fallbacks,
  explicit missing indicators, and complete population retention.

## Feature Construction

For each context family, build game-level features following the Phase 4A pattern:

1. **Phase 3 context-only:** Filter adjusted measurements for the family's measurement_ids, pivot by `(season, game_id, team)` to get `home_{measurement}_{role}`, `away_{measurement}_{role}` columns.

2. **Phase 2e per-season:** Join to games via `(season, team)` to get `home_{column}`, `away_{column}` for each family column.

3. **Phase 2e lagged_rankings:** Join via `(season, week, game_id, team)` since rankings are weekly.

4. **Missing data:** Training-fold mean imputation (same as Phase 4A `_standardize()`), with fallback flags.

The expanded feature matrix = 4 rating features + context features. The "no-context" baseline = 4 rating features only (re-fit Ridge on same folds).

## Frozen Bridge

- Ridge `alpha=10` (frozen from Phase 4A)
- Fold-local z-score standardization with `scale_floor=0.05` (same as Phase 4A)
- Same validation seasons: `(2018, 2019, 2021, 2022, 2023, 2024, 2025)`
- Same temporal folding: train on strictly preceding seasons
- Numerical guards: coefficient magnitude ≤1000, feature magnitude ≤100, finite checks

## Selection Logic (per target)

For each target (`margin`, `total`):

1. Compute baseline MAE (rating-only, 4 features)
2. For each context family:
   - Expand features (4 rating + family features)
   - Re-fit Ridge, compute pooled MAE
   - Compute improvement % vs baseline
3. Apply gates:
   - `improvement_pct >= 0.5%`
   - 90% paired bootstrap (season-then-week, 2000 draws, seed 20260908) excludes zero
   - `coverage_equal` (same game population)
   - `maximum_seasonal_regression_pct <= 5%`
4. If no family passes: retain no-context baseline
5. If multiple pass: select fewest-feature family within 0.5% of best

## Artifacts to Produce

| Dataset | Schema | Description |
|---|---|---|
| `phase4b_context_predictions` | `phase4b_context_predictions_v1` | Fold predictions for all families × targets |
| `phase4b_context_attribution` | `phase4b_context_attribution_v1` | Evaluation metrics per family per target |
| `phase4b_context_coverage` | `phase4b_context_coverage_v1` | Coverage/fallback diagnostics per family |
| Retained baseline manifest | `data_first_phase4b_retained_baseline_v1` | Signed handoff for Phase 5 |

Output root: `artifacts/research/data-first-football-v1/phase4b/runs/<run-id>/`

## Implementation Tasks

### Task 1: Contracts module — `src/cks_picks_cfb/data/data_first_phase4b.py`

- `Phase4BError` class
- `phase4b_identity()` — deterministic run identity binding all 3 parents
- `verify_phase4a_parent()` — verify Phase 4A retained rating (frozen, `rho_0_60__exposure`, no auxiliary context)
- `verify_phase2e_parent()` — verify Phase 2e eligibility (reconstructed-only, activation-ineligible)
- `CONTEXT_FAMILY_FEATURES` — sealed mapping of family → feature columns
- `validate_phase4b_config()` — reject drift in family registry and selection params
- `select_context()` — per-target gates + simplicity tie-break
- `retained_baseline_manifest()` — signed handoff with activation-ineligible flags
- Schema constants for all 3 datasets

### Task 2: Schema registration — `src/cks_picks_cfb/data/schema_contracts.py`

- Register `phase4b_context_predictions`, `phase4b_context_attribution`, `phase4b_context_coverage` schemas

### Task 3: Tournament computation — `src/cks_picks_cfb/ratings/phase4b.py`

- `load_context_features()` — load Phase 3 context-only + Phase 2e datasets from storage
- `build_game_context()` — join context to game frame, pivot to home/away features
- `run_context_tournament()` — for each family × target, expand features, fit Ridge, compute predictions
- `evaluate_context_tournament()` — compute attribution metrics per family per target
- Reuse Phase 4A `_standardize()`, `_fit_predict_ridge()`, `_native_float64()` patterns (extract to shared utils or duplicate with Phase4B naming)

### Task 4: Runner script — `scripts/research/run_data_first_phase4b.py`

- CLI: `--phase4-rating-uri`, `--phase3-retained-uri`, `--auxiliary-eligibility-uri`, `--run-id`, `--expected-code-sha`, `--environment`, `--as-of`, `--config`, `--apply`
- Pre-flight: code SHA, clean worktree, committed paths, parent SHA verification
- `compute()`: load parents, build context features, run tournament
- `apply()`: write datasets, write manifest
- Dry-run default

### Task 5: Verifier script — `scripts/research/verify_data_first_phase4b.py`

- Independent verification of retained manifest
- Check all output datasets (schemas, row counts, finiteness)
- Verify no market contamination
- Verify rating states remain context-free
- Verify population equality across families

### Task 6: Config — `conf/research/data_first_football_v1/phase4b_target_context_v1.yaml`

- Sealed context family registry (8 families with feature columns)
- Selection parameters (0.5% threshold, 5% max regression, 90% bootstrap, 2000 draws, seed)
- Ridge alpha=10, validation seasons

### Task 7: Tests — `tests/test_data_first_phase4b.py`

- Parent verification (Phase 4A, Phase 2e, Phase 3)
- Config validation
- Context feature construction (each family)
- Selection logic (gates, simplicity tie-break, no-context retention)
- Tournament evaluation (identical populations, fold-local fitting)
- Market exclusion
- Immutable collision detection

### Task 8: Documentation

- Update Phase 4B plan status to `Implemented`
- Update roadmap checkpoint
- Add Phase 4B to certified predecessor evidence table
- Session log

## Key Design Decisions

1. **Context features are per-side** (`home_X`, `away_X`) following Phase 4A pattern, not differences.

2. **Phase 3 context-only measurements use per-game adjusted values** (which equal raw aggregates since `adjustment_method="none"`).

3. **No-context baseline is re-fit** (not copied from Phase 4A predictions) to ensure identical code path.

4. **Margin and total are evaluated independently** — each can select a different context family or no context.

5. **Lagged rankings join on `(season, week, game_id, team)`** since they're weekly updates; all other Phase 2e families join on `(season, team)`.

6. **Missing data uses training-fold mean imputation** with fallback flags, same as Phase 4A.

7. **Numerical guards are inherited from Phase 4A** (coefficient magnitude ≤1000, feature magnitude ≤100, finite checks, suppressed matmul warnings).

## Validation

- Test parent identity, fold-local transforms, ranking lag, missing indicators,
  structural fallbacks, equal populations, thresholds, deterministic manifests,
  immutable collisions, and market exclusion.
- Run focused Phase 2e/Phase 3/rating tests plus full warning-as-error Python,
  coverage, Ruff, contracts validation, strict MkDocs, V4/boundary checks, and
  `git diff --check`.
- Dry run: warning-free with expected population counts
- Apply: immutable artifacts written
- Independent verification: status `verified`

## Definition of Done

- [x] Each target retains no more than one context family.
- [x] Rating states remain context-free and every game remains represented.
- [x] Frozen simple target baselines are reproducible and research-only.
- [x] Artifacts, validation, documentation, and a session log are complete.

## Amendments

Context stacking, additional families, altered bridge/folds/thresholds, market
inputs, or rating-context interaction requires a revised approved plan.

## File Manifest

| File | Action |
|---|---|
| `src/cks_picks_cfb/data/data_first_phase4b.py` | Create |
| `src/cks_picks_cfb/ratings/phase4b.py` | Create |
| `src/cks_picks_cfb/data/schema_contracts.py` | Edit (add Phase 4B schemas) |
| `scripts/research/run_data_first_phase4b.py` | Create |
| `scripts/research/verify_data_first_phase4b.py` | Create |
| `conf/research/data_first_football_v1/phase4b_target_context_v1.yaml` | Create |
| `tests/test_data_first_phase4b.py` | Create |
| `docs/plans/2026-09-07/03-phase4b-target-context-selection.md` | Edit (status → Implemented) |
| `docs/planning/data-first-football-forecasting-roadmap.md` | Edit (checkpoint + evidence table) |
| `session_logs/2026-09-08/03-phase4b-target-context-completion.md` | Create |
