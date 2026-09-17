# V5-05C: Diagnostic Rehearsal, Verification, and Runbook

- **Status:** Draft
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** Pending user approval of this execution decomposition.
- **Implementation log:** Pending; create `session_logs/<execution-date>/NN-v5-05c-rehearsal-verification-runbook.md`.
- **Commit policy:** Separate code checkpoint and certified-evidence documentation checkpoint; user executes Git.

## Goal

Implement Contract 05 Task 5 on the Phase 05A/05B foundation: run a full
historical diagnostic rehearsal (permanently ineligible for prospective
counting), independently verify readiness → replay → freeze → scoring →
counter end-to-end, publish the verified real-season readiness report (ready
or blocked with concrete reasons), and write the V5 shadow runbook with the
Contract 06 handoff. Closes umbrella V5-05 tooling.

## Current State and Entry Gate

Phases 05A and 05B must be **Implemented** with committed SHAs and reviewed
deterministic preflight evidence before 05C executes. Required interfaces: all
six schemas, `shadow_v1.yaml`, readiness/replay CLIs, freeze/score CLIs with
evidence-bound applies, ledger/counter.

This contract remains **Draft** until a separate explicit user approval after
05B certifies. V5-05 remains Approved and is not complete until this phase
certifies with the verified readiness report and runbook committed.

## Proposed Approach

Build the verifier-owned reconstruction module (no producer shadow imports —
same boundary as `forecast_verification.py`), the diagnostic rehearsal runner
with deliberate negative cases, and the real-season readiness assessment that
refreshes the same-day assessment doc with verified findings. Every rehearsal
output carries the permanent `diagnostic_only` class. Independent verification
recomputes timing, availability, population, predictions, scores, and counts
from source artifacts.

## Scope

### Included

- `shadow_verification.py` with AST-enforced producer-import boundary
- `verify_v5_shadow.py` CLI for end-to-end independent verification
- Full historical diagnostic rehearsal with negative cases and idempotent rerun
- Real-season readiness assessment refreshing
  `docs/research/2026-09-17-v5-live-readiness-assessment.md` with verified verdict
- `docs/ops/v5_shadow_runbook.md` with exact commands, refs, cutoffs, recovery,
  counter rules, and Contract 06 handoff
- Umbrella-05 closure documentation (plan index, roadmap checkpoint)

### Excluded

- Readiness/replay tooling (05A), freeze/score/ledger tooling (05B) — prerequisites
- Measurement/rating pipeline extension, prospective collection (Contract 06)
- Any V4, Neon, catalog, web, subscription, provider, scheduler change
- Public outputs or serving writes of any kind

## Architecture decisions

Inherit all 05A/05B interfaces unchanged: schemas, stage root, pinned
parents, `shadow_v1.yaml`, R2-only, `production_activation_authorized: false`.

**Verifier boundary:** `shadow_verification.py` may import only
`data_first_shadow_v1` (constants/schemas), `lake` (generic readers),
`data_first_phase2d` (signing), `schema_contracts`, `storage`. Must NOT import
`shadow` producer functions, any runner, or `offsets`/`heads`/`horizons`/
`calibration`. Enforced by an AST import-boundary test plus a
producer-perturbation test the verifier must catch.

**Rehearsal data:** pinned historical refs (2022–2025 seasons with complete
source/model lineage) — never live 2026 mutable state. Negative cases:
timing violation, <40 games, missing outcome, correction, immutable
collision, candidate-change reset. Every rehearsal record carries
`diagnostic_only = true`.

**Readiness refresh:** the real-season assessment re-runs 05A readiness logic
against currently available exact inputs and overwrites the verdict section of
`docs/research/2026-09-17-v5-live-readiness-assessment.md` with verified
findings (expected: `blocked` — no 2026 measurement/rating pipeline, Preview
lag). The historical evidence sections of that doc are preserved; only the
verdict, input inventory, and blocker list are refreshed.

## Affected Components and Interfaces

- New `src/cks_picks_cfb/forecast/shadow_verification.py`:
  `verify_shadow_artifact()` plus internal `_reconstruct_readiness()`,
  `_reconstruct_replay()`, `_reconstruct_freeze()`, `_reconstruct_scores()`,
  `_reconstruct_counter()`, `_compare_*` helpers; signed verifier manifest.
- New `scripts/research/run_v5_shadow_rehearsal.py`: `--season-range`,
  historical parent refs, negative-case flags; `diagnostic_only` enforced.
- New `scripts/research/verify_v5_shadow.py`: `--manifest-uri`,
  `--expected-code-sha`, `--environment preview`, parent URIs.
- Refresh `docs/research/2026-09-17-v5-live-readiness-assessment.md` (verdict
  + inventory + blockers only).
- New `docs/ops/v5_shadow_runbook.md`.
- New `tests/test_v5_shadow_verification.py`,
  `tests/test_v5_shadow_rehearsal.py`.
- Update umbrella-05 closure note, `docs/plans/index.md`, roadmap checkpoint.

## Implementation Tasks

### Task 1 — Independent shadow verifier

**Files:** `src/cks_picks_cfb/forecast/shadow_verification.py`,
`scripts/research/verify_v5_shadow.py`.

**Changes:** verifier-owned reconstruction of source availability, frozen
replay, freeze timing/population/predictions, scores, and ledger counts from
source artifacts; producer-perturbation sensitivity; tampered-bytes/wrong
parent rejection; signed verifier manifest (`verification/verifier-manifest.json`,
idempotent). Forbid producer imports via AST test.

**Acceptance criteria:**
- All stored outputs agree partition-by-partition; verifier manifest signed.
- Perturbed-producer, tampered-bytes, wrong-parent fixtures rejected with
  named errors.
- No producer import present (AST test passes).

**Validation:** focused verifier tests warnings-as-errors; CLI `--help`/compile.

### Task 2 — Diagnostic rehearsal

**Files:** `scripts/research/run_v5_shadow_rehearsal.py`.

**Changes:** full historical future-like rehearsal on pinned refs:
readiness → replay → freeze validation → stabilized scoring → counter
reconstruction, exercising all six negative cases; `diagnostic_only`
permanent class on every output; idempotent rerun byte-identical. No public
outputs or serving writes.

**Acceptance criteria:**
- All negatives disposed with correct reasons; counter shows zero qualifying
  (diagnostic class can never count).
- Rerun byte-identical; verifier confirms end-to-end.

**Validation:** rehearsal integration test warnings-as-errors; independent
verify pass on rehearsal outputs.

### Task 3 — Readiness report, runbook, closure

**Files:** `docs/research/2026-09-17-v5-live-readiness-assessment.md` (refresh),
`docs/ops/v5_shadow_runbook.md` (new), umbrella-05 closure note, plan index,
roadmap.

**Changes:** re-run 05A readiness logic read-only against current exact
inputs; refresh verdict/inventory/blockers (expected `blocked`); preserve
historical sections. Runbook: exact commands with pinned refs, cutoffs,
freeze/score sequencing, failure recovery, counter rules, evidence-class
definitions, Contract 06 handoff (tooling refs + readiness verdict + what 06
must re-verify per slate). No scheduler; no auto-collection. Close umbrella
V5-05 only after rehearsal verified + report + runbook committed.

**Acceptance criteria:**
- Report names concrete available inputs, fallbacks, and blockers; verdict
  reproducible from cited refs.
- Runbook commands execute verbatim in a fresh rehearsal checkout.
- 06 handoff lists exact tooling refs and per-slate re-verification duties.

**Validation:** strict mkdocs build; `git diff --check`; runbook command
dry-run.

### Task 4 — Phase 05C certification execution

**Changes:** on a clean committed worktree: rehearsal preflight → review →
evidence-bound apply → independent verify → idempotent repeat; then readiness
refresh + runbook committed as the documentation checkpoint. Record run IDs,
SHAs, cutoffs, digests, verdict, URIs.

**Acceptance criteria:** all four lifecycle steps pass under identical
lineage; documentation checkpoint committed separately by the user.

**Validation:** full warning-as-error suite + coverage; scoped ruff; `ruff
check .`; `make contracts-check`; production-boundary regression (zero
V4/Neon/web diffs); R2 inventory (Preview shadow paths only).

## Testing Strategy

- Unit: verifier reconstruction per record type; negative-case dispositions;
  import boundary (AST); producer perturbation.
- Integration: complete rehearsal dry-run/apply/verify/reapply with all six
  records + verifier manifest.
- Regression: 05A/05B suites; full warning-as-error suite.
- Recovery: interrupted-run re-execution under same identity; collision
  handling.

## Risks and Edge Cases

- **Rehearsal/runtime cost.** Historical replay across multiple seasons with
  two horizons is heavy; stream by partition, bound progress, checkpoint
  counts. Interrupted runs re-execute — never resume partial prefixes into
  eligibility.
- **Verifier false agreement.** Only generic utilities shared; any shared
  timing/population/scoring math is a defect.
- **`blocked` misread as failure.** A verified `blocked` report with rehearsed
  tooling is the contractually complete outcome; it only means 06 cannot
  collect eligible evidence yet.
- **Week 3 live state.** The real-season assessment must cite frozen Week 3
  and pending close without mutating anything.

## Definition of Done

- [ ] Independent verifier reconstructs all six records without producer imports.
- [ ] Diagnostic rehearsal (with negatives) verified end-to-end + idempotent.
- [ ] Real-season readiness report refreshed with verified verdict and reasons.
- [ ] Shadow runbook complete with verbatim commands and 06 handoff.
- [ ] No rehearsal counts prospectively; zero production/Neon/web writes proven.
- [ ] All quality gates pass; session logs complete.
- [ ] Umbrella V5-05 Implemented; Contract 06 entry state recorded (ready or still-blocked).

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be
logged if output order, bytes, plans, digests, identities, and acceptance
criteria are unchanged. Any change to sources, math, timing rules, population
gates, schemas, eligibility, verification independence, or production
boundaries requires user-approved replanning.
