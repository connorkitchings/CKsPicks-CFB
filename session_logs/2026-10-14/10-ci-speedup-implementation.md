# Session: CI speedup implementation

## TL;DR
- **Worked On:** Independent Python CI suites, database fixture/cleanup repairs, explicit coverage aggregation and manual-only historical 6B workflow.
- **Outcome:** Implementation delivered in isolated managed worktree; final validation recorded below.
- **Plan Contract:** docs/plans/2026-10-14/03-ci-speedup.md
- **Approval / Status:** User explicitly requested implementation of the revised plan. Contract remains In Progress until hosted acceptance evidence is collected.
- **Blockers:** Hosted artifact transfer, PostgreSQL 16 private-cluster behavior, runtime and runner-minute comparison await user publication.
- **Next:** User reviews and publishes changes, then compare completed Actions evidence with baseline.

## Context and Decisions
- Initial checkout dev dde737b1; isolated worktree /Users/connorkitchings/.codex/worktrees/ci-speedup/ckspicks-cfb.
- Followed start-session, persisted approved plan, then fresh Terra workers implemented independent file groups. User git operations remain manual.
- Reproduced cleanup blockage on disposable PostgreSQL 16: an idle-in-transaction backend retained a SELECT lock on predictions/games; pg_blocking_pids identified it as the blocker for DROP SCHEMA ops.
- Root cause: a pending-selection path now reads the run manifest, but the fixture did not supply that manifest. An unexpected exception bypassed explicit rollback/close on a raw connection. Real in-memory manifest bytes now exercise the production pending-window gate, and connection contexts always roll back and close.
- An initial direct reproduction inherited R2 configuration and issued one unsuccessful read for a nonexistent fixture key (NoSuchKey); no writes occurred. Subsequent runs explicitly isolated storage to local temporary fixture paths and supplied no live API credentials.
- PostgreSQL batch tests use connect_timeout=5, statement_timeout=15000 and lock_timeout=10000; failed cleanup logs backend activity. Thread cleanup releases its owning connection before joining.
- Batch and migration pending-kickoff fixtures now use database-derived anchors. Deliberately historical evidence and timing-boundary assertions remain intact.
- PostgreSQL TCP tests ran on disposable Docker PostgreSQL 16; local private-cluster tests use installed PostgreSQL 14. CI explicitly requires host PostgreSQL 16 and retains its separate TCP PostgreSQL 16 service.

## Work Completed
- Python lint, web, general, rating-publication and database jobs start independently. Only general tests fetch full git history.
- Final Python tests gate rejects unsuccessful prerequisites, missing/empty/unexpected coverage files and sub-60% combined coverage. Unique hidden coverage artifacts and JUnit outputs are configured.
- Historical 6B suite moved unchanged into workflow_dispatch-only rebuild-6b.yml; README documents exact-revision release evidence.
- Added three database regressions: rollback/closure after unexpected failure, actual bounded cleanup timeout with blocker diagnostics, and relative kickoff boundary behavior.
- No production implementation or SQL migrations changed.

## Files Modified
- .github/workflows/ci.yml — parallel suites and coverage gate.
- .github/workflows/rebuild-6b.yml — manual historical regression workflow.
- tests/test_v5_batch_selection_v2.py — isolated manifest fixtures, cleanup, timeouts and three regressions.
- tests/test_migration_integration.py — database-relative future kickoff/freeze fixture.
- README.md — CI and manual historical release validation.
- docs/plans/index.md and approved contract — lifecycle/index/amendment.
- Planning and implementation session logs — handoff and evidence.

## Validation
- Baseline collection: 3,211 IDs. Final collection: 3,214 IDs; zero removed, three behavioral regressions added.
- Partition: general 3,031; rating 7; database 141; manual historical 6B 35. Every automatic test assigned exactly once.
- General suite with four workers, warnings as errors and coverage: 3,012 passed, 19 skipped, 101.27 seconds locally.
- Rating-publication suite with warnings as errors and coverage: 7 passed, 42.03 seconds locally.
- Repaired batch-selection suite on PostgreSQL 16: 17 passed, including the real ten-second lock-timeout regression.
- Focused migration fixture plus original batch-selection/advisory-lock sequence: 3 passed in 3.53 seconds.
- Actual workflow prerequisite script: success passes; failed, cancelled and skipped fail. Actual coverage guard/combine/report: absent files fail, synthetic 0% fails, synthetic 100% passes.
- actionlint 1.7.12 validates both workflows; Python YAML parsing also passes.
- Full Ruff check passes; Ruff format check passes (821 files); shared contracts pass; quality registry passes (32 checks).
- Code-reviewer review across reliability, design/simplicity, functionality/testing and external contracts found no actionable issues. Additional migration fixture amendment separately reviewed.
- The unchanged full historical 6B suite was collected, not reexecuted; its scheduling change does not alter its test content.
- Final database/coverage/documentation results appended below.

## Amendments and Blockers
- Mechanical contract amendment extends the same fixture timing repair to the migration test discovered in the combined partition. No production gate was weakened.
- Hosted validation remains open; local runtimes are not GitHub runtime predictions.

## Handoff Notes
- **Resume at:** Review changes in the isolated worktree, perform user-controlled git publication, then inspect the new CI run and dispatch historical 6B only when its documented release criteria apply.
- **Watch out for:** Keep both PostgreSQL modes, exact coverage artifacts, warnings-as-errors and the 60% threshold. Do not treat a passing older SHA as release evidence.
- **Proposed commit:** chore(ci): parallelize Python checks and isolate historical rebuilds

**tags:** ["ci", "testing", "postgres", "github-actions"]

## Final validation results
- Five-file database partition: **141 passed, zero skipped in 39.61 seconds**. Disposable PostgreSQL 16 container removed after testing.
- Combined real general/ratings/database coverage: **69%**, passing the unchanged **60%** gate. Coverage report retained locally at /private/tmp/ckspicks-ci-coverage-report.txt; JUnit outputs at /private/tmp/ckspicks-ci-{general,ratings,database}.xml.
- Total automatic partition: **3,160 passed, 19 skipped**; full historical 35-test suite remains manual.
- Final MkDocs build and git diff --check passed.
- No commits, pushes, deployment or database serving writes performed.
