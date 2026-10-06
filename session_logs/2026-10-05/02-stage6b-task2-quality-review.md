# Session: Stage 6B Task 2 Quality Review

## TL;DR
- **Worked On:** Audited and repaired the committed Stage 6B implementation from `7b93608`.
- **Outcome:** The market schema repair passed against Preview. Task 3 then stopped at `old_grade_reproduction`: hash-pinned CSVs and Preview DB records disagree on 86 side/result values.
- **Plan Contract:** [Stage 6B Task 2 quality review](../../docs/plans/2026-10-05/02-stage6b-task2-quality-review.md), user authorized 2026-10-05.
- **Approval / Status:** User explicitly requested implementation. Quality review and governing Stage 6B contract remain In Progress.
- **Blockers:** The Stage 9 zero-mismatch hard gate found 86 Preview/CSV differences. Any change to the no-bet/grading interpretation needs an explicit contract decision or source correction. Strict documentation build warnings also remain unresolved.
- **Next:** Resolve the authoritative Preview/CSV discrepancy under the existing hard gate or obtain a contract amendment before continuing beyond Stage 9.

## Context and Decisions
- Baseline: `7b93608`, branch `dev`. All Git staging and commits remain user-run.
- Amendment 1 remains controlling: writes are limited to Preview R2 `rebuild/6b/<run_id>/` and registered `lake/gold/dataset=reconstruction_*`; no serving, selection, authorization, production R2, or production database writes.
- Preview sources were hash-checked. Task 3 preflight passed on `4f09aef`; Stage 7 first stopped at zero selections. The line-column repair was committed as `83b0de3`; a fresh preflight passed, and stages 1–8 built and verified. Stage 9 stopped before writing outputs. Read-only Preview database inspection confirmed the mismatches. No Preview R2, catalog, database, serving, authorization, or production writes occurred.
- The 6A root, Task 4 root, receipt SHA and namespace behavior were preserved. No contract amendment was needed.

## Contract-to-Evidence Review

| Area / finding | Severity | Repair or evidence | Regression / validation | Remaining limit |
| --- | --- | --- | --- | --- |
| Foundation ignored the return value of signed-payload verification after reading the Task 4 receipt. | Critical | Compare raw receipt bytes with the pinned Task 4 root, validate the signature/checksum, then parse and consume that original payload. Source-lock input is declared by scoring-events. | `test_changed_pinned_input_fails`; full fixture foundation and scoring-events stages. | Real Preview preflight remains Task 3. |
| Summary producer/consumer keys did not agree, and missing gate evidence could default to success. | Critical | Standardized selection, grade, unresolved team-game and gate fields; required gates now demand explicit expected values. | Receipt construction, missing-gate tamper test, and full flow. | None found in fixture review. |
| Rebuild source identities and original cutoffs were not comprehensively pinned. | High | Added hash-pinned source references for original per-week prediction manifests, quote/snapshot inputs, Week 5 outcome/scored sources, and original served artifacts. Foundation validates raw manifest hashes and reads each original `data_as_of`. | Changed pin and changed child-byte tests; foundation flow. | A separately captured Week 5 serving-manifest SHA is included as metadata; foundation uses the hash-verified Week 5 prediction manifest’s `data_as_of` as cutoff authority. Task 3 should confirm the live objects still match. |
| Finals and original grade reproduction did not distinguish the historical constrained CSV baseline from the later unconstrained Preview baseline. | Critical | Amendment 2 treats them as distinct authoritative states. Preview's 541 selections/grades are independently recomputed; 455 active CSV grades are recomputed; 86 CSV target rows must satisfy the archived September 29 threshold policy and reconcile without unexplained drift. | Full flow fixture verifies exact 541/455/86 counts; identity, side and result checks; tampered persisted-grade artifact rejection. Full Python suite: 1,997 passed, 9 skipped. | Live post-amendment Stage 9 has not run; current Task 3 must stop at any discrepancy. |
| Persisted verification could rely on stored summaries instead of independently re-deriving artifacts. | High | Persisted verifiers rerun the stage builder from hash-checked inputs and declared parents, then compare every artifact. Receipt requires the exact gate set, exact non-claims, hashes and canonical re-derived payload. | Fresh orchestrator verifies all persisted stages; tampered receipt/CSV tests; deterministic retry. | Signature is content-checksum signing, not signer authentication, as stated in receipt non-claims. |
| Stage DAG parent reads and Gold lineage/schema compatibility needed stronger enforcement. | High | Added direct-parent read restrictions; fixed typed partition refs and parent lineage. The orchestrator writes five partitioned Gold datasets through schema validation. | Full stage flow, `collect_entries` catalog compatibility and parent checks, `test_rebuild_catalog_publish.py` rollback/idempotency tests, schema tests. | No Preview catalog registration was performed. |
| Offset/state parity or bridge compatibility could fail without stopping downstream use. | Critical | Existing hard gates are exercised with injected offset-freeze disagreement, state identity disagreement, and incompatible bundle cases. | New three gate-injection tests plus late-evidence tests. Actual Task 3 runs verified offsets, states and bridge. | None for stages 1–8. |
| Markets returned 0/541 on Preview because snapshots use `spread_line`/`total_line`, while the builder looked up `spread`/`total`. | Critical | Commit `83b0de3` maps the canonical Silver columns explicitly and fails if either is absent. The fixture uses the Preview schema. | Fresh Preview Stage 7 built 541 selections and its persisted verifier passed; the 27-test flow module passes. | None; this gate passed on the second Task 3 attempt. |
| Receipt’s in-memory re-derivation compared pre-JSON integer keys to parsed string keys. | Medium | Compare canonical serialized JSON so equality matches the persisted representation. | Full 12-stage flow and fresh persisted verification. | None. |

## Work Completed
- Added `conf/rebuild/6b_source_refs_v1.json` and updated `conf/rebuild/6b_v1.yaml` with source pins and corrected declared dependencies.
- Repaired foundation, source validation, stage dependency/read boundaries, market preparation, complete finals and grade reproduction, typed Gold lineage, and receipt derivation/verification.
- Added fixture-backed 12-stage orchestration coverage with 271 games across Weeks 0–5, the single locked missing total, real measurement/rating/offset/forecast/market/grade/lake computations, fresh persisted verification, and deterministic retry.
- Added failure injection for altered inputs/children, missing/duplicate finals and grades, late evidence, offset/state parity disagreement, incompatible bundle, tampered receipt/CSV, and undeclared parent reads.
- Updated the Stage 6B implementation log and plan index to record this review.
- Task 3 preflight passed on `4f09aef`; its `markets` build failed 0/541. The follow-up was committed as `83b0de3` and passed fresh preflight `3abd0e1a…`.
- On `83b0de3`, stages `foundation`, `scoring_events_2026`, `offsets_2026`, `states_at_cutoff`, `application_frames`, `predictions`, `markets`, and `finals` each built and verified. `old_grade_reproduction` failed on an ungradable CSV selection before emitting its stage manifest.
- Read-only cross-check of hash-pinned scored CSVs and Preview DB returned 541 rows each and 86 mismatches, all involving side/result. No downstream grade, comparison, or receipt stage ran.
- User-directed Amendment 2 on 2026-10-06 documents that Plan 04 created two valid historical baselines and replaces direct row equality with dual-baseline verification. Stage 9 validates Preview and constrained CSV evidence separately and gates all 86 exceptions against the September 29 thresholds.
- The amended six-week fixture passed all 29 tests, including 541 Preview grades, 455 CSV grades, 86 policy exceptions and fresh persisted re-derivation. Full Python suite passed 1,997 tests (9 skipped); repository Ruff, contracts validation, MkDocs build and `git diff --check` passed.
- The Stage 6B implementation remains In Progress pending user commit and a fresh sequential Task 3 run on that committed code SHA. No live Preview rebuild was run after Amendment 2.

## Files Modified
- `conf/rebuild/6b_v1.yaml` and `conf/rebuild/6b_source_refs_v1.json` — source hashes and corrected stage dependencies.
- `src/cks_picks_cfb/rebuild/` — source verification, direct-parent reads, stage gates, typed lineage and canonical receipt re-derivation.
- `tests/test_rebuild_6b.py` and `tests/test_rebuild_6b_flow.py` — corrected expectations, complete fixture pipeline and injected failures.
- `docs/plans/2026-10-05/02-stage6b-task2-quality-review.md`, `docs/plans/index.md`, and `session_logs/2026-10-05/01-stage6b-implementation.md` — review status and evidence references.

## Validation
- [x] Focused Stage 6B and namespace checks: 22 passed.
- [x] Full Stage 6B fixture module before the Preview schema correction: 24 passed.
- [x] Full Python suite before the final three gate-injection tests: 1,992 passed, 9 skipped.
- [x] Stage 6B fixture module after the market schema correction: 27 passed.
- [x] Task 3 Preview preflight on `83b0de32462500be6cbd757d9bd220e093d20db2`: passed (`3abd0e1a…`).
- [x] Task 3 stages 1–8 on `83b0de3`: each build and persisted verification passed.
- [x] Read-only Preview/CSV comparison: 541 rows each; 86 side/result mismatches, details above.
- [ ] Stage 9 old-grade reproduction: stopped at the required mismatch gate; no Stage 10–12 execution.
- [x] Full Ruff check: clean.
- [x] Contracts validation: passed.
- [x] Data-quality registry: 29 checks, no problems.
- [x] Non-strict MkDocs build completed. Strict mode remains blocked by existing broken relative references to historical session logs/report paths and the unrecognized `5a-data/` reference; no docs-link policy changes were made.
- [x] `git diff --check`: clean after the final documentation edits.

## Amendments and Blockers
- No material change to cutoff policy, identities, model design, or write scope.
- Strict MkDocs warning debt is documented and is unrelated to Stage 6B code. The Task 2 quality plan remains In Progress until required checks are resolved or dispositioned.
- Task 3 previously reached the original-grade gate and stopped. Amendment 2 now defines the required dual-baseline interpretation; fixture success does not substitute for a fresh committed-code live run. Publication remains separately gated.

## Handoff Notes
- **Resume at:** Finish the Stage 9 amendment checks and obtain the user commit. Then archive the partial staging directory from `83b0de3`, capture the new committed HEAD and rerun preflight.
- **Watch out for:** No post-amendment live Stage 9 run has occurred. Run each stage sequentially and stop at the first failure. Preview DB commands must use `zsh scripts/ops/with_preview_env.sh` and remain read-only.

**tags:** ["stage6b", "rebuild", "integrity", "fixture-verification", "preview"]
