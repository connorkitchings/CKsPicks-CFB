# Session: CI speedup planning

## TL;DR
- **Worked On:** start-session investigation of GitHub Actions timings and tests.
- **Outcome:** User approved concurrent Python suites, database reliability repair, explicit coverage combining and manual-only full 6B integration.
- **Plan Contract:** docs/plans/2026-10-14/03-ci-speedup.md
- **Approval / Status:** Approved by explicit user implementation request.
- **Blockers:** None for implementation; hosted timing evidence awaits user publication.
- **Next:** Terra implementation workers in isolated ci-speedup worktree.

## Context and Decisions
- Cached dependencies take seconds; Docker images are not justified.
- SQL cleanup blocks in test_v5_batch_selection_v2; fixed dates and leaked transactions require reproduction.
- Both TCP service PostgreSQL and private socket-cluster binaries must be present in CI.

## Validation
- GitHub run metadata/logs and local test source inspected read-only.
- Documentation validation recorded in implementation log.

## Handoff Notes
- **Resume at:** Execute approved contract.
- **Watch out for:** Retain coverage gate and all non-6B test IDs; no user git operations.

**tags:** ["ci", "planning"]
