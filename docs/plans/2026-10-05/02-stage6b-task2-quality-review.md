# Stage 6B Task 2 Quality Review and Repair

- **Status:** In Progress (Task 3 stopped at the original-grade reproduction gate after finding 86 Preview/CSV mismatches)
- **Approval:** User explicitly requested implementation of the complete review plan in this chat on 2026-10-05.
- **Authority:** [6B contract](01-stage6b-completed-week-reconstruction.md), Amendment 1.
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

Read-only comparison of hash-verified Preview artifacts and Preview database rows found 541 grade rows, 541 scored-CSV selection rows, and 86 side/result mismatches. Example: Week 0 game `401858202`, total is `No Bet`/`No Bet` in `scored.csv` but `over`/`loss` in Preview; the point, price, quote and snapshot match. No later stage ran. This violates the contract’s zero-mismatch hard gate. Resolving it requires correcting the authoritative source artifacts/records or explicitly amending Stage 9’s policy; the verifier must not discard these rows to force a pass.

The quality review remains In Progress pending that source/policy decision. Strict MkDocs also exits on existing repository-relative link warnings documented in the implementation log.

The final evidence table and unresolved provenance/compatibility limits are recorded in `session_logs/2026-10-05/02-stage6b-task2-quality-review.md`.
