# <Plan Title>

- **Status:** Draft
- **Created:** YYYY-MM-DD
- **Planner:** Sol
- **Approval source:** Pending
- **Implementation log:** Pending
- **Commit policy:** Separate plan commit | Commit with implementation

## Goal and acceptance

State the problem, intended outcome, observable success criteria and definition of done. Implementation is complete only when every acceptance item and required check passes.

## Baseline and constraints

Record the inspected branch/commit, worktree, existing behavior and relevant authority/dependencies. State included and excluded scope, affected interfaces/components, compatibility requirements, evidence to preserve, risks and failure/stop gates. Identify assumptions requiring confirmation before implementation.

## Ordered changes

List bounded tasks in execution order. For each task, specify the affected components or interfaces, intended change, acceptance criteria and focused validation. Resolve consequential design choices before handoff; link shared specifications instead of repeating them.

## Validation

List required tests/checks and positive, negative, boundary and recovery scenarios appropriate to the change. Specify any readback, idempotence, rollback or release evidence needed. Include `git diff --check` and the scoped documentation/session-log checks.

## Handoff/amendments

State the approval and resume gate, implementation log, user-controlled commit policy and precise next action. Preserve the Sol-to-Terra workflow and separate exact release approvals. A mechanical amendment may proceed only if architecture, interfaces, scope and acceptance remain unchanged; a material conflict returns to Sol for review. Record each amendment's reason, previous approach, revised approach and impact here.
