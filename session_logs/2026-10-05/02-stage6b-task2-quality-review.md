# Session: Stage 6B Task 2 Quality Review

## TL;DR
- **Worked On:** Audited and repaired the committed Stage 6B implementation from `7b93608`.
- **Outcome:** The full six-week fixture pipeline and persisted verification pass; Task 2 is ready for Task 3 preflight and sequential staged verification.
- **Plan Contract:** [Stage 6B Task 2 quality review](../../docs/plans/2026-10-05/02-stage6b-task2-quality-review.md), user authorized 2026-10-05.
- **Approval / Status:** User explicitly requested implementation. Quality review In Progress because strict MkDocs is blocked by existing repository link warnings. The governing Stage 6B contract remains In Progress.
- **Blockers:** No fixture correctness or write-boundary blocker. Live Preview compatibility remains a Task 3 gate; fixture success does not prove it. Strict documentation build warnings remain unresolved.
- **Next:** After user commits the reviewed changes, Task 3 captures the new HEAD, runs fresh preflight, then builds and verifies each stage sequentially, stopping at the first failure.

## Context and Decisions
- Baseline: `7b93608`, branch `dev`. All Git staging and commits remain user-run.
- Amendment 1 remains controlling: writes are limited to Preview R2 `rebuild/6b/<run_id>/` and registered `lake/gold/dataset=reconstruction_*`; no serving, selection, authorization, production R2, or production database writes.
- No reconstruction or catalog publication was run. Preview R2 source metadata was read with hash checks for pins; the pipeline test uses fixture-backed R2 and a read-only Preview database response.
- The 6A root, Task 4 root, receipt SHA and namespace behavior were preserved. No contract amendment was needed.

## Contract-to-Evidence Review

| Area / finding | Severity | Repair or evidence | Regression / validation | Remaining limit |
| --- | --- | --- | --- | --- |
| Foundation ignored the return value of signed-payload verification after reading the Task 4 receipt. | Critical | Compare raw receipt bytes with the pinned Task 4 root, validate the signature/checksum, then parse and consume that original payload. Source-lock input is declared by scoring-events. | `test_changed_pinned_input_fails`; full fixture foundation and scoring-events stages. | Real Preview preflight remains Task 3. |
| Summary producer/consumer keys did not agree, and missing gate evidence could default to success. | Critical | Standardized selection, grade, unresolved team-game and gate fields; required gates now demand explicit expected values. | Receipt construction, missing-gate tamper test, and full flow. | None found in fixture review. |
| Rebuild source identities and original cutoffs were not comprehensively pinned. | High | Added hash-pinned source references for original per-week prediction manifests, quote/snapshot inputs, Week 5 outcome/scored sources, and original served artifacts. Foundation validates raw manifest hashes and reads each original `data_as_of`. | Changed pin and changed child-byte tests; foundation flow. | A separately captured Week 5 serving-manifest SHA is included as metadata; foundation uses the hash-verified Week 5 prediction manifest’s `data_as_of` as cutoff authority. Task 3 should confirm the live objects still match. |
| Finals and original grade reproduction did not prove complete, identity-safe equality across Preview rows and served `scored.csv`. | Critical | Finals require full Preview game coverage and zero score differences. Original grade reproduction checks full selection/grade keys, quote identity, result, profit and served artifacts before new grades can run. | Missing/duplicate/wrong-score finals cases; missing/duplicate/wrong-grade/wrong-quote/wrong-profit original-grade cases; full flow. | Fixture DB rows do not establish live Preview parity. |
| Persisted verification could rely on stored summaries instead of independently re-deriving artifacts. | High | Persisted verifiers rerun the stage builder from hash-checked inputs and declared parents, then compare every artifact. Receipt requires the exact gate set, exact non-claims, hashes and canonical re-derived payload. | Fresh orchestrator verifies all persisted stages; tampered receipt/CSV tests; deterministic retry. | Signature is content-checksum signing, not signer authentication, as stated in receipt non-claims. |
| Stage DAG parent reads and Gold lineage/schema compatibility needed stronger enforcement. | High | Added direct-parent read restrictions; fixed typed partition refs and parent lineage. The orchestrator writes five partitioned Gold datasets through schema validation. | Full stage flow, `collect_entries` catalog compatibility and parent checks, `test_rebuild_catalog_publish.py` rollback/idempotency tests, schema tests. | No Preview catalog registration was performed. |
| Offset and state parity or bridge compatibility could fail without stopping downstream use. | Critical | Existing hard gates are exercised with injected offset-freeze disagreement, state identity disagreement, and incompatible bundle cases. Late state and offset evidence are rejected before predictions. | New three gate-injection tests plus late-evidence tests. | Live 6A bundle and 2026 parity are not established by fixture execution. |
| Receipt’s in-memory re-derivation compared pre-JSON integer keys to parsed string keys. | Medium | Compare canonical serialized JSON so equality matches the persisted representation. | Full 12-stage flow and fresh persisted verification. | None. |

## Work Completed
- Added `conf/rebuild/6b_source_refs_v1.json` and updated `conf/rebuild/6b_v1.yaml` with source pins and corrected declared dependencies.
- Repaired foundation, source validation, stage dependency/read boundaries, market preparation, complete finals and grade reproduction, typed Gold lineage, and receipt derivation/verification.
- Added fixture-backed 12-stage orchestration coverage with 271 games across Weeks 0–5, the single locked missing total, real measurement/rating/offset/forecast/market/grade/lake computations, fresh persisted verification, and deterministic retry.
- Added failure injection for altered inputs/children, missing/duplicate finals and grades, late evidence, offset/state parity disagreement, incompatible bundle, tampered receipt/CSV, and undeclared parent reads.
- Updated the Stage 6B implementation log and plan index to record this review.

## Files Modified
- `conf/rebuild/6b_v1.yaml` and `conf/rebuild/6b_source_refs_v1.json` — source hashes and corrected stage dependencies.
- `src/cks_picks_cfb/rebuild/` — source verification, direct-parent reads, stage gates, typed lineage and canonical receipt re-derivation.
- `tests/test_rebuild_6b.py` and `tests/test_rebuild_6b_flow.py` — corrected expectations, complete fixture pipeline and injected failures.
- `docs/plans/2026-10-05/02-stage6b-task2-quality-review.md`, `docs/plans/index.md`, and `session_logs/2026-10-05/01-stage6b-implementation.md` — review status and evidence references.

## Validation
- [x] Focused Stage 6B and namespace checks: 22 passed.
- [x] Full Stage 6B fixture module before added failure-injection cases: 24 passed.
- [x] Full Python suite before the final three gate-injection tests: 1,992 passed, 9 skipped.
- [x] New offset/state/bundle injection tests: 3 passed.
- [x] Full Ruff check: clean.
- [x] Contracts validation: passed.
- [x] Data-quality registry: 29 checks, no problems.
- [x] Non-strict MkDocs build completed. Strict mode remains blocked by existing broken relative references to historical session logs/report paths and the unrecognized `5a-data/` reference; no docs-link policy changes were made.
- [x] `git diff --check`: clean after the final documentation edits.

## Amendments and Blockers
- No material change to cutoff policy, identities, model design, or write scope.
- Strict MkDocs warning debt is documented and is unrelated to Stage 6B code. The Task 2 quality plan remains In Progress until required checks are resolved or dispositioned.
- Fixture verification establishes internal stage flow and boundary behavior only. Task 3 must verify access, pins and real-data compatibility against Preview, stop at the first failing stage, and avoid publication.

## Handoff Notes
- **Resume at:** Run final `git diff --check` and confirm status; then hand the review to the user for staging and commit.
- **Watch out for:** User stages and commits. Task 3 must use the new committed HEAD and the Preview role wrapper for any database command.

**tags:** ["stage6b", "rebuild", "integrity", "fixture-verification", "preview"]
