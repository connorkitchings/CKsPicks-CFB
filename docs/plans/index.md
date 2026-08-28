# Implementation Contracts

`docs/plans/` holds task-level implementation contracts prepared by Sol and executed by a fresh Terra task. It is distinct from `docs/planning/`, which holds strategic roadmaps and long-lived initiatives.

## Location and naming

Store each contract at:

```text
docs/plans/YYYY-MM-DD/<descriptive-slug>.md
```

The date folder is the chronological ordering. Prefix a same-day filename with `01-`, `02-`, and so on only when implementation order matters.

Copy the template from `.agent/skills/plan-session/assets/implementation-contract-template.md`. A contract records status, approval source, implementation log, and commit policy as well as the goal, current state, tasks, validation, risks, definition of done, and amendments.

## Lifecycle

| Status | Meaning |
| --- | --- |
| `Draft` | Sol is investigating or the user has not approved the contract. |
| `Approved` | The contract is ready for Terra, either by recorded approval or an explicit user handoff for the exact path. |
| `In Progress` | Terra is implementing the contract. |
| `Implemented` | All definition-of-done items and required validation have passed. |
| `Superseded` | A later contract replaces this one. |

Terra must not execute a Draft contract without an explicit user instruction naming that exact path. In that case, Terra records the instruction as the approval source and changes the status to `Approved` before code changes.

## Current rating-transition contracts

- [R1 manifest-declared play-coverage remediation](2026-08-28/r1-manifest-declared-play-coverage-remediation.md)
  — In Progress. Restores the R1 path from complete source capture to
  certification while preserving its existing 90% coverage gate and strict
  default reconciliation behavior.
- [R4 structured predictor and candidate-v2 freeze](2026-08-27/r4-structured-predictor-and-candidate-v2-freeze.md)
  — Approved. Runs selection only through 2024, freezes the end-to-end design,
  and owns the single locked-2025 confirmation and optional candidate-v2 refit.
- [R3 mixed state-update tournament](2026-08-27/r3-mixed-state-update-tournament.md)
  — Approved, blocked on R2. Compares fixed, Bayesian, recency, Glicko-style,
  and constrained ML updaters without reading 2025.
- [R2 redesigned offseason-prior tournament](2026-08-27/r2-redesigned-offseason-prior-tournament.md)
  — Approved, blocked on R1. Generates and selects pooled, EWMA, Ridge, and
  baseline priors from exact certified refs without caller-produced metrics.
- [R1 full-corpus recapture and certification](2026-08-27/r1-full-corpus-recapture-and-certification.md)
  — In Progress, blocked on catalog-restored 2019 legacy comparison evidence.
  The Preview preflight published its immutable failure report before any
  successor capture; it cannot substitute evidence or authorize R2.
- [R1 play-capture reliability hardening](2026-08-27/r1-play-capture-reliability-hardening.md)
  — Superseded by the full-corpus R1 contract. Its bounded weekly worker,
  request ledger, and reconciliation implementation remain reusable.
- [Historical expansion and ratings methodology reset](2026-08-26/historical-expansion-ratings-methodology-reset.md)
  — In Progress governing contract, amended 2026-08-27 for full-corpus
  recapture, redesigned R2–R4, and one end-to-end locked-2025 confirmation.
- [Phase 5 protected prospective evidence](2026-08-26/phase5-protected-prospective-evidence.md)
  — In Progress as O2 diagnostic evidence for frozen candidate v1 only. It
  cannot tune v1, block successor-v2 research, or transfer its evidence to
  candidate v2.
- [Phase 4 isolated shadow operations](2026-08-26/phase4-shadow-operations.md)
  — Implemented 2026-08-26. The Preview-only full-2025 rehearsal passed all 15
  weeks and its byte-identical rerun (summary SHA-256 `b755b585…`).
- [Phase 1/2 true-PPSO remediation and Phase 3 v3 tournament](2026-08-26/phase1-phase2-true-ppso-remediation-and-phase3-v3.md)
  — Implemented 2026-08-26. Phase 1 v3 and Phase 2 v2 are certified with
  byte-identical reruns, and the sealed Phase 3 v3 tournament froze passing
  candidate `negative_binomial_scores` (run `2026-08-26T1502Z-phase3-score-v3`).
  Phase 4 shadow operations are plan-eligible under a fresh contract.
- [Phase 3 v2 sealed team-score tournament](2026-08-25/phase3-score-model-tournament-v2.md)
  — Superseded 2026-08-26 by the passing v3 candidate under the 2026-08-26
  contract. Its sealed selection failed all-family gates on the pre-remediation
  foundation; it is immutable failed research and no v1/v2 artifact may be
  tuned or retried.

## When to use a contract

Use the Sol-to-Terra workflow for architecture, data/model lineage, schemas or migrations, production/deployment behavior, security-sensitive work, or changes that span multiple subsystems. Use the normal fast path for a small, localized change that follows an established pattern.

## Amendments and commits

Terra may append a minor amendment and continue only when it preserves architecture, public interfaces, scope, and acceptance criteria. A material conflict requires stopping and returning to Sol for a revised contract.

Record whether the plan should receive a separate commit. A separate plan commit is recommended for multi-session work, asynchronous review, migrations, production changes, or difficult-to-reverse decisions. Git operations remain user-controlled.
