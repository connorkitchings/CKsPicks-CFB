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

## Current active contracts

### Data-first football forecasting

The [2026-09-08 review and authority reset](2026-09-08/transformation-review-and-authority-reset.md)
records the approved corrective checkpoint. The original Phase 4B result cannot
be consumed by Phase 5. Ratings remain mandatory; polls/direct models are diagnostics.

| Current contract or record | Status and dependency |
| --- | --- |
| [Repair and recertification v2](2026-09-08/data-first-repair-and-recertification-v2.md) | **Implemented and independently Preview-verified.** Sole repaired modeling parent. |
| [Phase 3 compact-state measurement/core v2](2026-09-10/phase3-v2-compact-tournament-state.md) | **In Progress.** Committed implementation; Preview preflight, materialization, verifier, and rerun are pending. The September 8/9 contracts retain inherited modeling decisions and historical context. |
| [Documentation alignment and next research steps](2026-09-10/documentation-alignment-and-next-research-steps.md) | **In Progress.** Records the agreed possession-based direction and the required methodology-design handoff. |
| [Phase 4A prior/dynamic ratings v2](2026-09-08/phase4a-prior-and-dynamic-rating-selection-v2.md) | **Approved record; execution held** pending methodology replacement or explicit reaffirmation after verified Phase 3. |
| [Phase 4B pregame context v2](2026-09-08/phase4b-pregame-context-selection-v2.md) | **Approved record; execution held** pending the rating-methodology decision. |
| [Phase 5 rating-based forecasts v2](2026-09-08/phase5-rating-based-forecast-selection-v2.md) | **Approved record; execution held** pending replacement forecasting design. |
| [Phase 6 prospective evidence v2](2026-09-08/phase6-prospective-evidence-v2.md) | **Approved record; execution held** pending a verified replacement candidate. |

Each research phase requires a separate implementation task; documentation approval executes no phase.

### Retained transformation engineering and superseded evidence

- [Phase 0 alignment](2026-09-05/00-repository-architecture-and-documentation-alignment.md)
  — Implemented; retained compatibility boundaries.
- [Corrected Phase 1 audit](2026-09-05/01-data-and-evidence-audit.md)
  — Implemented; historical-result dispositions retained.
- [Phase 2 repair](2026-09-05/02-data-repair-and-recertification.md)
  — **Implemented after repair.** Existing engineering retained; auxiliary semantics
  and descendant population require the new repair contract.
- [Phase 2c materialization](2026-09-06/03-phase2c-materialization-and-ref-set-closure.md)
  — Implemented; complete schedule is the reconciliation denominator.
- [Phase 2d/2e bounded repair](2026-09-06/05-transformation-check-in-phase2d-repair-and-phase3-redesign.md)
  — Existing engineering retained; revised semantic eligibility supersedes downstream assumptions.
- [Phase 3](2026-09-07/01-phase3-measurement-certification-and-core-selection.md)
  and [Phase 4A](2026-09-07/02-phase4a-context-free-rating-selection.md)
  — Superseded authority; EPA-only and carryover/exposure results retain reduced-population limitations.
- [Phase 4B](2026-09-07/03-phase4b-target-context-selection.md)
  — Superseded; same-game context invalidates pregame comparison and retained-parent eligibility.
- [Old Phase 5](2026-09-07/04-phase5-final-spread-total-selection.md),
  [old Phase 6](2026-09-07/05-phase6-prospective-evidence-and-market-diagnostics.md),
  and [2026-09-06 resequencing](2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md)
  — Superseded by the approved 2026-09-08 package; never execute as current authority.

### Historical operations (Week 1)

- [Week 1 operations](2026-08-31/week1-operations.md)
  — Completed operational record. Week 1 was published, frozen, and scored;
  the September 10 verification found 43 games and 86 grade rows. Current
  weekly procedures live in the operations runbooks.

### Production model performance

- [2025 V4 week-by-week operational replay](2026-09-09/2025-v4-operational-replay.md)
  — **Implemented 2026-09-10.** Replaced the ad-hoc 2025 backfill with a
  genuine week-by-week operational replay of the selection-time V4 model
  (`v4-locked-test-replay-20260909b`, trained 2021-2024) using authentic
  pre-kickoff provider lines, through the real generate → publish →
  freeze → score pipeline (16 weeks, 762 games incl. Army-Navy). Final 2025
  YTD: spread 380-366-16, total 340-292-5. Live `current_week` restored.

- [2026 v5 shadow rebuild diagnostic](2026-09-10/2026-v5-shadow-rebuild-diagnostic.md)
  — **In Progress — BLOCKED on W2 finals (Amendments 1–3).** All Tier 1 + Tier 2
  gates pass (W0 confinement + 8/8 exact; W1/W2 byte-identical reruns + 43/43 and
  49/49 exact controls, assembler path-equivalence byte-identical + exact).
  Three strict v5 Golds + three shadow prediction artifacts in Preview R2; W0/W1
  shadows scored. Interim (not a verdict): v5 predictions are bit-identical to
  v4 for all 51 W0/W1 games. W2 first kickoff Fri 2026-09-11 → pooled W1+W2
  verdict + kill criterion resume after the Week 2 close. W2 shadow frozen
  pre-kickoff and grading-ready. Preview-only, no serving writes. Replaces the
  contract below as the executable plan.

- [Rebuild 2026 predictions with correct features](2026-09-09/rebuild-2026-predictions.md)
  — **Superseded as executable plan** by the shadow diagnostic above;
  retained as the root-cause record. Its Step 5 (`superseded` state, hand-edited
  run tables) is not executable and predates the Week 2 freeze.
  Documentation updated in `docs/ops/weekly_pipeline.md` and `docs/ops/production_runbook.md`.

### Historical and compatibility rating-transition contracts

- [Early-week strength-prior research](2026-09-02/early-week-strength-prior-research.md)
  — **Implemented 2026-09-04 (pending final user commit).** Adds audited,
  football-only offseason-context research to separate R2 prior and direct
  Game 1–3 tracks. Admission, the direct selection report, and the R2 prior
  tournament (`continuity_ridge_alpha_0_1`, all gates passed) are complete;
  the cross-report decision memo is
  `docs/research/2026-09-04-early-week-context-cross-report.md`. All evidence
  is reconstructed and activation-ineligible; V4 and production stay
  unchanged.

- [R1 cross-lineage audit scope remediation](2026-08-28/r1-cross-lineage-audit-scope-remediation.md)
  — Approved. Compares each hard dataset against its own legacy counterpart
  (games are FBS-scope; outcomes are a superset with legitimately canceled
  games) before the fresh full-corpus R1 run and certification.
- [R1 derived-schema registration and atomicity](2026-08-28/r1-derived-schema-registration-and-atomicity.md)
  — In Progress. Adds executable contracts for the complete derived R1 output
  set and prevents partial immutable writes before a fresh full-corpus R1
  recapture.
- [R1 manifest-declared play-coverage remediation](2026-08-28/r1-manifest-declared-play-coverage-remediation.md)
  — In Progress. Restores the R1 path from complete source capture to
  certification while preserving its existing 90% coverage gate and strict
  default reconciliation behavior.
- [R4 structured predictor and candidate-v2 freeze](2026-08-27/r4-structured-predictor-and-candidate-v2-freeze.md)
  — **Superseded before implementation** by the data-first roadmap.
- [R3 mixed state-update tournament](2026-08-27/r3-mixed-state-update-tournament.md)
  — **Superseded before implementation** by the data-first roadmap.
- [R2 redesigned offseason-prior tournament](2026-08-27/r2-redesigned-offseason-prior-tournament.md)
  — Implemented runner; its R1 certificate gate and reconstructed context
  admission are satisfied. Its first Preview execution remains research-only.
- [R1 full-corpus recapture and certification](2026-08-27/r1-full-corpus-recapture-and-certification.md)
  — Certification completed in Preview run `r1-full-corpus-20260831-5f2a384`.
  Its immutable coverage report permits tournaments; prior failed preflights
  remain diagnostic evidence only.
- [R1 legacy-comparison 2019 selection remediation](2026-08-31/r1-legacy-comparison-2019-selection-remediation.md)
  — Implemented. Its manifest-anchored 2019 resolution enabled the certified
  R1 run; the original catalog failure remains immutable diagnostic evidence.
- [R1 play-capture reliability hardening](2026-08-27/r1-play-capture-reliability-hardening.md)
  — Superseded by the full-corpus R1 contract. Its bounded weekly worker,
  request ledger, and reconciliation implementation remain reusable.
- [Historical expansion and ratings methodology reset](2026-08-26/historical-expansion-ratings-methodology-reset.md)
  — Completed R1/R2 work remains historical evidence; its unfinished R3/R4 and
  locked-2025 sequence is superseded by the data-first roadmap.
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
