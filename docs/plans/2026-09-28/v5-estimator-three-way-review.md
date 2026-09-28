# V5 Estimator Review: Snapshot Stream vs Single Cumulative vs Game-Specific

- **Status:** In Progress
- **Created:** 2026-09-28
- **Planner:** Sol
- **Approval source:** User approved the Draft ("approved", 2026-09-28 session)
- **Implementation log:** `session_logs/2026-09-28/08-followup2-implementation.md`
- **Commit policy:** Separate plan commit (research; independent review track)

## Goal

Resolve the audit's open estimator concern with a bounded, reproducible
comparison of three rating estimators on identical populations:

- **(a) snapshot-stream replica** — the accepted construction: each game's
  cumulative iteration-4 adjusted snapshot consumed as one evidence value
  (`_streams` in `src/cks_picks_cfb/ratings/possession_live_replay.py:226`,
  terminal fallback in `build_current_team_states` at `:439`).
- **(b) single cumulative shrunk once** — the latest admissible cumulative
  adjusted estimate combined with the prior in one update.
- **(c) game-specific adjusted observations** — genuinely per-game adjusted
  values, each assimilated exactly once.

Phase 1 proves influence weights and timing on small hand-computable schedules
before any historical run. Phase 2 evaluates chronologically with the lab's
common bridge. Success is a trustworthy attribution of *how* the three differ
(weights, timing, forecast skill, uncertainty behavior) — not the selection of
a production replacement. No estimator is promoted by this contract.

## Current State

- The audit (`docs/research/2026-09-28-current-v5-ratings-audit.md`,
  "The cumulative-snapshot issue") shows estimator (a) assigns South Carolina's
  cumulative season measurement to the Alabama game and re-enters Kent State
  inside later values; equal-exposure illustration gives raw games effective
  weights 61.1/27.8/11.1% within the evidence component. Methodology's
  "do not repeatedly assimilate cumulative snapshots" instruction is in tension
  with this construction.
- The V6 lab (`src/cks_picks_cfb/ratings_lab/`) already provides: versioned
  `Game`/`Observation`/`RatingState` contracts with `individual` vs
  `cumulative` kinds and contributor IDs (`contracts.py`); a replay engine with
  `incremental` (consume-once) and `cumulative` (latest-replaces) modes plus
  admissibility/chronology enforcement (`replay.py`); raw per-game PPP
  individuals from pinned V5 parents (`corpus.py`, `measurements.py`
  `build_individual`); cumulative-mean snapshots with contributor IDs
  (`build_cumulative`); a common alpha-10 Ridge bridge with earlier-only
  calibration and paired bootstrap comparison (`evaluation.py`).
- Gaps this contract fills: the lab has **no** shared V5-exposure updater
  (rho-0.60 init, `prior_weight = 8/(8 + P0·N)`), **no** imported
  opponent-adjusted cumulative snapshots, and **no** per-game adjusted recipe —
  the lab's individuals carry `raw_value`, and its cumulative builder averages
  raw values rather than reproducing V5's 4-pass adjusted snapshots.

## Proposed Approach

Implement the missing updater once as shared lab code, import V5's adjusted
cumulative snapshots as labeled data (never as independent game measurements),
derive per-game adjusted values with an earlier-only recipe, and register the
three estimators as lab designs reusing the existing replay modes and common
bridge. Phase 1 on synthetic schedules first; Phase 2 on the accepted
historical corpus only after Phase 1 weights match hand computation.
Alternatives rejected: reusing raw cumulative means as the (a)/(b) input
(answers the wrong question — the concern is specifically about *adjusted*
snapshots); fitting per-game adjustment on full-season graphs (leaks future
opponent information into early states).

## Scope

### Included

- Shared V5-exposure updater in the lab (rho-0.60 carryover init, k=8
  exposure weighting, exact prior/evidence shares in explanations).
- Corpus import of V5 iteration-4 adjusted cumulative snapshots as labeled
  `cumulative` observations with contributor IDs (new measurement id, e.g.
  `ppp_adj_cumulative_v1`); pinned to the accepted r9 parents.
- Earlier-only per-game adjustment recipe (new measurement id, e.g.
  `ppp_adj_game_v1`): same 4-pass additive form as the V5 methodology, fitted
  only on games admissible at each target game's availability boundary,
  standardized with the accepted historical scales.
- Three registered designs plus frozen-V5 reproduction validation for (a).
- Phase 1 synthetic-schedule proofs; Phase 2 historical evaluation with
  sensitivities (sparse early opponent networks, garbage-time exposure, prior
  strength, variance interpretation).
- Operator-grade documentation of influence weights, timing, and findings.

### Excluded

- Any change to accepted V5 code, artifacts, R2 objects, Neon rows, site
  selections, or the weekly operator.
- Production promotion, selection, or retirement decisions; any winner
  declared because it reorders Alabama/South Carolina.
- 2020 data in any boundary; full-season-fitted adjustment; fixed-V5-coefficient
  reuse on rescaled ratings (common bridge is always refit per candidate).
- New immutable publishes to the lab bucket before V6 Task 5 closes; Phase 2
  runs read-only through the source adapter with local manifests recorded.

## Affected Components and Contracts

- `src/cks_picks_cfb/ratings_lab/` — new updater module, corpus import
  extension, new measurement recipe, three designs, synthetic-schedule tests.
  Existing replay modes, bridge, and evaluation protocol unchanged.
- `conf/research/ratings_lab_v1/protocol.yaml` — only if a new measurement id
  or experiment identity must be registered; protocol seasons, folds, and
  bootstrap seed (2000 replicates, seed 20260928, 90% interval) unchanged.
- `scripts/research/ratings_lab.py` — only additive CLI wiring if needed for
  new stages; dry-run-by-default preserved.
- `docs/modeling/v5_status.md` — findings note on completion.
- No change to `src/cks_picks_cfb/ratings/`, `contracts/`, Neon, or `web/`.

## Implementation Tasks

### Task 1 — Shared V5-exposure updater plus snapshot-stream replica (a)

**Files:**

- `src/cks_picks_cfb/ratings_lab/` (new updater module + design registration)
- `tests/ratings_lab/` (updater unit tests)

**Changes:**

- Implement `initialize` (rho-0.60 carryover, `0.60^gap` with two-year
  2019→2021 gap preserved) and `estimate` (exposure-weighted update with
  `I = N/8`, `P = 1/(1/P0 + I)`, exact `prior_weight`/`evidence_weight` in
  every explanation, linear methods only).
- Register design (a) in `incremental` mode consuming imported adjusted
  cumulative snapshots one per game, replicating `_streams` assignment
  (game's own possessions weight its cumulative snapshot; most-recent game
  without a later-week boundary uses the terminal value).

**Acceptance criteria:**

- Updater unit tests reproduce the audit's hand values (e.g. South Carolina
  offense 1.893284 decomposition terms within 1e-9).
- Design (a) reproduces frozen V5 pregame states across the development
  corpus (max abs mean difference recorded; must be ~0 — any deviation is a
  fidelity defect, not a finding).

**Validation:**

- New focused pytest module; existing `tests/ratings_lab/test_platform.py`
  still passes; `ruff format --check .` and `ruff check` (both — the CI gap
  lesson).

### Task 2 — Single-cumulative design (b) and game-specific recipe/design (c)

**Files:**

- `src/cks_picks_cfb/ratings_lab/` (corpus import, recipe, two designs)
- `tests/ratings_lab/` (recipe and chronology tests)

**Changes:**

- Import V5 adjusted cumulative snapshots as labeled `cumulative`
  observations with explicit contributor IDs, pinned to accepted r9 parents
  with SHA verification; reject any use of them as `individual` evidence
  (the engine already enforces kind separation — add a regression test).
- Register design (b) in `cumulative` mode over the same snapshots with the
  Task 1 updater: latest admissible snapshot replaces prior evidence.
- Implement the earlier-only per-game adjustment recipe and register design
  (c) in `incremental` mode over its outputs with the Task 1 updater.

**Acceptance criteria:**

- (b) terminal state equals a single shrink of the final cumulative snapshot
  on synthetic schedules (exact).
- (c) on synthetic schedules equals the plain exposure-weighted mean of its
  per-game adjusted values (exact); no observation consumed twice (engine
  duplicate-key enforcement plus explanation audit).
- Missing/sparse early opponent graphs degrade with explicit reasons, never
  silent borrowing.

**Validation:**

- Recipe tests: earlier-only fitting (a late-season result cannot move an
  early state — shuffle/future-mask test), FCS-only early graphs, byes,
  postponed games, 2019→2021 gap, 2020 rejection.
- Full lab test suite green; format and lint gates pass.

### Task 3 — Phase 1 hand-computable proofs

**Files:**

- `tests/ratings_lab/` (new proof module)
- `docs/research/` (weights-and-timing note)

**Changes:**

- Three-team synthetic schedules with hand-computed expectations proving:
  (a) yields the 61.1/27.8/11.1 effective-weight pattern on equal exposures;
  (b) matches single-shrink; (c) matches exposure-weighted mean; all three
  agree exactly on single-game seasons.
- Timing proofs: bye preserves state, delayed evidence stays out of pregame
  states, boundary-assignment matches `_streams` semantics for (a).

**Acceptance criteria:**

- Every asserted number hand-derived in the docs note; tests fail if any
  estimator's weight or timing changes.
- Phase 2 may not start until Phase 1 passes.

**Validation:**

- Proof module green; docs note records all hand computations.

### Task 4 — Phase 2 historical evaluation and sensitivities

**Files:**

- `src/cks_picks_cfb/ratings_lab/` (experiment wiring only; no engine changes)
- `docs/research/` (evaluation report)

**Changes:**

- Replay (a)/(b)/(c) over development seasons 2015–2019 + 2021–2025 under
  protocol `ratings_lab_historical_v1`; headline comparison on 2022–2025 with
  the existing common bridge (separately refit per candidate, earlier-only
  calibration) and paired bootstrap; metrics MAE/RMSE/bias/CRPS,
  coverage/width, stages 0/1/2/3/4+.
- Sensitivities: sparse early opponent networks, garbage-time exposure
  variants, prior strength (k grid around 8 as diagnostic), and rating-variance
  interpretation under correlated inputs for (a).
- 2026 observed results enter only a separately labeled diagnostic replay —
  never fitting or selection.

**Acceptance criteria:**

- Full-population coverage on the same game keys as the frozen V5 benchmark
  (missing predictions cannot improve a score — engine validation enforces).
- Report attributes every skill difference to weights, timing, or inputs with
  numbers; no production recommendation; no Alabama-ordering selection.

**Validation:**

- Evaluation report with manifest keys, checksums, runtime; deterministic
  rerun preserves logical hashes; full test suite + gates green.

## Testing Strategy

- Unit: updater math, recipe earlier-only property, owner/contributor identity.
- Proof: hand-computed synthetic schedules (Phase 1 gate).
- Regression: full lab suite plus storage/boundary/V5-rating suites on every
  change; `ruff format --check` and `ruff check` (both, always).
- Evaluation: common-bridge paired protocol only; no bespoke metrics per
  candidate.

## Risks and Edge Cases

- Per-game adjustment on sparse early graphs (FCS opponents, byes) may be
  unstable — that instability is a finding to report, not to smooth away.
- If design (a) fails to reproduce frozen V5 states, stop: fidelity first,
  no Phase 2 on a broken replica.
- Correlated-input variance for (a) is expected to misbehave; the task is to
  characterize, not to fix, the variance.
- Research reads go through the read-only source adapter; no lab-bucket
  writes until V6 Task 5 closes. V6 Task 5 itself is not a prerequisite.

## Definition of Done

- [ ] Updater, three designs, and both recipes implemented with Phase 1 proofs green.
- [ ] (a) reproduces frozen V5 pregame states (difference recorded ~0).
- [ ] Phase 2 evaluation complete with full-population coverage and paired comparison.
- [ ] Sensitivities and variance characterization reported; no promotion claim.
- [ ] `v5_status.md` findings note recorded; implementation log created.
- [ ] Full test suite, `ruff format --check`, `ruff check`, `mkdocs build`, `git diff --check` pass.
- [ ] Plan status updated to `Implemented` only then; otherwise `In Progress` with blocker.
- [ ] No accepted V5 artifact, production state, or selection changed.

## Amendments

None yet. A change to the adjustment recipe form, evaluation folds, or any
production/p promotion implication requires a new approved amendment.
