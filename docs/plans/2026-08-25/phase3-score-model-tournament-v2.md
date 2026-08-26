# Phase 3 v2 — Sealed Team-Score Model Tournament

- **Status:** In Progress
- **Created:** 2026-08-25
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact contract on 2026-08-25.
- **Implementation log:** `session_logs/2026-08-25/08-phase3-score-model-tournament-v2.md`
- **Commit policy:** Commit code and configuration before joining outcomes or writing Preview artifacts.

## Goal

Create a new, sealed Phase 3 candidate identity after the immutable v1
structured margin/total baseline failed its historical gates. Compare linear
and NB2 point-in-time team-score families on expanding 2022–2024 folds,
confirm the winner once on 2025, and freeze it only if every unchanged gate
passes.

## Current State

Phase 1, Phase 2, the foundation review, and the V4 historical benchmark are
certified Preview-only parents. Phase 3 v1 remains immutable failed research:
its diagnostic evaluation may not be used to retune that design. V4 remains
the unchanged production champion; rating research cannot reach Neon, the
catalog, public publication, markets, or production paths.

## Proposed Approach

Use one symmetric, point-in-time, two-side score frame. Each game contributes
a home-score and away-score equation with own offense state, opponent defense
state, pace, and a non-neutral home-field term. The two specified families are
selected together for margin and total, using derived joint-score moments. The
selection rule is frozen: lowest average target-wise MAE ratio to paired V4,
with linear only as the 0.01 tie-break.

## Scope

### Included

- Isolated `rating-score-v2` configuration and immutable Preview contracts:
  `rating_score_models_v2`, `rating_score_predictions_v2`, tournament
  evaluation, and `rating_score_candidate_v2`.
- Deterministic OLS and NB2 fitting, paired score covariance, and derived
  margin/total uncertainty.
- Sealed expanding selection, one unchanged locked-2025 confirmation, and a
  post-cutoff 2026 dry run explicitly labeled non-prospective evidence.
- Test coverage, documentation authority updates, and a session log.

### Excluded

- Changes to V4, markets, residual ML, production R2 paths, Neon, catalog
  registration, public APIs, publication, or Phase 4 operations.
- Retuning Phase 3 v1 or relaxing gates after results are known.

## Implementation Tasks

### Task 1 — Freeze configuration and lineage

**Files:** `conf/ratings/score_model_tournament_v2.yaml`,
`scripts/pipeline/build_rating_score_tournament.py`

Pin certified Phase 1/2/foundation/V4 refs and checksums. Reject non-Preview
storage, uncommitted code, uncertified source parents, market/production
lineage, and output URIs outside the new run-stamped research prefix.

### Task 2 — Build symmetric score families

**Files:** `src/cks_picks_cfb/ratings/score_models.py`,
`src/cks_picks_cfb/ratings/predictions.py`, `pyproject.toml`

Build the shared pregame score frame; fit constrained linear and deterministic
NB2 equations with SciPy; derive margin/total moments and 50/80/95% intervals
without adding state uncertainty a second time.

### Task 3 — Seal selection and confirmation

Train/evaluate 2021→2022, 2021–22→2023, and 2021–23→2024; select only a
family passing every paired V4 gate; confirm that unchanged family with
2021–24→2025. Failed selection/confirmation writes only the immutable
diagnostic tournament report. A passing design refits 2021–25 and writes the
frozen Preview models, predictions, and candidate manifest.

### Task 4 — Validate and close authority

Cover symmetry, signs, venue behavior, score algebra, valid covariance and
intervals, NB2 convergence, fold isolation, deterministic selection/tie-break,
confirmation immutability, and write-boundary rejection. On a passing run,
record exact refs/checksums and rerun evidence; on a failure, record only
diagnostic evidence and retain `In Progress`.

## Validation

- Focused ratings and complete Python tests; Ruff; contracts validation/sync;
  strict MkDocs; `git diff --check`.
- Both score targets retain complete paired V4 coverage and `source_kind`,
  finite positive uncertainty, valid interval ordering, and certified lineage.
- Each selected candidate passes every frozen MAE/RMSE, seasonal, bias,
  standardized-residual, and 80/95% calibration gate on selection and locked
  confirmation.
- A passing Preview run has a byte-identical same-stamp rerun. Failed gates
  have no successful model, prediction, or candidate-manifest ref.

## Definition of Done

- [ ] Configuration, score families, CLI, and regression tests are complete.
- [ ] Required source and repository validation passes.
- [ ] Preview materialization either records a passing frozen v2 candidate and
  byte-identical rerun, or records only immutable failure diagnostics.
- [ ] Documentation and session log state the exact result.
- [ ] Plan is `Implemented` only after a passing candidate freeze; otherwise it
  remains `In Progress` and Phase 4 remains blocked.

## Implementation Record — Sealed selection failure (2026-08-26)

The first execution under run `2026-08-26T0318Z-phase3-score-v2` wrote only a
diagnostic report because both fits detected sign violations after fitting.
This was a mechanical contract defect: frozen direction bounds were checked but
not enforced during optimization. Commit
`ea0d3ac65261c72b5c0ee325c3b22ee2aab9a144` corrected only that behavior with
bounded linear and NB2 optimization plus a regression test; it did not change
equations, inputs, selection, chronology, or gates.

The permitted fresh run used that commit, cutoff `2026-08-26T03:22:08Z`, and
run `2026-08-26T0322Z-phase3-score-v2`. Its immutable selection diagnostic is
at
`artifacts/research/rating-successor/score-tournament-v2/9131f094dd90f2acc902fd8d0b972cd47c0e08263b769f425942b09d331331af/runs/2026-08-26T0322Z-phase3-score-v2/tournament.json`
with SHA-256
`0e391d8c2d48b3252bd9a7b2e13c184a75ca2bd1457d0a9cded632339edb620c`.

Both candidates retained complete paired V4 coverage (2,236 rows per target)
and passed pooled/seasonal error checks. Linear scores passed every margin gate
but failed total bias (7.757) and standardized-residual mean (0.446). NB2
failed margin 80% coverage (91.19%) and residual SD (0.739); its total also
failed bias (8.645), standardized mean (0.370), residual SD (0.735), and 95%
coverage (99.02%). No candidate was selected; no locked-2025 confirmation ran;
and no model, prediction, or candidate-manifest ref exists. This plan remains
`In Progress`, and Phase 4 remains blocked.

## Amendments

None.
