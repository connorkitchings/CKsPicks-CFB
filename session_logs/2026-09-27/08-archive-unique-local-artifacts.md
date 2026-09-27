# Session: Archive Unique Local Artifacts

## TL;DR

- **Worked On:** Implemented the fixed-allowlist Preview R2 artifact archive command and backed up 11 historical files.
- **Outcome:** All 11 files (1,338,899,132 apparent bytes) and a content-addressed manifest uploaded; a second full remote read verified every SHA-256 and size. No local file deleted because lifecycle proof remains unavailable.
- **Plan Contract:** `docs/plans/2026-09-27/03-archive-unique-local-artifacts.md` (In Progress).
- **Approval / Status:** User explicitly authorized this implementation. The deletion gate remains unfulfilled.
- **Blockers:** The configured Preview R2 key returns `AccessDenied` for read-only bucket lifecycle configuration. Computer access to the Cloudflare dashboard in Chrome was denied by automatic review. Await a current read-only admin/dashboard rule record or a key with lifecycle-read permission.
- **Next:** Review lifecycle rules for the exact Preview bucket and backup prefix, then rerun `verify` and `prune` only if no enabled expiry applies. Finish the report and mark the plan Implemented after successful prune.

## Context and Decisions

- Confirmed the worktree was clean before edits and `CFB_STORAGE_BACKEND=r2` with complete Preview R2 credentials, without printing credential values. This command does not operate on the repository `data/` directory.
- Rehashed all 11 allowlisted files before upload. Their sizes and hashes matched the previous cleanup report. The upload order was smallest first, and the 1.10 GB CSV used bounded 16 MiB multipart parts.
- Used conditional creates for R2 object keys. Existing keys are reusable only after a full remote hash match. The separate `verify` command read every remote file and the manifest after all uploads completed. Multipart ETags were not used as proof.
- The tracked manifest is `docs/reports/2026-09-27-local-artifact-archive-manifest.json`; the exact remote key is in the [report](../../docs/reports/2026-09-27-local-artifact-archive.md).
- The lifecycle API returned `AccessDenied`; no deletion was attempted. The eight approved candidates and all three local keepers remain byte-for-byte unchanged. Before and after local inventories compare equal.

## Work Completed

1. Added `scripts/ops/archive_local_artifacts.py` with `inventory`, `upload`, `verify`, and `prune` modes; exact allowlist and symlink/file-identity checks; bounded multipart upload; full remote SHA-256 verification; lifecycle gate; and durable prune journal logic.
2. Added eight focused tests covering the successful and failure paths.
3. Published the 11-file content-addressed manifest to Preview R2 and saved its tracked copy.
4. Recorded per-file disposition and zero reclaimed bytes in `docs/reports/2026-09-27-local-artifact-archive.md`.

## Files Modified

- `scripts/ops/archive_local_artifacts.py` — internal archival command.
- `tests/test_archive_local_artifacts.py` — safety-gate tests.
- `docs/reports/2026-09-27-local-artifact-archive-manifest.json` — tracked exact remote mapping and hashes.
- `docs/reports/2026-09-27-local-artifact-archive.md` — proof and disk report.
- `docs/plans/2026-09-27/03-archive-unique-local-artifacts.md` — in-progress contract and blocker.
- `session_logs/2026-09-27/08-archive-unique-local-artifacts.md` — this log.

## Validation

- [x] Archive-command tests: 8 passed.
- [x] Final CI-equivalent Python suite: 1,466 passed, 2 skipped; 66.21% coverage.
- [x] Ruff format and lint, shared contracts validation, strict MkDocs build.
- [x] Repository-boundary and documentation-authority scoped run: 30 passed.
- [x] Full remote read and SHA-256/size comparison for 11/11 backups, plus manifest.
- [x] Local inventory unchanged: 11/11 files remain; 1,338,899,132 apparent and 1,338,929,152 allocated bytes before and after.
- [ ] Lifecycle proof and approved eight-file prune; blocked by `AccessDenied` and absent dashboard evidence.
- [x] Final `git diff --check` after all documentation edits; no tracked files deleted. Ruff, contracts, strict MkDocs, and 30 scoped tests rerun after report edits.

## Amendments and Blockers

No scope amendment. The contract explicitly requires retention when lifecycle proof is unavailable, so the unfulfilled prune step is reported rather than bypassed. Automatic review denied Chrome computer access to inspect the dashboard; it did not affect the R2 backup or tests.

## Handoff Notes

- **Resume at:** Obtain lifecycle-rule evidence, inspect every enabled expiry rule against `artifacts/research/local-artifact-archive-v1/`, then run `.venv/bin/python scripts/ops/archive_local_artifacts.py verify` and `prune` after the gate passes.
- **Watch out for:** Keep the locked CSV and two weights sidecars local. A screenshot must show the full rule list for the exact Preview bucket. Never delete files manually or treat the R2 ETag as byte proof.
- **Suggested commit message:** `chore: back up historical artifacts with verified R2 archive command`

**tags:** ["cleanup", "artifacts", "r2", "preview"]
