# Stage 6B Task 2 Quality Review and Repair

- **Status:** In Progress (implementation and fixture verification complete; strict docs warning gate unresolved)
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
The source and fixture review supports proceeding to Task 3 preflight and sequential stage execution. Live Preview compatibility remains a Task 3 hard gate. The task is not marked Implemented because strict MkDocs exits on five repository-relative link warnings documented in the implementation log.

The final evidence table and unresolved provenance/compatibility limits are recorded in `session_logs/2026-10-05/02-stage6b-task2-quality-review.md`.
