# Stage 6B Task 2 Quality Review and Repair

- **Status:** In Progress (Amendment 2 and dual-baseline Stage 9 repair implemented; focused fixture validation and fresh Task 3 rerun pending)
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

The user directed Amendment 2 on 2026-10-06. Stage 9 now verifies Preview's 541 unconstrained grades independently, regrades all 455 active CSV rows, validates all 86 CSV exceptions against the archived September 29 thresholds, and reconciles the two populations without rewriting either source. Its persisted verifier rederives the evidence and compares the regenerated outputs to persisted artifacts. Focused fixture validation is in progress. No post-amendment live stage run has occurred; the 2026-10-05 run stopped at Stage 9 before the repair. The quality review remains In Progress until focused/full validation passes and a new committed HEAD completes fresh sequential Task 3 gates. Strict MkDocs also exits on existing repository-relative link warnings documented in the implementation log.

The final evidence table and unresolved provenance/compatibility limits are recorded in `session_logs/2026-10-05/02-stage6b-task2-quality-review.md`.
