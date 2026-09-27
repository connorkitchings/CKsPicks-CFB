# Archive Unique Local Artifacts and Reclaim Disk Space

- **Status:** In Progress
- **Created:** 2026-09-27
- **Approval source:** User explicitly requested implementation of this plan on 2026-09-27
- **Implementation log:** `session_logs/2026-09-27/08-archive-unique-local-artifacts.md`
- **Commit policy:** User controls Git operations

## Goal

Back up the five Preview training files and six historical rating traces to the configured Preview R2 bucket, verify each backup by full remote SHA-256 read, then reclaim local space from the eight approved large files only after lifecycle-rule proof.

## Contract

1. Add an internal `inventory`, `upload`, `verify`, `prune` command with an exact 11-file allowlist. Reject symlinks, changed files, unexpected paths, and missing files without prior prune proof.
2. Store files under `artifacts/research/local-artifact-archive-v1/files/sha256=<hash>/<filename>`. Reuse existing keys only after full byte verification. Never overwrite. Use bounded multipart transfer for large files.
3. Publish a content-addressed remote manifest and tracked local copy with path, size, SHA-256, backup key, and bucket. Back up all 11; retain the locked-candidates CSV and both weights files locally.
4. Before removing any of the eight approved files, obtain read-only lifecycle rules proving no enabled expiration covers the prefix. If proof is unavailable or expiry applies, retain all local files. Recheck each deletion candidate immediately before unlink and keep a durable prune journal.
5. Report per-file disposition and before/after apparent and allocated bytes. Do not touch other local artifacts, R2 objects, production paths, or concurrent web edits.

## Validation

Test successful and failure paths, including identical object, collision, incomplete upload, remote mismatch, local change, symlink, missing lifecycle proof, and interrupted prune. Run Ruff, Python tests, repository-boundary checks, contracts, MkDocs, and `git diff --check`.

## Definition of done

- [ ] All 11 remote copies fully verified and both manifests published.
- [ ] Lifecycle proof shows the backup prefix is not subject to enabled expiration.
- [ ] Only the eight approved local files removed with immediate pre-unlink proof.
- [ ] Report, session log, and validation complete.

## Amendments and blockers

The backup and independent verification stages completed on 2026-09-27. The configured Preview R2 key returned `AccessDenied` for the read-only lifecycle configuration request. No current administrator/dashboard rule record was available. The lifecycle proof and eight-file prune tasks remain open; no local file was removed. See the [execution report](../../reports/2026-09-27-local-artifact-archive.md).
