# V5 Authority Reconciliation and Critical Path

- **Status:** Implemented
- **Created:** 2026-09-20
- **Planner:** Sol
- **Approval source:** User approved the proposed documentation and planning package with “go” on 2026-09-20.
- **Implementation log:** `session_logs/2026-09-20/02-v5-authority-reconciliation-and-critical-path.md`
- **Commit policy:** Separate documentation/contract commit; user controls Git operations.

## Goal

Reconcile every current-authority V5 entry point with the completed Contract 10B
audit, implemented Contract 11A verification, and approved Contract 12A
scorecard plan. Publish one unambiguous critical path from the current checkpoint
to conditional historical results, full historical readiness, 2026 application,
prospective evidence, and any later promotion review.

Observable success means that current-authority pages and their regression tests
agree on all lifecycle states and gates; historical records remain unchanged;
Contract 12A is clearly ready for implementation; and a new Draft diagnostic
contract defines how Findings 001 and 003 will be investigated before a
corrective execution contract is designed.

## Current State

The worktree was clean on `main` at `7e863f6` during planning. That commit
approves Contract 12A. Contract 10/10B is Implemented with valid Preview
publication `historical-audit-10b-20260919-full`; all four findings remain open
blockers and `contract11_permitted: false`. Contract 11A is Implemented under
`conditional-v1-20260919-9265314-11a` and independently reconstructed all six
forecast outputs, but its permitted use is only
`conditional_historical_results_only`. Contract 12A is Approved and is the
immediate executable task for a V5-only conditional historical scorecard.

The focused documentation-authority suite currently records 36 passing tests
and one failure: it still requires Contract 12A to be Draft. The same stale
checkpoint appears in several current-authority pages:

- the roadmap and plan index call Contract 12A Draft;
- the common V5 contract calls 10B In Progress and 11A/12A Draft;
- onboarding summaries describe 10B and 11A as future work;
- the roadmap's ordered-future-work paragraph lists completed work as pending;
- some summaries still state that no independent forecast reconstruction has
  occurred, without distinguishing successful conditional 11A reconstruction
  from unresolved full forecast eligibility.

The full-readiness critical path remains blocked by:

1. Finding 001 — Repair v2 verification imports producer `compute_repair`.
2. Finding 003 — 81 score-ledger team-game keys exceed repaired final scores.
3. Finding 002 — full forecast eligibility has not been closed, despite the
   narrower successful 11A reconstruction.
4. Finding 004 — no final forecast fit trained through 2025 exists.

The cause of Finding 003 is not yet known. It may be a Repair-layer defect, a
measurement/scoring-attribution defect, or a mixed issue. Choosing a repair
artifact identity or descendant rebuild scope before diagnosis could duplicate
work and incorrectly bind the independent Repair verifier required by Finding
001.

This is documentation and planning work only. No cloud data access is required;
R2, Neon, production, V4, model configuration, and immutable artifacts remain
unchanged.

## Proposed Approach

Perform a bounded authority reconciliation rather than rewriting every
historical document. Update current entry points, canonical status pages,
active contracts, and authority regression tests. Preserve session logs,
completed contract narratives, artifact identities, and audit findings as dated
evidence.

Represent progress with distinct finish lines:

1. **Conditional historical scorecard:** implement already-approved 12A.
2. **Historically eligible V5 candidate:** diagnose and correct Findings
   001/003, execute full Contract 11 including a through-2025 final fit, then
   complete and explicitly accept final Contract 12.
3. **2026/prospective readiness:** re-review and execute deferred Contracts
   07–09, then collect six qualifying pre-kickoff frozen slates under Contract
   06.
4. **Production replacement:** create and approve a separate promotion contract
   only after the prospective evidence gate.

Create a separate Draft diagnostic contract for Findings 001/003. It must be
read-only by default and must determine the responsible layer and replacement
blast radius before specifying corrective execution. It must coordinate the
Repair independence work with whichever Repair identity survives the ledger
correction, avoiding certification of an artifact that will immediately be
replaced.

## Scope

### Included

- Reconcile active V5 lifecycle, evidence, permitted-use, and next-step claims.
- Update the dated current checkpoint to 2026-09-20 where appropriate.
- Distinguish successful 11A conditional reconstruction from unresolved full
  Contract 11 eligibility and final-fit work.
- Mark Contract 12A Approved everywhere and identify it as the immediate
  independent execution task.
- Preserve the four open audit findings and `contract11_permitted: false`.
- Publish the ordered finish lines and critical path above.
- Create Draft `02-v5-foundation-blocker-diagnosis.md` with a decision-complete
  diagnostic boundary for Findings 001/003.
- Strengthen documentation-authority tests so lifecycle and gate drift fails
  loudly.
- Create the Terra implementation session log and update this contract to
  Implemented only after validation passes.

### Excluded

- Implementing Contract 12A or calculating scorecard values.
- Reading or writing R2, Neon, catalog, production, web-serving state, or V4.
- Diagnosing the 81 keys during this documentation implementation.
- Repairing data, changing scoring attribution, rebuilding descendants, or
  closing any audit finding.
- Approving or executing the new diagnostic contract.
- Starting full Contract 11, final Contract 12, Contracts 06–09, or promotion.
- Rewriting historical session logs or changing immutable artifact identities.

## Affected Components and Contracts

Current-authority entry points and status pages:

- `AGENTS.md`
- `README.md`
- `.agent/CONTEXT.md`
- `.codex/QUICKSTART.md`
- `docs/index.md`
- `docs/planning/data-first-football-forecasting-roadmap.md`
- `docs/planning/roadmap.md`
- `docs/plans/index.md`
- `docs/modeling/rating_system_requirements.md`
- `docs/modeling/evaluation.md`
- `docs/modeling/possession_rating_methodology.md`
- `docs/modeling/measurement_catalog.md`
- `docs/architecture/repository_boundaries.md`

Active contract surfaces:

- `docs/plans/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md`
- `docs/plans/2026-09-18/10-v5-historical-foundation-audit.md`
- `docs/plans/2026-09-18/11-v5-forecast-verification-closure.md`
- `docs/plans/2026-09-18/12-v5-historical-results-and-readiness-review.md`
- `docs/plans/2026-09-19/11a-v5-conditional-forecast-verification.md`
- `docs/plans/2026-09-19/12a-v5-conditional-historical-scorecard.md`
- `docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md` (new, Draft)

Regression coverage:

- `tests/test_data_first_documentation_authority.py`

Only files with a current-authority statement that requires correction should
change. A listed file with no stale statement remains untouched.

## Implementation Tasks

### Task 1 — Reconcile the canonical checkpoint

**Files:**

- `docs/planning/data-first-football-forecasting-roadmap.md`
- `docs/plans/index.md`
- `docs/plans/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md`
- affected active contracts listed above

**Changes:**

- Record 10B and 11A as Implemented and 12A as Approved.
- Replace completed-work-as-future wording with the current sequence.
- State that 11A proved exact conditional reconstruction but did not close
  Findings 001/003, restore 04/04B eligibility, create a through-2025 fit, or
  authorize 2026 work.
- Keep all four findings open and keep full Contract 11 blocked.
- Identify 12A as executable independently of the full-readiness repair lane.
- Add the four finish lines and their exact gates.

**Acceptance criteria:**

- Roadmap, index, common contract, and active contracts agree exactly on status,
  permitted use, blockers, and next task.
- No page describes 10B or 11A as pending, 12A as Draft, or conditional evidence
  as full eligibility.
- Historical identities and audit dispositions are unchanged.

**Validation:**

- Targeted text search for stale lifecycle phrases.
- Documentation-authority tests.

### Task 2 — Align onboarding, architecture, and modeling guidance

**Files:**

- `AGENTS.md`
- `README.md`
- `.agent/CONTEXT.md`
- `.codex/QUICKSTART.md`
- `docs/index.md`
- `docs/planning/roadmap.md`
- affected modeling/architecture pages listed above

**Changes:**

- Update the current checkpoint without converting historical sections into
  current authority.
- Preserve V4 as production champion and the original Phase 4B prohibition.
- Explain the conditional/full-readiness distinction consistently.
- Link every summary back to the canonical data-first roadmap and plan index.
- State that 2025 remains development evidence and six future qualifying slates
  remain necessary before a promotion review.

**Acceptance criteria:**

- A reader entering through any supported onboarding page reaches the same
  current state and ordered next steps.
- No wording implies that implementing 12A clears an audit finding or advances
  the prospective counter.
- Operational runbooks and V4 production claims are not changed unless a stale
  cross-link or V5 summary requires correction.

**Validation:**

- Entry-point parameterized authority tests.
- Strict MkDocs link/build validation.

### Task 3 — Create the Draft foundation-blocker diagnostic contract

**File:**

- `docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md`

**Changes:**

Create a full Draft contract with no execution authorization. It must require:

1. Exact-hash revalidation of the 10B finding record, Repair v2, and R6
   measurement/scoring-ledger parents before analysis.
2. Read-only reconstruction of all 81 excess keys from source scoring events,
   repaired finals, participants, possession eligibility, scoring category,
   regulation/overtime classification, and duplicate/split attribution.
3. A complete cause taxonomy and affected-key digest, with bounded examples but
   no silent exclusion or threshold relaxation.
4. A determination of whether the correction belongs to Repair, measurement
   attribution, both layers, or a justified finding-disposition amendment.
5. An independent Repair verification design that never imports or calls
   producer computation, with an import-boundary check and behavioral matrix.
6. A lineage impact graph naming every artifact that would need a new identity
   under each confirmed cause, including measurements, ratings, forecasts,
   11A/12A evidence, and any final fit.
7. A recommendation for one subsequent corrective execution contract with exact
   parents, outputs, verification, idempotency, and re-audit requirements.

The diagnostic contract must prohibit artifact replacement, R2 apply, finding
closure, threshold changes, and descendant rebuilds. It may permit read-only
Preview access only when later explicitly approved and when environment checks
pass.

**Acceptance criteria:**

- The Draft contract leaves the diagnosis mechanics decision-complete but does
  not prejudge the responsible layer.
- Finding 001 work is sequenced against the Repair identity expected to survive
  Finding 003 correction.
- The future corrective contract cannot be executed until the diagnosis report
  fixes the actual blast radius.

**Validation:**

- Contract metadata/lifecycle review.
- Link and terminology checks.

### Task 4 — Strengthen authority regression coverage

**File:**

- `tests/test_data_first_documentation_authority.py`

**Changes:**

- Require 10B and 11A Implemented and 12A Approved.
- Require every canonical page to preserve
  `conditional_historical_results_only`, the four open findings, the blocked
  full-11 gate, and the immediate 12A task.
- Reject stale states: 10B In Progress, 11A Draft/future, 12A Draft, or claims
  that no independent reconstruction has occurred at all.
- Reject the opposite overstatement: 11A restores forecast eligibility, clears
  findings, supplies a through-2025 final fit, authorizes 2026, or creates
  prospective evidence.
- Require the diagnostic contract to remain Draft and non-authorizing.

**Acceptance criteria:**

- The pre-existing 12A lifecycle failure is corrected.
- Both stale-understatement and conditional-overstatement fixtures fail as
  intended.
- Historical-evidence preservation tests remain green.

**Validation:**

- `uv run pytest -q tests/test_data_first_documentation_authority.py`
- `uv run ruff check tests/test_data_first_documentation_authority.py`

### Task 5 — Close the documentation implementation

**Files:**

- this contract
- the Terra implementation session log

**Changes:**

- Record actual files changed and exact validation results.
- Mark this contract Implemented only when all acceptance criteria pass.
- Leave the new blocker-diagnosis contract Draft.
- Provide separate copy-ready handoffs for approved 12A implementation and for
  later user review/approval of the diagnostic contract.

**Acceptance criteria:**

- The worktree contains only scoped documentation/test changes plus the session
  log.
- No computational, configuration, artifact, database, production, or V4 state
  changes occurred.

**Validation:**

- `uv run pytest -q tests/test_data_first_documentation_authority.py`
- `uv run ruff check tests/test_data_first_documentation_authority.py`
- `uv run python contracts/validation.py`
- `make contracts-check`
- `uv run mkdocs build --strict --quiet`
- `git diff --check`

## Testing Strategy

Use the focused documentation-authority suite as the semantic gate and strict
MkDocs as the structural/link gate. Run scoped Ruff for the changed Python test,
the repository contract validators for shared-contract drift, and
`git diff --check` for formatting hygiene. Do not run research pipelines or use
R2 merely to restate already signed evidence; exact identities come from the
implemented contracts and 10B/11A reports.

## Risks and Edge Cases

- **Conditional/full conflation:** successful 11A reconstruction must not be
  described as full artifact eligibility.
- **Premature repair design:** the 81-key cause is unknown; the diagnostic plan
  must not choose Repair versus measurement correction in advance.
- **Duplicated certification:** completing Finding 001 against an artifact that
  Finding 003 later replaces would waste work and create ambiguous authority.
- **Historical rewriting:** dated logs and superseded contracts may accurately
  describe prior states and should not be mass-edited.
- **Status without capability:** Approved 12A means executable, not implemented;
  it supplies no metrics until its full evidence-bound workflow passes.
- **Production drift:** Week 3 and later weekly operations are governed by their
  runbooks and separate logs; this V5 documentation task must not infer a new
  live-production state.

## Definition of Done

- [x] Every current-authority V5 page agrees on the 2026-09-20 checkpoint.
- [x] Contract 12A is consistently Approved and immediately executable.
- [x] Contracts 10B/11A are consistently Implemented; all four findings remain
  open and full Contract 11 remains blocked.
- [x] The conditional, historical-readiness, prospective, and promotion finish
  lines are explicit and correctly gated.
- [x] Draft blocker-diagnosis Contract 02 is complete and non-authorizing.
- [x] Authority tests cover stale and overbroad interpretations.
- [x] All required validation passes.
- [x] Terra session log is complete and this contract is marked Implemented.

## Amendments

Mechanical wording, link, and test-fixture corrections may be recorded in the
implementation log. Any change to artifact permitted use, finding disposition,
repair layer, model methodology, chronology, metrics, 2026 gates, or production
scope requires a separately approved amendment or contract before implementation.
