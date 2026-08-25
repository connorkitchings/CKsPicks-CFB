# Phase 3 — Structured Margin and Total Baseline

- **Status:** In Progress
- **Created:** 2026-08-25
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact contract on 2026-08-25.
- **Implementation logs:** `session_logs/2026-08-25/01-phase3-structured-prediction.md`,
  `session_logs/2026-08-25/04-phase3-foundation-certification.md`,
  `session_logs/2026-08-25/05-phase3-structured-prediction.md`
- **Commit policy:** Commit code/configuration before joining outcomes or writing Preview artifacts.

## Goal

Certify the authoritative Phase 1–2 handoff, then build a Preview-only,
two-equation OLS margin/total baseline with point-in-time pace and uncertainty.

## Contract

- Review exact refs, checksums, formulas, temporal boundaries, coverage,
  carryover, and uncertainty before prediction construction.
- Use pregame states only; terminal measurement snapshots are pace fallback.
- Fit expanding 2022–2025 folds, then refit unchanged on 2021–2025 only after
  all historical gates pass.
- Margin uses quality gap plus home-field; total uses offense/defense sums,
  standardized pace, and intercept. Markets, residual ML, V4 mutation,
  production, Neon, and public outputs are excluded.
- Emit immutable foundation review, model, prediction, evaluation, and final
  candidate-manifest artifacts under the ratings research prefix.

## Historical Gates

- Pooled MAE/RMSE no worse than 1.10x paired V4; seasonal MAE no worse than
  1.20x paired V4; bias at most 2 points and V4 bias plus 1 point.
- Standardized residual mean <= .15, SD in [.80, 1.20], 80% coverage in
  [72%, 88%], and 95% coverage in [90%, 99%].
- Any failed certification or historical gate leaves this plan In Progress and
  blocks Phase 4.

## Amendment 1 -- V4 benchmark-recovery prerequisite (2026-08-25)

Phase 3 prediction construction remains blocked until the separate
[`phase3-v4-benchmark-recovery.md`](phase3-v4-benchmark-recovery.md) contract
has produced a passing immutable `rating_v4_historical_predictions_v1` ref.
Paired V4 metrics must consume only that ref on matching game/target keys and
retain its `source_kind`; the historical gates above are unchanged.

### Implementation Record -- Certified V4 benchmark (2026-08-25)

The prerequisite is satisfied by the passing Preview
`rating_v4_historical_predictions_v1` version `f4ec062c7f931f125ce6be99`
(content SHA
`6bdbe75ce83554c5828ac1a807056e26844db44c77defb6607d2ec7386efca2d`).
Its audit SHA is
`f601ba9d24becc07019d0bfb97e6d8ed74801eaae3da89f2148e52dbfd821538`; all
six recovery gates pass and the same-stamp rerun is byte-identical. Phase 3
may use this artifact only on matching `(season, game_id, target)` keys and
must preserve `source_kind` in paired evaluation output. This record unblocks
the Phase 3 foundation review, not prediction construction or Phase 4.

### Implementation Record -- Foundation certification (2026-08-25)

The independent Preview review passed all 24 checks and is immutable at:

`artifacts/research/rating-successor/foundation-review/a0e74956f78b12a23de3eca08e5f8382b982c1222f3c101ff07db835d6e6a0fc/runs/2026-08-25T1429Z-foundation-review/report.json`

Its SHA-256 is
`865699a17198967a67664b254036164b3940a4f2f161f1a9aff1c98be4156e62`.
The report is bound to certification code commit
`d626258`, the authoritative Phase 1 v2 refs, and Phase 2 team-state version
`1fdcb1ca6d235bf2ecf87414`. It independently recomputed observation ratios,
point-in-time bounds, 39 exposure-weighted opponent-adjustment rows, component
standardization/posteriors, prior carryover, composites, and two-team pregame
coverage. The same-stamp rerun produced the identical report SHA.

This clears only the certification gate. Phase 3 may now implement the frozen
structured margin/total baseline; no predictions, outcomes-based evaluation,
markets, production, Neon, or public state were touched by this review.

### Implementation Record -- Pending Preview materialization (2026-08-25)

The isolated OLS baseline, deterministic pace context, Normal uncertainty,
paired V4 evaluation, immutable configuration, and Preview-only CLI are
implemented locally. The CLI is explicitly commit-identity-gated and has not
read historical outcomes or written Preview artifacts. Its code and
configuration must be committed before materialization; Phase 3 remains `In
Progress` until the immutable historical evaluation and candidate-freeze gates
pass.

### Amendment 2 -- Canonical score-column merge hardening (2026-08-25)

The first attempted Preview materialization recovered the exact staged parent
filenames after a pre-read `NoSuchKey` stop. The next attempt reached feature
assembly and stopped before any artifact write because canonical `games` also
contains score columns that collide with `game_outcomes` during the join. The
Phase 3 assembler now names outcome completion and score fields explicitly and
derives targets only from the authoritative outcome fields. This is a
mechanical lineage correction, preserves the frozen equations and gates, and
requires a new commit before a fresh run-stamped Preview retry.

## Validation

- Test ref tampering, formula recomputation, terminal-row rejection, OLS
  coefficients/chronology/sign failures, pace fallback, uncertainty, and
  deterministic reruns.
- Run focused and full tests, Ruff, contracts validation, strict MkDocs, and
  diff checks. Record exact refs and checksums in the implementation record.
