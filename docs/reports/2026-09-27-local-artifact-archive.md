# Local Artifact Archive: Verified Backups, Prune Gate Open

**Date:** 2026-09-27 18:18 UTC

**Contract:** [Archive Unique Local Artifacts](../plans/2026-09-27/03-archive-unique-local-artifacts.md)

**Manifest:** [Tracked copy](2026-09-27-local-artifact-archive-manifest.json)

## Result

The 11 exact allowlisted files were uploaded to the configured Preview R2 bucket under `artifacts/research/local-artifact-archive-v1/files/sha256=<sha256>/<filename>`. Each upload was followed by a full streamed remote read, and a separate `verify` run read and SHA-256 checked all 11 objects again. The remote content-addressed manifest was also read and hash checked. Its key is:

`artifacts/research/local-artifact-archive-v1/manifests/sha256=37d3946b52bf836a1afa6581348aaf7f8b4547f83d856c4f13d352a209f4f7de.json`

The tracked manifest records every exact original path, size, SHA-256, and backup key. R2 ETags were never used as content proof. Conditional create requests (`If-None-Match: *`) and full-content checks protect the write-once keys. No R2 object was overwritten or removed.

**No local artifact was deleted.** A read-only `GetBucketLifecycleConfiguration` request with the configured Preview R2 key returned `AccessDenied`. No dashboard or administrator lifecycle record was available to establish that enabled expiration rules do not cover the backup prefix. The contract therefore forbids pruning despite byte-verified backups.

## Per-file disposition

| Original local path | Apparent bytes | Remote proof | Local disposition |
| --- | ---: | --- | --- |
| `artifacts/preview/training/v4/selection-candidates-20260818.csv` | 1,099,653,745 | Full remote SHA-256 and size match the manifest | Retained pending lifecycle proof; approved prune candidate |
| `artifacts/preview/training/week0-regime-candidates.csv` | 50,154,066 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |
| `artifacts/preview/training/v4/locked-candidates-20260818.csv` | 4,819,211 | Full remote SHA-256 and size match | Kept for the current `extract_model_accuracy.py` default |
| `artifacts/preview/training/v4/selection-candidates-20260818.blend-weights.json` | 266 | Full remote SHA-256 and size match | Kept as local companion |
| `artifacts/preview/training/week0-regime-candidates.weights.json` | 240 | Full remote SHA-256 and size match | Kept as local companion |
| `archive/legacy_v1_2025/artifacts/ratings/2019/trace.nc` | 30,503,854 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |
| `archive/legacy_v1_2025/artifacts/ratings/2021/trace.nc` | 30,549,435 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |
| `archive/legacy_v1_2025/artifacts/ratings/2022/trace.nc` | 30,743,361 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |
| `archive/legacy_v1_2025/artifacts/ratings/2023/trace.nc` | 31,307,460 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |
| `archive/legacy_v1_2025/artifacts/ratings/2024/trace.nc` | 33,433,112 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |
| `archive/legacy_v1_2025/artifacts/ratings/2025/trace.nc` | 27,734,382 | Full remote SHA-256 and size match | Retained pending lifecycle proof; approved prune candidate |

The eight conditional prune candidates total **1,334,079,415 apparent bytes**. The local manifest hash, file hashes, and exact remote keys are in the tracked JSON manifest. The remote read completed after all 11 uploads and before any deletion decision.

## Disk accounting

| Scope | Before apparent bytes | After apparent bytes | Before allocated bytes | After allocated bytes | Reclaimed |
| --- | ---: | ---: | ---: | ---: | ---: |
| 11 allowlisted local files | 1,338,899,132 | 1,338,899,132 | 1,338,929,152 | 1,338,929,152 | 0 |
| Eight conditional prune files | 1,334,079,415 | 1,334,079,415 | 1,334,099,968 | 1,334,099,968 | 0 |

The before and after inventory JSON files in `/tmp/ckspicks-archive-inventory-20260927.json` and `/tmp/ckspicks-archive-inventory-after-20260927.json` compare equal, including file identity, size, allocated bytes, and SHA-256. The locked CSV, sidecars, and all other archive files remain locally untouched. No tracked path was removed.

## Validation and next gate

- Eight focused archive-command tests pass: successful upload/reuse/verify/prune, key collision, remote mismatch, incomplete multipart abort, changed local file, symlink, missing or expiring lifecycle proof, interrupted prune, unexpected path, and dashboard evidence tampering.
- Final CI-equivalent Python run: 1,466 passed, 2 skipped, 66.21% coverage. Ruff format/lint, contracts validation, strict MkDocs build, and 30 focused repository-boundary/documentation tests pass.
- Before attempting `prune`, obtain a current read-only Cloudflare administrator/API or dashboard record for the configured Preview bucket showing all lifecycle rules and no enabled expiry applying to `artifacts/research/local-artifact-archive-v1/`. Do not alter bucket rules. Then rerun `verify` and `prune`; the command rechecks every candidate before unlink and writes a durable prune journal.

The pending lifecycle evidence is the only reason local recovery remains zero. No local deletion should be performed manually.
