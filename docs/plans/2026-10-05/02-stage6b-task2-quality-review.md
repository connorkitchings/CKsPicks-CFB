# Stage 6B Task 2 Quality Review and Repair

- **Status:** In Progress (Amendment 2 includes the exact Known Issue 6 Stage 9 exception; focused/full validation passed, fresh Task 3 rerun awaits user commit)
- **Approval:** User explicitly requested implementation of the complete review plan in this chat on 2026-10-05.
- **Authority:** [6B contract](01-stage6b-completed-week-reconstruction.md), Amendments 1–2.
- **Baseline:** `7b93608`; clean `dev`.
- **Commit policy:** User stages and commits.
- **Implementation log:** `session_logs/2026-10-05/02-stage6b-task2-quality-review.md`

## Goal and scope
Audit all twelve committed stages, repair defects within the approved contract, and establish Task 3 readiness. Code, tests, configuration and documentation only; no reconstruction run, cloud publication, catalog registration or serving changes. Preview source metadata may be read with exact hashes.

## Required work
- Fix receipt return-value misuse and undeclared scoring input; standardize required summary fields and explicit gates without permissive defaults.
- Audit stage dependencies, keys, temporal boundaries, parity, quotes, grading, comparison and receipts. Hash-check all remote sources, including Week 5 and original Preview artifacts; check original cutoff provenance.
- Require complete Preview finals coverage and reproduce original grades against both database records and scored CSVs with full keys and policy versions.
- Recompute persisted invariants, require exact receipt gates/non-claims, and verify Gold schemas, partitions, lineage and catalog compatibility. Preserve 6A identities and legacy restrictions.
- Exercise actual builders/verifiers through the real orchestrator with fixture storage/DB, all six weeks and 271 games, the one missing total, failure injection, fresh persisted verification and deterministic retries. Cover catalog rollback and CSV/grade consistency.
- Run focused checks and full Python suite, Ruff, contracts check, MkDocs and diff check. Record a contract-to-evidence review table and readiness verdict.

## Acceptance
All confirmed defects repaired; full fixture pipeline/persisted verification and required checks pass; no unresolved correctness/provenance/boundary issue. Fixture success does not establish live parity. Material changes require amendment. Task 3 captures the new committed HEAD and runs fresh preflight then sequential build/verify; publication is separately gated.

## Review outcome
After commit `4f09aef`, fresh preflight passed and stages through `predictions` passed, but `markets` failed with zero selections. The follow-up mapping repair was committed as `83b0de3`; its fresh preflight passed. On that commit, stages `foundation` through `finals` built and verified, including the expected 541 market selections. `old_grade_reproduction` then stopped because pinned served CSVs include `No Bet` rows while Preview has selections and grades for those same keys.

Read-only comparison of hash-verified Preview artifacts and Preview database rows found 541 grade rows and 541 scored-CSV target rows, with 86 differences. Example: Week 0 game `401858202`, total is `No Bet`/`No Bet` in `scored.csv` but `over`/`loss` in Preview; the point, price, quote and snapshot match. This is consistent with the approved 2026-10-02 Plan 04 transition from the constrained 2026-09-29 CSV baseline to unconstrained Preview selections/grades.

The user directed Amendment 2 on 2026-10-06. Stage 9 verifies Preview's 541 unconstrained grades independently, regrades all 455 active CSV rows, validates all 86 ungraded CSV rows against the archived thresholds, and reconciles the populations without rewriting either source. The first post-commit Task 3 attempt on `8e10f19` passed stages 1–8, then exposed an overstrict verifier assumption: a Week 5 p2 total at edge `1.070459` is graded `under`/`loss` in both the pinned CSV and Preview, although it falls below the archived 1.5 total grade threshold. A read-only Preview query confirmed the exact row's side, quote, point, snapshot and grade agree. The verifier now preserves and regrades rows the immutable CSV marks graded, while threshold-checking the rows it marks `No Bet`. Stage 9 stopped before emitting a manifest; no Stage 10–12 stage ran. The repaired fixture passes 29 tests; the full Python suite passes 1,997 tests (9 skipped). No live rerun has occurred on the uncommitted repair. The partial `8e10f19` stage 1–8 run must be archived, then fresh preflight and sequential Task 3 gates must use the next committed HEAD. Strict MkDocs warning debt remains documented separately.

On 2026-10-06, the user committed the repair as `e980e7a`. Fresh preflight passed and Stages 1–8 built and verified. Stage 9 stopped on a new, live Preview inconsistency at `2026w5-v5repair-20260929-p2 / 401858245 / spread`. Read-only queries found five Week 5 p2 rows where the current `prediction_market_selections.side` differs from `prediction_grades.side`; the first row has selection `home`, grade `away/win`, while the pinned CSV records `no bet` and the final is Virginia Tech 33–35 Pittsburgh. The Plan 04 backfill only inserts a grade when one is missing, so pre-existing grade sides may be retained while current selections reflect the unconstrained direction; this is a plausible historical mechanism, not yet confirmed for these exact rows. Under the current Stage 9 requirement to reproduce every Preview selection against its stored grade, the five rows are unexplained and the gate correctly remains closed. No Stage 9 manifest or downstream stage was produced. The fresh-run evidence is in `session_logs/2026-10-06/02-stage6b-task3-run.md`; resolve the Preview baseline and amend the contract if the accepted historical representation differs before retrying.

The user then traced those five keys to Known Issue 6, documented 2026-10-03: frozen null-lean rows carried the publisher defaults `home`/`over`, while the grades-only backfill stored their mathematical sides `away`/`under`. Amendment 2 now allows only those exact five keys, verifies both side values and recomputes the grade/profit using the stored mathematical grade side; every other Preview selection/grade side mismatch fails. Fixture coverage includes those keys, altered exception values, an unlisted mismatch, and tampered persisted exception evidence. After adding tests for altered exception-side values, the Stage 6B flow suite passed 34 tests. The full Python suite had passed 2,000 tests (9 skipped) immediately before those final two cases were added; a final full run is pending. Ruff, contracts validation, MkDocs, and `git diff --check` passed before the final test additions. The new committed HEAD must receive fresh preflight and sequential Task 3 execution. See `session_logs/2026-10-06/03-stage6b-known-issue6-repair.md`.

The final evidence table and unresolved provenance/compatibility limits are recorded in `session_logs/2026-10-05/02-stage6b-task2-quality-review.md`.
