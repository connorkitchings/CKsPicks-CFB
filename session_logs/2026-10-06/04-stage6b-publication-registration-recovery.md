# Session: Stage 6B Preview Catalog Registration Recovery

## TL;DR
- **Worked On:** Recovered the Stage 6B Task 4 publication flow after the authorized apply copied immutable R2 artifacts but failed during catalog registration.
- **Outcome:** Recovered the atomic catalog registration failure, published the five Stage 6B datasets to Preview, independently read back the catalog versions and dependency edges, and proved a zero-write retry.
- **Plan Contract:** [Stage 6B contract](../../docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md), Amendment 1 and Task 4.
- **Approval / Status:** User explicitly authorized Stage 6B Preview publication and idempotence proof. Publisher repair committed at `918294323afa53dd625d0cc9d8e75955477b6dc9`; publication and independent readback passed.
- **Blockers:** None for Task 4. Stage 7B remains a separate contract and authorization gate.
- **Next:** Handoff the published Stage 6B receipt and datasets to the separately gated Stage 7B work.

## Context and Decisions
- Command used the required wrapper: `zsh scripts/ops/with_preview_env.sh .venv/bin/python scripts/pipeline/publish_6a.py --plan conf/rebuild/6b_v1.yaml --expected-code-sha eca6871d727060adf8612bd7d8769c29d5243579 --apply --register-catalog --prove-idempotence`.
- Stage verification and preflight were valid; all twelve stage verifiers passed. The publisher copied 112 stage objects and created `rebuild/6b/6b-replay-20261005-r1/root-manifest.json` before catalog registration failed on FK parent version `14ba359ac849b4dc10e6be86`.
- A post-failure dry run showed all 112 stage objects already present and identical. A read-only catalog query found no reconstruction root versions and zero dependency rows, confirming the one-transaction registration rolled back. All 49 external parent versions exist; the four temporarily absent parent IDs are the four other reconstruction roots in the same transaction.
- Root SHA-256 is `6fb59797e35c05a6657219e4e41e0b3834187f1ee88971b1d78045c96c78e6cf`; it records build and first publisher code SHA `eca6871d727060adf8612bd7d8769c29d5243579`, verify SHA `e462ae05408999c4e7d7fa61519b134f97a074dc8acb4d714680d6048b525aaa`, and 112 objects.
- The failure is caused by root entries sorted lexicographically: application frames reference offsets, while offsets appeared later in the transaction. A stable topological ordering fixes this without changing dataset identities or write scope.
- Retry must preserve the immutable existing root. The orchestrator now reuses it only when the signed root exactly matches the current preflight, verify record, stage manifests, and object map, and when the old publisher commit is verified in the build-to-current-publisher Git lineage. The new commit records the recovery tooling; the signed root continues to describe the original verified build/copy.
- No production or serving paths/tables were touched.
- After commit `9182943`, the required-wrapper dry run found all 112 of 112 expected R2 objects byte-identical to staged content, totaling 1,446,029 bytes across 65 `lake/gold` and 47 `rebuild/6b` objects. It reported exactly the five planned reconstruction catalog entries and verification SHA `e462ae05408999c4e7d7fa61519b134f97a074dc8acb4d714680d6048b525aaa`.
- The authorized apply registered root manifest `rebuild/6b/6b-replay-20261005-r1/root-manifest.json` with SHA-256 `32105bbe8dbc97328557406347cbf5c55c727ad38d186a352089fe0d5aaf8d45`. The root reused the byte-identical objects (0 R2 writes). The immediate idempotence retry kept the same root SHA and wrote 0 R2 objects and 0 catalog rows.
- Independent read-only Preview catalog query, through `with_preview_env.sh` as `cks_preview_pipeline`, found exactly five `validated` versions: offsets (271 rows), application frames (271), predictions (542), market selections (541), and grades (541); it found 54 dependency edges.

## Work Completed
- Added stable parent-before-child topological ordering for catalog entries, with duplicate-version and dependency-cycle rejection.
- Added a controlled existing-root retry path for failed atomic catalog registration.
- Updated the CLI to prove the original root's publisher commit belongs to the build/current-HEAD lineage.
- Added regressions for in-batch parent ordering, exact-root reuse across an ancestor publisher, and rejection of unrelated publisher roots.
- Updated the Stage 6B contract execution record. The partial apply remains incomplete until catalog registration, idempotence proof, and independent readback pass.

## Files Modified
- `src/cks_picks_cfb/rebuild/catalog_publish.py` — topological order for batch dependencies.
- `src/cks_picks_cfb/rebuild/orchestrator.py` — validate and reuse existing immutable root during safe retry.
- `scripts/pipeline/publish_6a.py` — validate publisher ancestry on recovery.
- `tests/test_rebuild_catalog_publish.py` — parent-first ordering regression.
- `tests/test_rebuild_publish_cli.py` — safe retry and unrelated-root rejection regressions.
- `docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` — Task 4 execution and recovery record.
- `session_logs/2026-10-06/04-stage6b-publication-registration-recovery.md` — this log.

## Validation
- [x] Focused publication/catalog/orchestrator tests — 43 passed.
- [x] Ruff formatting and lint for changed Python files — passed.
- [x] Full Python suite — 2,005 passed, 9 skipped.
- [x] `.venv/bin/ruff check .` and format check — passed.
- [x] `.venv/bin/python contracts/validation.py` — passed.
- [x] `.venv/bin/python -m mkdocs build --quiet` — passed.
- [x] `git diff --check` — passed.
- [x] After user commit: fresh dry run, catalog registration, zero-write idempotence proof, independent Preview readback.

## Amendments and Blockers
- No data identity, model, or write-scope change. The retry preserves the existing signed build root and registers only the five authorized reconstruction datasets in the existing single catalog transaction.
- The authorized apply partially completed its Preview R2 copy before catalog registration failed. All objects remain create-once and byte-identical. Do not delete or rewrite them; resume with the safe retry after commit.

## Handoff Notes
- **Resume at:** Task 4 is complete. Stage 7B is a separate handoff and requires its own contract and authorization.
- **Watch out for:** A changed root or non-ancestor publisher must fail closed. No serving, authorization, production, or unrelated catalog writes.

**tags:** ["rebuild", "stage6b", "publication", "catalog", "preview"]
