# V5 Authority Simplification and Verified Site Cutover

- **Status:** In Progress
- **Created:** 2026-09-22
- **Planner:** Codex
- **Approval source:** User approved the proposed plan with “Implement the proposed plan.”
- **Implementation log:** `session_logs/2026-09-22/12-v5-authority-simplification-and-site-cutover.md`
- **Commit policy:** Keep changes unstaged; user executes Git operations manually.

## Goal

Declare the accepted V5 historical model complete, replace the six-slate prelaunch policy with a verified live cutover and rollback proof, simplify active documentation, and prepare the existing serving pipeline for V5. Production activation is a separate final decision.

## Current State

V5 historical development was accepted on 2026-09-22. Contracts 07 and 08 are independently verified only through Week 3; the Week 4 refresh remains required for Contract 09. The live forecast and evidence tooling from plan 03 is present as unstaged code-readiness work. V4 remains the production champion and the public weekly pipeline accepts V2/V3 model bundles, not the live V5 forecast manifest.

## Approach

Use one current V5 guide; preserve historical contracts and immutable evidence in an archive. Separate model completion, live certification, and site activation. Adapt verified V5 forecasts to the existing weekly serving artifact under an explicit versioned mode. Keep V4 available for rollback. Continue prospective monitoring after launch without a six-slate entry requirement.

## Scope

Included: authority and methodology cleanup, contract amendments, archival and link updates, a V5 serving adapter, Preview rehearsal and rollback tests, validation, and a cutover checklist. Excluded: refitting V5 on 2026 outcomes, a live 07/08/09 apply before stabilized Week 4 finals, R2 publication during code readiness, Neon production writes, or public activation.

## Implementation tasks

### 1. Simplify authority

Create a concise current guide with selected methodology, lineage, historical scorecard and limits, current operational state, and the next operator steps. Archive completed and superseded V5 contracts while preserving their contents and links. Keep 07–09 accessible until live certification. Amend the common contract, 06, current sequence, roadmap, AGENTS.md, and active entry points to state the new completion and promotion policy. Preserve immutable historical evidence and diagnostic exclusions.

### 2. Prepare serving

Add an explicit V5 serving mode that verifies the live forecast manifest and source timing, maps margin/total means and uncertainty into the existing weekly prediction artifact, checks schedule coverage and spread sign, and uses the established market display policy. Bind provenance to the immutable run. Preserve V4 configuration as the rollback path.

### 3. Rehearse and certify when parents exist

Test the adapter and a Preview publication/rollback rehearsal with synthetic refs. After Week 4 finals stabilize, create new independently verified 07/08 parents and run 09 preflight/apply/verification/repeat for the next eligible slate. Present the verified Preview run, coverage, health, and rollback proof for a separate production activation decision. Continue prospective evidence reporting after launch without using outcomes to retune V5.

## Validation

Run focused adapter/authority tests, Ruff, contract validation, strict MkDocs, archive link checks, and `git diff --check`. Test missing and mismatched parents, pregame cutoffs, incomplete coverage, deterministic repeats, sign conventions, Preview publication, and V4 rollback.

## Definition of done

- [x] One current guide and coherent authority map; historical contracts archived and links valid.
- [x] Serving adapter and synthetic Preview-path tests pass.
- [ ] A real Preview publication and V4 rollback rehearsal pass against refreshed live parents.
- [ ] Refreshed live 07/08/09 manifests and operational Preview rehearsal complete after Week 4.
- [ ] Separate production activation decision recorded; no implicit activation.
- [x] Code and documentation validation and implementation session log complete.

## Code-readiness checkpoint (2026-09-22)

The current guide, active contract map, V5 contract archive, revised promotion
policy, explicit `v5_weekly_serving_v1` adapter, V5 source verification,
schedule/market timing checks, and V4 rollback instructions are implemented.
The V5 Preview config has no forecast pinned and keeps activation disabled.
Focused tests, Ruff, contract validation, strict MkDocs, and diff checks passed.
No live 07/08/09 apply, Preview Neon publication, or prospective freeze occurred.
The remaining operational checklist is gated by stabilized Week 4 finals and
new independently verified 07/08 parents. Keep this contract In Progress until
the real Preview rehearsal and separate activation decision are recorded.

## Amendments

None.
