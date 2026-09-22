# V5: Contract 12 Acceptance and 07–09 Re-Review for the 2026 Extension

- **Status:** Implemented
- **Created:** 2026-09-22
- **Planner:** Sol
- **Approval source:** User approved this plan and its sequencing decisions in the 2026-09-22 planning session ("proceed"): (1) Contract 12 historical readiness review accepted 2026-09-22; (2) Contract 01 executes first; (3) due weekly V4 ops (Week 3 close, Week 4 prepare/publish/freeze) fold in as the Contract 07 entry-gate prerequisite; (4) first Contract 06 slate target is Week 5 (~Thu Oct 1 first kickoff), not Week 4.
- **Implementation log:** `session_logs/2026-09-22/03-v5-acceptance-and-07-09-rereview.md`
- **Commit policy:** Separate plan commit; user executes Git.

## Goal

Unblock the V5 2026 extension (Contracts 07 → 08 → 09 → 06) by (a) recording the
user's explicit acceptance of the Contract 12 historical readiness review and
(b) re-reviewing Contracts 07–09 against the corrected, certified lineage
produced by the 2026-09-21 11B/11C/11D re-derivation, lifting their
historical-first deferrals. Observable success: the plans index and roadmap show
Contracts 07–09 as re-reviewed and execution-authorized with exact corrected
parents, and the acceptance decision is durably recorded with citations.

This contract is documentation/lifecycle work only. Executing 07, 08, 09, and
06 remains governed by those (amended) contracts; weekly ops follow the
runbooks.

## Current State

The historical-first lane completed 2026-09-21:

- Repair v2 (`repair-v2-20260909T1417Z`) unchanged; its **verifier** was
  corrected (independent Repair verifier v3, zero producer imports), closing
  Finding 001.
- Measurements were re-materialized as
  `possession-v1-measurements-20260921-r9` (certification SHA `fc26a3d0…`),
  incorporating the 4-part scoring-extraction correction; score-ledger excess
  keys = 0 across all 10 seasons, closing Finding 003.
- Ratings were re-certified as
  `possession-v1-ratings-20260921-11d59ee-r9cert` (retained manifest SHA
  `2f1cdc5f…`) with **no selection flip**: `ppp__rho_0_60__exposure` retained.
- The forecast bridge was re-certified as
  `forecast-v1-20260921-5afd577-11c` including the **through-2025 final fit**
  (expanding horizon, alpha-10 reference heads, final calibration), closing
  Finding 004; independent verification manifest `4cfe5ef8…`
  (`final_fit_verified: true`) closed Finding 002.
- Contract 12 issued `accepted_for_prospective_evaluation` under run
  `readiness-v1-20260921-scorecard` (manifest SHA `a8351fb3…`); report at
  `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`.

Contracts 07–09 (Approved 2026-09-18, implementation deferred) still pin the
superseded lineage and carry deferral clauses that are now satisfied. Their
frozen selections are unchanged by the correction, so the re-review re-points
identities — it does not alter designs.

Weekly ops state (2026-09-22): Week 3 (`2026w3-68fe6a815bd6`) is frozen but
not yet closed; Week 4 is not yet published. Contract 07's entry gate requires
Preview 2026 Silver synced through the latest completed week.

## Proposed Approach

Amend Contracts 07, 08, and 09 in place (common amendment process) to bind the
corrected certified parents, require the corrected Repair verifier for any
Repair-2026 verification, explicitly apply the through-2025 final-fit bridge
and calibration for 2026 forecasts, and record gate satisfaction lifting the
deferrals. Record the Contract 12 acceptance in the plans index, roadmap, and
AGENTS.md checkpoint with citations. Document the authorized execution
sequence, including the Week-5 first-slate target and the Week-4-finals
refresh pass.

All run identities, manifest URIs, and SHAs referenced by the amendments must
be resolved from the cited certified records (session logs 2026-09-21
02/03/07/08/09/11 and the 11B/11C/11D plan contracts), never hand-typed.

### Corrected lineage binding

| Layer | Superseded pin (in 07–09 today) | Re-reviewed pin (certified 2026-09-21) |
| --- | --- | --- |
| Repair parent | `repair-v2-20260909T1417Z` | unchanged; independent verification must use Repair verifier v3 (Finding 001 closure) |
| Possession measurements | `possession-v1-measurements-20260915-18fb0aa-r6` | `possession-v1-measurements-20260921-r9` (certification SHA `fc26a3d0…`) |
| Ratings / frozen winner | `possession-v1-ratings-20260917-d029526-cert` | `possession-v1-ratings-20260921-11d59ee-r9cert` (manifest SHA `2f1cdc5f…`; selected `ppp__rho_0_60__exposure`, no flip) |
| Forecast bridge | `forecast-v1-20260917-4600ddd-04b` | `forecast-v1-20260921-5afd577-11c` (11D verifier `4cfe5ef8…`, `final_fit_verified: true`); 2026 application uses the through-2025 final-fit heads + final calibration |

## Scope

### Included

- Amendment sections added to Contracts 07, 08, 09 recording the re-review,
  corrected parents, and lifted deferrals.
- Acceptance decision record: plans index Contract 12 row, roadmap checkpoint,
  AGENTS.md status block.
- Execution-sequence documentation (Contract 01 first; ops prerequisite; W5
  first slate; W4-finals refresh pass) in this contract and the roadmap
  checkpoint.

### Excluded

- Any code change, run execution, R2 write, Neon/production/web write.
- Execution of Contracts 07/08/09/06 (governed by their amended contracts).
- Contract 01 execution (governed by its existing approved contract).
- Weekly V4 ops (runbook fast-path sessions).
- Any betting, staking, promotion, or publication decision.

## Affected Components and Contracts

- `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md` [MODIFY]
- `docs/plans/2026-09-18/08-v5-2026-rating-state-replay.md` [MODIFY]
- `docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md` [MODIFY]
- `docs/plans/index.md` [MODIFY: Contract 12 acceptance; 07/08/09 re-reviewed rows]
- `docs/planning/data-first-football-forecasting-roadmap.md` [MODIFY: current checkpoint]
- `AGENTS.md` [MODIFY: 2026 season execution status checkpoint]
- This contract and its implementation session log.

## Implementation Tasks

### Task 1 — Record Contract 12 acceptance

**Files:**

- `docs/plans/index.md`
- `docs/planning/data-first-football-forecasting-roadmap.md`
- `AGENTS.md`

**Changes:**

- Add to the Contract 12 index row (and roadmap checkpoint): user explicitly
  accepted the historical readiness recommendation
  `accepted_for_prospective_evaluation` on 2026-09-22, citing the report
  (`docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`)
  and scorecard run `readiness-v1-20260921-scorecard` (manifest `a8351fb3…`).
- Update the AGENTS.md V5 checkpoint paragraph to the post-acceptance state:
  historical lane complete and accepted; 07–09 re-reviewed and authorized;
  first Contract 06 slate targets Week 5; V4 production unchanged.

**Acceptance criteria:**

- Acceptance is unambiguous: what was accepted, by whom, when, on what record.
- Documentation-authority tests that pin statuses still pass (update pinned
  expectations if they assert deferred status text for 07–09).

**Validation:**

- `uv run pytest tests/test_data_first_documentation_authority.py` (and any
  lifecycle tests pinning 07–09/12 rows); `uv run mkdocs build --strict --quiet`.

### Task 2 — Amend Contract 07 (repair and measurement extension)

**Files:**

- `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md`

**Changes (Amendment 1 — re-reviewed lineage and lifted deferral):**

- Re-point the historical measurement reference from
  `possession-v1-measurements-20260915-18fb0aa-r6` to
  `possession-v1-measurements-20260921-r9`; the 2026 run must use the **same
  adjustment procedure, floors, fallbacks, exposure settings, and corrected
  scoring extraction as r9** (the 4-part correction that closed Finding 003).
- Task 2 (Repair-2026): independent verification must use the corrected
  independent Repair verifier (v3) per the Finding 001 closure; the historical
  anchor `repair-v2-20260909T1417Z` is unchanged.
- Record gate satisfaction: Contracts 10–12 Implemented, user acceptance
  recorded 2026-09-22, re-review complete per this contract — the
  historical-first deferral is lifted and execution is authorized.
- Keep every remaining guarantee (2020 forbidden, `live` timing scoped to 2026,
  `production_activation_authorized: false`, no Neon/production/web writes).

**Acceptance criteria:**

- No remaining normative reference binds 2026 work to R6 or the pre-correction
  extraction; deferral text is superseded with an explicit dated lift.

**Validation:**

- Documentation-authority/lifecycle tests; `uv run mkdocs build --strict --quiet`.

### Task 3 — Amend Contract 08 (rating-state replay)

**Files:**

- `docs/plans/2026-09-18/08-v5-2026-rating-state-replay.md`

**Changes (Amendment 1 — re-reviewed lineage and lifted deferral):**

- The frozen winner `ppp__rho_0_60__exposure` is unchanged; its certified
  identity is re-pointed from `possession-v1-ratings-20260917-d029526-cert` to
  `possession-v1-ratings-20260921-11d59ee-r9cert` (manifest SHA `2f1cdc5f…`),
  with the recorded no-selection-flip evidence cited.
- Replay consumes the certified 2026 measurement manifest from amended 07
  (whose settings inherit r9); priors apply the frozen carryover structure
  with no 2026-outcome fitting.
- Record gate satisfaction and lift the deferral (same dated note as Task 2).

**Acceptance criteria:**

- No remaining normative reference binds replay to the superseded rating run;
  replay-only guarantees (no refit, no re-selection) unchanged.

**Validation:**

- Documentation-authority/lifecycle tests; `uv run mkdocs build --strict --quiet`.

### Task 4 — Amend Contract 09 (forecast generation and live readiness)

**Files:**

- `docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md`

**Changes (Amendment 1 — re-reviewed lineage, final-fit application, lifted deferral):**

- Re-point the frozen bridge from `forecast-v1-20260917-4600ddd-04b` to
  `forecast-v1-20260921-5afd577-11c` (11D verification `4cfe5ef8…`,
  `final_fit_verified: true`).
- Make explicit: 2026 forecasts apply the **through-2025 final-fit heads
  (alpha-10, expanding horizon) and final calibration variances** — not the
  2024-max fold heads. Nothing is fitted on 2026 outcomes.
- First readiness target: the **Week 5** slate (~Thu Oct 1 first kickoff);
  readiness for Week 4 is explicitly not required and a skipped Week 4 slate
  is expected, not a failure.
- Record gate satisfaction and lift the deferral (same dated note).

**Acceptance criteria:**

- Bridge binding, final-fit application, and W5 readiness target are explicit;
  application-only guarantees unchanged.

**Validation:**

- Documentation-authority/lifecycle tests; `uv run mkdocs build --strict --quiet`.

### Task 5 — Record the authorized execution sequence and close out

**Files:**

- `docs/planning/data-first-football-forecasting-roadmap.md`
- `docs/plans/index.md`
- Implementation session log for this contract.

**Changes:**

- Roadmap checkpoint: replace the 2026-09-20 critical path with the authorized
  sequence —
  1. Contract 01 (existing approved contract) executes first.
  2. Weekly ops: close Week 3 (production) → `prepare-week` Week 4 (Preview;
     this satisfies 07's entry gate) → publish + freeze Week 4 per runbook.
  3. Execute 07 (code amendment → Repair-2026 → 2026 measurements W0–W3).
  4. Execute 08 (priors → replay W0–W3 → verify).
  5. After Week 4 finals stabilize (~Sep 28), re-run 07/08 through W4 under
     new run-IDs so Week 5 forecasts use current states.
  6. Execute 09 (2026 forecasts via final-fit bridge → verify → readiness
     `ready` on the Week 5 slate).
  7. Contract 06 begins: freeze at T−2h before the first Week 5 kickoff
     (≥40 paired games), then weekly cadence (score +24h, refresh chain,
     readiness, freeze); six qualifying slates (W5–W10 target) → Task 4
     recommendation. A separate Phase 7 promotion contract remains required.
- Update the plans index with this contract's row and 07–09 statuses.
- Session log; mark this contract Implemented when all tasks pass.

**Acceptance criteria:**

- Sequence is decision-complete for Terra handoffs; each phase names its
  governing contract; no phase implies production writes or promotion.

**Validation:**

- `uv run python contracts/validation.py`; `uv run mkdocs build --strict --quiet`;
  `git diff --check`; full `uv run pytest` if any pinned lifecycle expectations
  changed.

## Testing Strategy

Documentation/lifecycle only: documentation-authority and lifecycle tests,
`uv run python contracts/validation.py`, strict MkDocs, `git diff --check`. No
product code, no new unit tests, no R2/Neon writes.

## Risks and Edge Cases

- Pinned lifecycle tests may assert the old deferred statuses; update
  expectations to the amended statuses in the same change (precedent: 11B
  lifecycle-test update).
- SHAs/URIs must be copied from the cited certified records, never hand-typed;
  truncated forms in this contract are references, not authoritative values.
- Lifting deferrals authorizes execution of 07–09 only; it does not create
  prospective evidence, alter V4 production, or satisfy Contract 06's gates.
- CFBD finals lag (24–48h) may delay the W4-finals refresh; the W5 freeze
  window (~Oct 1) remains the protected boundary, and a late refresh must
  degrade to W3 states plus a recorded limitation rather than rushed finals.

## Definition of Done

- [x] Contract 12 acceptance recorded with date, approver, and citations.
- [x] Contracts 07/08/09 amended with corrected parents, final-fit application
      (09), dated deferral lifts, and unchanged guarantees.
- [x] Index, roadmap, and AGENTS.md checkpoint reflect the post-acceptance
      state and authorized execution sequence.
- [x] `uv run python contracts/validation.py`, strict MkDocs, documentation
      tests, and `git diff --check` pass.
- [x] Implementation session log created; this contract marked Implemented.

## Amendments

None.
