# V5-00: Documentation Alignment and Methodology Amendment

- **Status:** Implemented
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User approved the full V5 package with “Implement the proposed plan.” on 2026-09-13, then explicitly authorized this exact contract with “This explicitly authorizes that contract only.” in the implementation handoff.
- **Implementation log:** `session_logs/2026-09-13/03-v5-documentation-alignment.md`.
- **Commit policy:** Separate documentation/authority-test commit; user executes Git.

## Goal and current state

Make all active entry points agree with the certified September 11 research
checkpoint and the [approved V5 roadmap/common contract](v5-ratings-successor-roadmap-and-contracts.md).
The roadmap is the canonical current-status page, methodology/requirements carry
semantic authority, and dated contracts carry execution authority.

Phase 3 v2 is certified, the possession methodology is specified but unexecuted,
and V4 remains production. README, documentation home, onboarding context,
historical roadmap, and evaluation contain stale future-task descriptions. Five
authority tests currently pass without detecting these contradictions.

## Approach, scope, and interfaces

Apply the common contract's methodology amendments and publish one phase queue.
This contract changes documentation and documentation-authority tests only. No
data access, research execution, provider capture, model code, DB state, or web
behavior is authorized. No API or database schema changes.

## Implementation tasks

### Task 1 — Align status and navigation

**Files:** `docs/planning/data-first-football-forecasting-roadmap.md`,
`docs/planning/roadmap.md`, `docs/plans/index.md`, `README.md`, `AGENTS.md`,
`.agent/CONTEXT.md`, `docs/index.md`, `.codex/QUICKSTART.md`, `mkdocs.yml`.

**Changes:** Put the approved 00–06 queue on the data-first roadmap, linking each
exact contract. Record Repair verified, Phase 3 certified, possession methodology
specified/amended, and measurements not yet certified. Link concise dated status
summaries from onboarding rather than copying the entire queue. Label operational
examples as examples. Use V5 ratings successor separately from V4 feature schema
v5. Record Week 2 scored and Week 3 published as dated evidence, not enduring
live-state assertions. Replace stale “Draft rebuild” execution pointers with the
approved diagnostic closure contract while preserving the root-cause record.

**Acceptance:** Every current entry point points to the same next task. Both
roadmaps clearly distinguish operations, active research, and historical records.
No surviving current-state claim says Phase 3 needs certification or methodology
design has not happened. Preserve historical quotes where explicitly labeled.

### Task 2 — Amend semantic and evaluation authority

**Files:** `docs/modeling/possession_rating_methodology.md`,
`docs/modeling/rating_system_requirements.md`, `docs/modeling/measurement_catalog.md`,
`docs/modeling/evaluation.md`, `docs/architecture/repository_boundaries.md`,
`docs/decisions/decision_log.md`.

**Changes:** Apply the common contract's fixed constants, prior-dependent
precision equations, scoring ledger, bridge-first release, EPA/PPP distinction,
two fitting windows, and later-challenger deferrals. Correct D7/D9 and the
provisional-constants table; remove 2015–2019 global fitting as a certification
prerequisite. Update D12 and follow-on annex to match 02–06. Explicitly distinguish
the unit rating, non-offense translation offset, and outcome uncertainty.

Keep the approved two definitions, six priors, five updaters, chronological folds,
four-pass adjustment, no double schedule adjustment, and six-slate policy. Mark
possessions as specified but uncertified until 02's independent verifier passes.
Document the exact modified requirements in a September 13 decision entry.

**Acceptance:** Active prose and equations agree with the new contracts and
referenced executable baseline. No direct use of EPA as literal scoring, no
unexplained discarded scoring, and no claim of empirical support for fixed
constants. Historical Phase 4B remains an invalid forecasting parent.

### Task 3 — Resolve contract authority without rewriting history

**Files:** September 8 execution-held Phase 4A/4B/5/6 contracts;
September 11 methodology specification contract; `docs/plans/index.md`.

**Changes:** Mark the held September 8 execution contracts Superseded by 03/04/05–06
as applicable, retaining their original approval sources, hold notices, exact
historical findings, and sections explicitly inherited by the common contract.
The September 11 specification remains Implemented as a historical documentation
milestone, with a dated amendment pointer; do not imply its approved first version
was never implemented. No new contract may accidentally authorize an old runner
or the original Phase 4B manifest. Leave old session logs unchanged.

**Acceptance:** An implementer can determine the active contract and inherited
rules without treating an obsolete phase as executable. All seven contracts have
accurate lifecycle and unmet-dependency labels in the index.

### Task 4 — Strengthen authority regression checks

**Files:** `tests/test_data_first_documentation_authority.py`.

**Changes:** Extend the existing tests to cover all active entry points,
certified-versus-specified status, the complete 00–06 contract links, distinct V5
names, supersession/inherited-rule boundaries, fixed-constant chronology,
bridge-first policy, and the fitting-window comparison. Normalize harmless prose
whitespace when asserting content; do not reject intentionally labeled historical
text or change tests merely to accept an inconsistent queue.

**Acceptance:** Tests fail when an active entry point reverts to pending Phase 3
certification, premature possession certification, or old Phase 4B eligibility.

## Testing strategy

Run `uv run pytest -q -W error tests/test_data_first_documentation_authority.py`,
scoped Ruff on the modified test file, `uv run mkdocs build --strict --quiet`, and
`git diff --check`. Check every new contract link and metadata record. No full
computational or cloud run is required for documentation-only implementation.

## Risks, definition of done, and amendments

Do not erase historical evidence to make a text assertion pass. Avoid duplicating
frequently changing operational status. This documentation completion establishes
no computational certification.

- [x] Tasks 1–4 and focused validation pass.
- [x] Current authority pages consistently identify 02 as the next ratings task and 01 as an independent diagnostic.
- [x] Session log and implementation status updated; commit proposed, not executed.

Follow the common contract's amendment process for semantic or scope changes.
