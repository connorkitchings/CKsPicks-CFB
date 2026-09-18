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

### V5 ratings successor: current contracts

The [September 13 common contract](2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
is Approved; the [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md)
is the canonical status page. Repair v2 and Phase 3 v2 are certified. Possession
measurements are independently certified in Preview as
`possession-v1-measurements-20260915-18fb0aa-r6`; the active V5 priority is the
historical-foundation audit through 2025. V5 ratings successor is distinct from
V4 feature schema v5.
The original Phase 4B retained manifest remains prohibited as a forecasting parent.

| Contract | Status and dependency |
| --- | --- |
| 00: [Documentation alignment](2026-09-13/00-v5-documentation-and-methodology-alignment.md) | **Implemented.** Completed 2026-09-13: documentation and authority tests aligned; no computational certification. |
| 01: [V4 feature-v5 diagnostic closure](2026-09-13/01-v4-feature-v5-diagnostic-closure.md) | **Approved.** Independent side task; exact Week 2 outcomes/refs must be reverified. |
| 02: [Possession measurement certification](2026-09-13/02-v5-possession-measurement-certification.md) | **Implemented.** R6 Preview manifest independently verified and idempotent; its methodology and evidence are subject to Contract 10's full historical audit. |
| 03: [Possession rating estimation](2026-09-13/03-v5-possession-rating-estimation.md) | **Implemented.** Historical rating artifact selected `ppp__rho_0_60__exposure`; its lineage and methodology are subject to Contract 10. |
| 04: [Forecast bridge and fitting windows](2026-09-13/04-v5-forecast-bridge-and-fitting-window.md) | **In Progress.** 04A remains implemented; 04B's manifest-level verifier does not reconstruct forecast computations/outputs, so Contract 11 must close eligibility. |
| 05: [Prospective readiness and shadow tooling](2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md) | **Implemented.** 05A/05B/05C certify shadow tooling and diagnostic rehearsal only; they do not certify forecast quality, live readiness, or prospective evidence. |
| 06: [Prospective evidence and recommendation](2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | **Approved.** Deferred behind 10-12, explicit acceptance of historical readiness, and later re-reviewed live application. |

Each task names one exact contract. Approval does not satisfy a missing verified
parent, certify data, or create prospective evidence. Contract 01 is independent
of the rating sequence. No promotion or serving change is authorized.

### V5-04 execution decomposition (2026-09-17)

| Contract | Status and dependency |
| --- | --- |
| 04A: [Forecast offsets, bridge, and horizons](2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md) | **Implemented 2026-09-17.** Hardened, preflighted three times byte-identical under `forecast-v1-20260917-19ca44b-04a` (selected shared `expanding` horizon, alpha-10 reference heads, equal 3,659-game populations). |
| 04A hardening: [Hardening, preflight closure, and 04B rebase](2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md) | **Implemented 2026-09-17.** Exact three-URI binding, 2018/2019/2021 reporting, expanded metrics, two mechanical preflight repairs (Amendments 1–2); two dead diagnostic identities preserved. |
| 04B: [Calibration and certification](2026-09-17/02-v5-forecast-calibration-and-certification.md) | **In Progress.** The September 17 artifact remains historical evidence; Contract 11 must independently reconstruct outputs before forecast eligibility can be restored. |

### V5-05 execution decomposition (2026-09-17)

| Contract | Status and dependency |
| --- | --- |
| 05A: [Readiness validation and frozen replay](2026-09-17/04-v5-05a-readiness-and-replay.md) | **Implemented 2026-09-17.** Certified Preview artifact `shadow-v1-20260917-cd07d8b-05a`: verified `blocked` readiness (no 2026 schedule/team-states), frozen-replay proof `e4d798bac7d3`, preflight/apply/verify/repeat passed. |
| 05B: [Shadow freeze, scoring, and evidence ledger](2026-09-17/05-v5-05b-freeze-score-ledger.md) | **Implemented 2026-09-18.** Certified Preview freeze artifact `shadow-v1-20260918-73e8e9b-05b-freeze` and score artifact `shadow-v1-20260918-7aec1c8-05b-score`: measured freeze, outcome-versioned scoring, evidence counter, idempotent repeat verified. |
| 05C: [Diagnostic rehearsal, verification, and runbook](2026-09-17/06-v5-05c-rehearsal-verification-runbook.md) | **Implemented.** Certified 2026-09-18 Preview rehearsal `shadow-v1-20260918-6dc87e0-05c`: independent verifier, 7/7-case diagnostic rehearsal with qualifying 0, refreshed `blocked` readiness report, shadow runbook, Contract 06 handoff (still-blocked). |

### V5-07/08/09 2026 extension sequence (2026-09-18)

Approved 2026-09-18 as a possible later application path. Execution is deferred
until Contracts 10-12 close, the user explicitly accepts historical readiness,
and 07-09 are re-reviewed against the frozen design and exact eligible artifacts.
Each contract names its exact entry gate; approval does not satisfy a deferral or
unmet data dependency.

| Contract | Status and dependency |
| --- | --- |
| 07: [2026 Repair and possession measurement extension](2026-09-18/07-v5-2026-repair-and-measurement-extension.md) | **Approved, deferred.** Re-review only after 10-12 and explicit historical-readiness acceptance. |
| 08: [2026 rating-state replay](2026-09-18/08-v5-2026-rating-state-replay.md) | **Approved, deferred.** Requires re-reviewed 07 and frozen historically accepted design; replay does not create prospective evidence. |
| 09: [2026 forecast generation and live readiness](2026-09-18/09-v5-2026-forecast-and-readiness.md) | **Approved, deferred.** Requires re-reviewed 07/08 and exact frozen forecast artifact; `live` timing alone is not prospective proof. |

### V5 historical-first review sequence (2026-09-18)

| Contract | Status and dependency |
| --- | --- |
| 10: [Historical foundation audit](2026-09-18/10-v5-historical-foundation-audit.md) | **Draft.** Umbrella: frozen parents, outputs, severities/dispositions, Contract 11 gate. |
| 10a: [Audit harness and lineage](2026-09-18/10a-v5-audit-harness-and-lineage.md) | **Draft.** Spec, lineage inventory, read-only harness; ends with three byte-identical preflights; zero R2 writes. Explicit user handoff authorizes 10a execution. |
| 10b: [Full-corpus audit execution](2026-09-18/10b-v5-full-corpus-audit-execution.md) | **Draft.** Full-corpus checks, independent verification, findings, publication; requires completed 10a. |
| 11: [Forecast verification closure](2026-09-18/11-v5-forecast-verification-closure.md) | **Draft.** Starts after 10 resolves forecast findings; independently reconstructs the forecast chain. |
| 12: [Historical results and readiness review](2026-09-18/12-v5-historical-results-and-readiness-review.md) | **Draft.** Starts after 10/11; historical report and non-automatic readiness recommendation. |

### Certified foundations and superseded execution records

| Record | Status and permitted use |
| --- | --- |
| [Repair v2](2026-09-08/data-first-repair-and-recertification-v2.md) | **Implemented and independently Preview-verified.** Exact repaired source/population parent. |
| [Phase 3 compact-state v2](2026-09-10/phase3-v2-compact-tournament-state.md) | **Implemented.** `phase3-v2-compact-state-20260910-r2`, selected `quality_core_epa_split`; independent verification and idempotent rerun passed 2026-09-11. Historical reconstructed benchmark only. |
| [September 10 alignment](2026-09-10/documentation-alignment-and-next-research-steps.md) | **Implemented.** Historical documentation checkpoint. |
| [September 11 methodology specification](2026-09-11/possession-rating-methodology-specification.md) | **Implemented.** Original documentation milestone; amended by the September 13 package and current [methodology](../modeling/possession_rating_methodology.md). Not possession certification. |
| [September 8 Phase 4A](2026-09-08/phase4a-prior-and-dynamic-rating-selection-v2.md) | **Superseded** by 03; only explicitly inherited mathematical sections remain binding. |
| [September 8 Phase 4B](2026-09-08/phase4b-pregame-context-selection-v2.md) | **Superseded** by 04; additional context selection deferred. |
| [September 8 Phase 5](2026-09-08/phase5-rating-based-forecast-selection-v2.md) | **Superseded** by 04; first release is the Ridge bridge, not the old family registry. |
| [September 8 Phase 6](2026-09-08/phase6-prospective-evidence-v2.md) | **Superseded** by 05–06; old runners are not authorized by mathematical inheritance. |

The [September 8 review](2026-09-08/transformation-review-and-authority-reset.md)
retains its exact findings and historical approvals. Neither old manifest hashes
nor historical implementation completion establish current forecast eligibility.

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
  — **In Progress.** Completed parity gates and Week 0/1 scored artifacts remain
  intact. The September 13 operations record establishes Week 2 closure; resume
  Task 5 under [contract 01](2026-09-13/01-v4-feature-v5-diagnostic-closure.md)
  only after fresh verification of exact final-outcome and shadow refs. The pooled
  verdict is pending, not completed by this documentation update. This V4 feature
  schema v5 diagnostic is independent of V5 ratings. Preserve its threshold
  calculation and use paired prediction/error changes for causal interpretation.

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
