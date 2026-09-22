# V5-10b: Full-Corpus Historical Audit Execution

- **Status:** Implemented
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the revised umbrella + 10a/10b plan with "go" on 2026-09-18, and explicitly authorized 10b execution.
- **Implementation log:** `session_logs/2026-09-18/09-v5-10b-historical-audit.md`
- **Commit policy:** Separate evidence and report checkpoints; user controls Git operations.

## Goal

Execute the full-corpus historical audit with the 10a harness, run independent
evidence verification, and publish the findings report. The
[umbrella](10-v5-historical-foundation-audit.md) owns the boundary, outputs,
severities/dispositions, and Contract 11 gate; [10a](10a-v5-audit-harness-and-lineage.md)
must be complete (committed checkpoint + three identical preflights) before
the evidence-bound 10b apply. Contract 10 completes even with open blockers;
open blockers prevent the full forecast-eligibility Contract 11 from starting.

## Current state

10a delivers the frozen boundary (four exact parents), the read-only harness,
local preflight evidence, and the two seeded structural findings awaiting
scope/severity/disposition determination. The 55-test baseline plus new 10a
audit tests must keep passing; 10b adds execution coverage on top.

**Progress record (2026-09-19 — Implemented):** Full-corpus audit complete. Run
`historical-audit-10b-20260919-full` at code SHA `7a476648` produced 93 checks and 4
findings (3 failed checks). Evidence digest
`edeebe85498f2b7935c3f03a31dde03cc44d08876ded45f8c8c42b7a67e84d42` was reviewed and
accepted. Apply published four versioned outputs to the Preview audit prefix; manifest
SHA `0a95002ce42c28d2d588e3c6a0d327adbe95f95e0232ab16036ff8b6967aabe3`. Independent
verifier confirmed `publication_valid: true`, `verified: true`. Idempotent repeat
returned `already_applied`. All four findings are open blockers; `contract11_permitted:
false`. Human-readable report: `docs/research/2026-09-19-v5-10b-historical-foundation-audit-report.md`.

## Proposed approach

Run every check family across the complete eligible corpus (streaming large
partitioned datasets), publish the four compact versioned outputs to the
Preview audit prefix, run the audit verifier's independent re-read, confirm
idempotent repeat, and write the human-readable report.

## Scope

### Included

- Full-corpus population, football-semantics, opponent-adjustment, rating,
  forecast-chronology, and verifier-assurance checks.
- Final `evidence-register.json`, `check-results.json`, `findings.json`, and
  terminal `audit-manifest.json` (written last) in Preview only.
- Independent re-read, idempotent repeat, `docs/research/` report, and
  lifecycle/roadmap/index/session-log updates.

### Excluded

- Any repair, retune, reselection, or artifact replacement (separate
  corrective contracts).
- Contract 11 forecast reconstruction (record as unresolved, do not duplicate).
- Catalog, Neon, production, web, V4, or historical-artifact writes.

## Affected components and contracts

- Code: `src/cks_picks_cfb/audit/` check suites; `scripts/research/verify_data_first_historical_audit.py`.
- Outputs: `artifacts/research/data-first-football-v1/audits/historical-foundation-v1/runs/<run-id>/`
  (Preview only) plus `docs/research/` report.
- Consumers: [Contract 11](11-v5-forecast-verification-closure.md)
  (gated) and [Contract 12](12-v5-historical-results-and-readiness-review.md).

## Implementation tasks

### Task 1 — Population and football semantics

**Changes:**

- Reconcile schedule, outcome, forecast-eligible, and measurement-usable
  populations by season and FBS/FCS classification.
- Preserve completed games lacking measurements; report every
  omission/disposition.
- Reconcile possession membership, scoring-event attribution, regulation
  offense, excluded offense, non-offense scoring, overtime, and unresolved
  increments to final scores.
- Confirm PPP and EPA-per-possession use the same eligible denominator and
  retain declared native meanings.
- Verify home/away and offense/defense role mappings and fallback behavior.

**Acceptance criteria:**

- Every population gap has an evidence-backed disposition; ledger imbalances
  and role reversals are findings, not silent drops.

**Validation:**

- Reconciliation tests on bounded fixtures plus full-corpus counts/digests.

### Task 2 — Opponent adjustment and ratings

**Changes:**

- Confirm four-pass league-centered adjustment, retained iterations, units,
  and absence of a second schedule-strength adjustment in ratings.
- Validate preseason-prior inputs, neutral and fixed-rho fallbacks,
  learned-prior chronology, FCS fallback behavior, and the 2019→2021 transition.
- Confirm rating updates consume only evidence strictly before each
  prediction cutoff (same-game/future perturbation invariance on bounded fixtures).
- Verify the 60-candidate registry, selected candidate identity, state
  continuity, uncertainty arithmetic, and stored rating-selection evidence.
- Confirm 2025 participates only as chronological development evidence.

**Acceptance criteria:**

- Any leakage, chronology violation, or unreproducible selection is a
  `blocker`; coverage/fallback/uncertainty weaknesses are `major` or below
  with interpretation impact stated.

**Validation:**

- Perturbation-invariance tests; chronology and carryover fixture tests.

### Task 3 — Forecast construction and chronology

**Changes:**

- Confirm targets, venue signs, non-offense offsets, completed-game-stage
  counts, fitting seasons, inner-alpha seasons, horizon populations, and
  calibration-residual seasons.
- Prove same-game and future-row perturbations cannot alter earlier states
  or forecasts on bounded fixtures.
- Explicitly determine whether a complete through-2025 final fit/calibration
  artifact exists and is reproducible; absence is a blocking finding for
  later 2026 application.
- Record forecast-output reconstruction as unresolved for Contract 11 rather
  than duplicating Contract 11 inside the audit.

**Acceptance criteria:**

- The final-fit existence question is answered explicitly with evidence.
- Forecast-output reconstruction is dispositioned as Contract 11 work, not
  re-implemented here.

**Validation:**

- Perturbation tests over every offset, parameter, and calibration path;
  artifact-existence check with hash evidence.

### Task 4 — Findings, verification, and publication

**Changes:**

- Classify every finding with severity (`blocker/major/minor/info`),
  artifact disposition
  (`eligible_for_next_contract/historical_evidence_only/prohibited_until_closed`),
  `closure_state` (`open`/`closed`/`incorporated_into_contract_11`),
  required action, closure criteria, and blocking dependencies — including
  the two seeded structural findings. Severity/disposition describe the
  defect and artifact use; `closure_state` alone drives the Contract 11 gate.
- Run the local full audit first and review every generated finding. Then
  perform the evidence-bound Preview apply with `audit-manifest.json`
  written last carrying `finalized: true`, `overall_disposition`, exact
  parent raw hashes, and a digest derived from the three published evidence
  documents and their identity. Final publication rejects provisional
  severities/dispositions, open required fields, failed integrity checks,
  and preflight state.
- Run the audit verifier against the published prefix: it must require final
  state, recompute all published hashes and gate arithmetic, and reread and
  hash the exact parent manifests. Publication validity (manifest–verification
  agreement) and the Contract 11 gate (finding closure) are separate
  decisions: validity is required for a legitimate publication; closure
  determines whether Contract 11 may start. The verification record itself
  stays local/session-log evidence carrying the verified manifest hash —
  the contract publishes exactly four outputs, never a fifth file.
- Enforce the declared `rejected_seasons: [2020, 2026]` in every 10b check;
  development seasons remain 2015–2019 and 2021–2025.
- Publish the four outputs (compact per umbrella), then the human-readable
  report under `docs/research/`, then lifecycle/roadmap/index/session-log updates.
- Evaluate and record publication validity and the Contract 11 entry gate
  explicitly and separately.

**Acceptance criteria:**

- Contract 10 is complete when evidence is published and every finding has a
  severity, disposition, `closure_state`, and closure criterion — even with open blockers.
- A publication is valid only when the audit manifest and the independent
  audit-verification record agree exactly; validity never implies Contract 11
  permission.
- R2 writes confined to the new Preview audit prefix; production, Neon,
  catalog, web, V4, and the four parents unchanged.

**Validation:**

- Full Python suite (`-W error`), scoped Ruff, schema/contract validation,
  strict MkDocs, `git diff --check`; idempotent repeat returns
  `already_applied`; R2-write confinement check.

## Testing strategy

Same gates as 10a plus execution coverage: full-corpus count/digest
agreement tests, perturbation invariance across all paths, final-fit
existence evidence test, manifest-last ordering test, and gate-arithmetic
tests (every finding dispositioned; gate evaluates exactly per umbrella).

## Risks and edge cases

- Full-corpus streaming cost — bounded by season/cutoff partitions; apply
  and verification each carry a 600s cap (compact outputs, no corpus
  recomputation); overruns block publication pending a performance amendment.
- A failed independence check changes permitted use, not historical bytes.
- Blockers remaining open is a normal completion state — it closes Contract
  10 and holds Contract 11, rather than forcing silent resolution.

## Definition of done

- [x] Reviewed evidence-bound 10b apply passes (600s cap).
- [x] Four versioned outputs published; manifest written last with
  `finalized: true`, `overall_disposition`, exact parent raw hashes,
  `production_activation_authorized: false`, and the evidence-derived digest.
- [x] Independent re-read agrees exactly (publication valid); idempotent repeat
  returns `already_applied` on full identity + digest + parent + output-hash match.
- [x] Every finding has severity, disposition, `closure_state`, and closure criteria.
- [x] Publication validity and the Contract 11 gate evaluated and recorded separately; report and lifecycle docs updated.
- [x] All validation green; `git diff --check` clean.

## Amendments

**Conditional-results clarification (2026-09-20):** Implemented 11A and
approved 12A may pursue a separately bounded
`conditional_historical_results_only` scorecard from 10A lineage/preflight
evidence. They neither replace this full-corpus audit nor clear its findings.
Completion of 10B remains required evidence for foundation readiness, full
forecast eligibility, final Contract 12, and every 2026 gate. No audit finding
is closed by this documentation amendment.

Mechanical fixes stay in-contract. New blockers requiring code,
methodology, schema, or artifact changes need separately approved corrective
contracts — never implemented inside the audit.
