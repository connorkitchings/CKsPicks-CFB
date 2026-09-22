# V5 Historical-First Documentation and Contract Reset

- **Status:** Implemented
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved this exact plan for implementation on 2026-09-18.
- **Implementation log:** `session_logs/2026-09-18/04-v5-historical-first-documentation-reset.md`
- **Commit policy:** Separate documentation-contract commit; user controls Git operations.

## Goal

Make design correctness and historical validation through 2025 the active V5
priority. Correct claims that exceed the completed verification, preserve all
recorded artifacts and historical evidence, and defer 2026 application until
the historical foundation is reviewed and explicitly accepted.

## Current State

V5 development is restricted to 2015-2019 and 2021-2025, with 2020 excluded.
The R6 measurement and Contract 03 rating artifacts record those boundaries.
The Contract 04B forecast artifact exists, but its current verifier validates
the signed manifest, identities, and reference labels without independently
reconstructing offsets, features, bridge fits, calibration, selection, or
stored forecast outputs. It therefore cannot support the documented
computational-verification claim. Contract 05's verified historical rehearsal
tests shadow tooling with diagnostic synthetic predictions; it is not evidence
of forecast quality or live readiness.

## Proposed Approach

Keep the completed measurement, rating, forecast, and shadow records available
as dated historical evidence. Reopen only forecast eligibility and independent
computational verification. Make a full historical-foundation audit, forecast
verification closure, and historical-results/readiness review the ordered work
before any 2026 application. Do not change code, configurations, R2 artifacts,
V4 production, Neon, or serving state in this contract.

## Scope

### Included

- Current-authority documentation, V5 lifecycle/eligibility corrections, and
  focused authority regression tests.
- Draft Contracts 10-12 for the historical audit, verification closure, and
  readiness review.
- Deferral gates and re-review requirements for Contracts 06-09.

### Excluded

- Research execution, model selection, artifact writes, migrations, production,
  V4 changes, and 2026 application work.

## Implementation Tasks

### Task 1 — Align active V5 authority

Update the roadmap, common contract, contract index, onboarding summaries,
requirements, methodology, evaluation policy, and shadow runbook. State that
2025 is development evidence; every historical operation is cutoff-correct;
2026 application follows accepted historical readiness; frozen state updates,
retrospective replay, prospective evidence, and promotion have distinct roles.

**Acceptance criteria:** All current-authority pages name the historical audit
as next and refer readers to the canonical roadmap. Historical identities and
session logs remain unchanged.

### Task 2 — Correct eligibility and defer application

Keep Contracts 02/03 implemented, retain 04A history, mark 04/04B In Progress,
and state why forecast eligibility remains incomplete. Keep 05 tooling
implemented without calling it predictive certification. Defer 06-09 behind
audit, verification, historical review, and explicit user acceptance.

**Acceptance criteria:** The index, common contract, roadmap, and affected
contracts agree on lifecycle and gate semantics.

### Task 3 — Create the historical-first queue

Add Draft Contracts 10-12 with exact dependencies, allowed writes, evidence,
validation, amendment process, and completion gates.

**Acceptance criteria:** 10 audits the full measurement-to-forecast chain; 11
requires independent computational reconstruction; 12 reports historical
results and a non-automatic readiness recommendation.

### Task 4 — Protect the authority boundary

Update authority tests to reject stale next-task claims, unconditional 04B
certification, and any treatment of rehearsal/replay as predictive or
prospective evidence.

**Acceptance criteria:** Focused authority tests, strict MkDocs, scoped lint,
and `git diff --check` pass.

## Risks and Amendment Rules

This contract changes documentation and eligibility only. It must not imply an
artifact is invalid or alter its bytes. A finding that changes V5 methodology,
interfaces, or acceptance criteria requires a new approved implementation
contract. Mechanical wording and link corrections may be recorded in this
contract's implementation log.

## Definition of Done

- [x] Current authority pages agree on historical-first V5 status.
- [x] Forecast-verification limitation and 04/04B lifecycle are explicit.
- [x] Contracts 10-12 are Draft and correctly ordered.
- [x] Contracts 06-09 are deferred behind historical readiness and re-review.
- [x] Authority tests, MkDocs, lint, and `git diff --check` pass.
- [x] Session log is complete and this contract is marked `Implemented`.
