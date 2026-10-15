# Speed up CI while preserving regression coverage

- **Status:** Merged (PR #7; 2026-10-15 review confirmed integration)
- **Created:** 2026-10-14
- **Planner:** Sol
- **Approval source:** User explicitly requested implementation of the revised plan in this chat.
- **Implementation log:** session_logs/2026-10-14/10-ci-speedup-implementation.md
- **Commit policy:** Commit with implementation; user performs git operations.

## Goal and acceptance

Eliminate the database cleanup hang, run independent Python suites concurrently, and move the full historical 6B suite to manual dispatch. Preserve all other test coverage and the 60% coverage gate. The 3–5 minute automatic CI duration is an unverified target, not a promise.

## Baseline and constraints

Baseline dev dde737b1; CI main 1fd3afca. Prior run 38601940715: general tests 305 seconds, rating publication 100 seconds, database cleanup hangs at DROP SCHEMA in the advisory-lock test after batch selection, 6B 976 seconds. Dependencies install in 3 seconds. Keep native runners, cached frozen uv installs, triggers, cancellation and web validation. No production semantics, schema/data changes, paid runners, custom images, remote test-result caching or scheduled runs. Only general tests need full history. All other jobs, including manual 6B, use shallow checkout.

## Ordered changes

1. Reproduce database blocking on disposable PostgreSQL 16 and identify originating transaction before repair. Always close/rollback explicitly opened connections and release locks/join threads after failures. Use test-only statement_timeout=15000, lock_timeout=10000 and a bounded connection timeout; emit blocking diagnostics. Replace clock-dependent fixture kickoff literals with one database-derived anchor, preserving historical evidence and timing-boundary checks. Do not weaken production gates.
2. Start lint, web, general tests, ratings and database jobs independently. General tests retain xdist -n 4 and existing exclusions, additionally excluding test_season_release_postgres.py. Ratings remain one process. Database job runs the four existing shared-database files and season-release PostgreSQL file serially. Provide both postgres:16 TCP service with TEST_DATABASE_URL and host PostgreSQL 16 binaries on PATH for the independent private socket cluster. Assert prerequisites; missing server binaries must fail rather than skip.
3. Set COVERAGE_FILE to .coverage.general/.coverage.ratings/.coverage.database. Upload exact paths with actions/upload-artifact@v4, include-hidden-files=true, if-no-files-found=error, unique coverage-* names. Upload unique JUnit artifacts even on failure. Final Python tests gate uses if: always(), checks lint and all suite results for success, downloads coverage-* with actions/download-artifact@v4 and merge-multiple=true, requires all three files, runs uv run coverage combine then uv run coverage report --fail-under=60. Partial coverage cannot pass. Retain warnings as errors.
4. Separate workflow_dispatch-only 6B workflow retains all 35 tests, synthetic population sizes, computations, persisted verification, grading and tamper checks, timeout, slow durations and JUnit output. Report tested revision and document manual use before historical reconstruction/shared-numerics/persisted-contract releases. Keep smaller rebuild and current season tests automatic; no additional optional-suite sharding.

## Validation

Reproduce then repeat affected database sequence; inject transaction failure and verify schema cleanup proceeds. Check fixture timing across old boundaries. Compare collected node IDs: every non-6B test assigned exactly once. Execute private PostgreSQL suite without missing-binary skips. Exercise final gate failures for bad prerequisite statuses, absent coverage files and coverage below 60%. Validate workflow syntax, scoped lint, git diff --check and uv run mkdocs build --quiet. After user publication compare hosted wall time, runner minutes, counts, skips and coverage against baseline; this evidence remains pending until then.

## Handoff/amendments

User authorizes implementation in this session; persist the contract first, then delegate implementation to fresh Terra workers in the isolated worktree. No commits/pushes. Nonmaterial mechanical amendments may proceed if scope and acceptance remain unchanged; material conflicts return for review. Mark Implemented only when all required evidence, including hosted validation, is complete.

### Mechanical amendment: migration fixture timing

The combined database partition exposed an additional expired future-kickoff literal in test_stage7a_migrations_guard_prospective_and_revocation_records in tests/test_migration_integration.py. Extend the same database-derived fixture-time repair to that test only; preserve production triggers and historical before/after behavior. This changes neither scope architecture nor acceptance criteria. Local TCP validation uses disposable PostgreSQL 16; local private-cluster validation uses installed PostgreSQL 14, while the workflow explicitly requires PostgreSQL 16 for both CI modes. Hosted PostgreSQL 16 private-cluster and runtime evidence remain pending user publication.

### Local implementation acceptance

Implementation and local checks complete: automatic partition 3,160 passed/19 skipped, no removed test IDs, three new behavioral regressions; database partition 141 passed/zero skips; combined coverage 69% (60% gate); Actions syntax, negative gate cases, lint, formatting, contracts, registry, MkDocs and diff checks pass. Four code-review lenses found no actionable findings. Remains In Progress only for the planned post-publication hosted PostgreSQL 16 private-cluster/artifact/runtime and runner-minute evidence; no git publication was performed.

### Publication authorization

After reviewing the delivered changes and the PR-trigger correction, the user asked "can you proceed?", authorizing the scoped commit, fast-forward integration into dev, push and PR creation for hosted verification. This supersedes the manual-only git restriction for these publication steps. No merge to main or deployment is authorized. Publication evidence is tracked in session_logs/2026-10-14/11-ci-speedup-publication.md.


### Hosted acceptance completed

PR https://github.com/connorkitchings/CKsPicks-CFB/pull/7, implementation revision bf53e5a6396b21ade868cbd7309386661a0bb7bc, CI https://github.com/connorkitchings/CKsPicks-CFB/actions/runs/38673650571: all six CI jobs passed. General 3,012 passed/19 skipped, ratings 7 passed, database 141 passed/zero skips with host PostgreSQL 16.15. Coverage artifacts transferred and combined successfully: 69%, above 60%. Vercel Preview passed.

Observed first-job-to-final-gate elapsed time was 4m32s; run creation to completion was 6m09s including queueing behind a superseded run. Summed job elapsed time was 11m31s versus 39m00s for baseline run 38601940715 (which ended cancelled after the database hang). The timing API reports zero billable milliseconds for both runs, so these figures describe elapsed runner work rather than billed minutes or cost. This single-run comparison is evidence, not a guaranteed duration.

Implementation acceptance is complete. Separate PR release blocker: GitGuardian scans the earlier commit 8aa6a4f5 and flags its disposable postgres:postgres test URL. Current workflow uses github.run_id for the temporary service and client password. No production credential was involved. Resolve the false positive in GitGuardian; do not rewrite published dev history without separate authorization. No main merge or production deployment performed.

### GitGuardian disposition and release authorization

User explicitly requested clearing incident #23000215 and merging PR #7. After user sign-in, the incident UI confirmed Ignored / Not a secret (false positive). No security rules or integrations were disabled. Existing GitHub check requires a fresh scan; the release-preparation receipt triggers it. The latest documentation-head run 38674516002 also passed, taking 6m46s from first job to final gate, demonstrating runner variation beyond the first 4m32s observation. Weekly serving/data state remains unchanged by this CI release.
