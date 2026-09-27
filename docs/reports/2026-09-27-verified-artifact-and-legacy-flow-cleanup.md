# Verified Artifact and Legacy Flow Cleanup

**Date:** 2026-09-27

**Contract:** [Verified Artifact and Legacy Flow Cleanup](../plans/2026-09-27/02-verified-artifact-and-legacy-flow-cleanup.md)

**Outcome:** Retired one unused example flow. Retained all 460 ignored local artifact files because no immutable R2 counterpart or explicit provenance mapping was found. No local artifact was deleted or uploaded.

## Release and source gates

- Before tracked edits, `git status --short` was empty. Production `/api/health` showed Week 5 run `2026w5-d6366e59fd43` selected in `published` state, 56 predicted games, 34 lined; `session_logs/2026-09-27/06.md` records the completed release.
- The CI-equivalent Python baseline passed: 1,458 tests, 2 skipped, 66.16% coverage; Ruff format and lint were clean.
- A tracked-text scan found no caller of `src/cks_picks_cfb/flows/example_flow.py` or `example_data_flow`. The prior inventory named the file only as a candidate. No Make, CI, test, compatibility, or current operator path names it. The user confirmed that no external flow runs it. The historical `preaggregations_flow` appears in two 2025 session logs, so its module and package remain.

## Local artifact method

The read-only audit walked every file beneath `artifacts/preview/training/` and `archive/legacy_v1_2025/artifacts/`, checked tracking and ignore status, excluded symlinks, and streamed each local file through SHA-256. A second pass after the Week 5 release found the same 460 paths, byte sizes, allocated sizes, and hashes. No file changed during hashing. The temporary per-file inventory is `/tmp/ckspicks-cleanup-readonly-inventory-20260927.json`; the five Preview hashes are reproduced below.

With `CFB_STORAGE_BACKEND=r2` and complete Preview credentials verified without printing their values, a read-only `list_object_metadata` call found **zero objects** under each exact candidate prefix in the configured Preview R2 bucket:

- `artifacts/preview/training/`: 0 objects
- `archive/legacy_v1_2025/artifacts/`: 0 objects

The repository and local sidecar search found no explicit R2 manifest or provenance link mapping these local files to a different immutable key. The archive's MLflow metadata points to a former local `file://` path, not R2. Therefore there was no remote payload to hash or immutability claim to verify. Matching by filename or ETag was not attempted. Every local file is retained.

## Preview training files: all retained

| Path below `artifacts/preview/training/` | Apparent bytes | Local SHA-256 | Additional reason |
| --- | ---: | --- | --- |
| `v4/selection-candidates-20260818.csv` | 1,099,653,745 | `487f72a149291120d770d139f74ac54d8f8e6d367b458116037a7dc8722bcc50` | No immutable counterpart mapped |
| `week0-regime-candidates.csv` | 50,154,066 | `d23458fa13c0ab45107e668a34310116370058a2d6b38512a88afecf26759135` | No immutable counterpart mapped |
| `v4/locked-candidates-20260818.csv` | 4,819,211 | `4216ee9c9f9b28ad5a24b8f9e4b7f94f1098c1e46d71c9cb4be060a1fc3d2a35` | Also the default local input of `scripts/pipeline/extract_model_accuracy.py` |
| `v4/selection-candidates-20260818.blend-weights.json` | 266 | `c9ada11b30dbee733d53facc35dbcef019a2160be762c0f32fcaba675f3091d5` | No immutable counterpart mapped |
| `week0-regime-candidates.weights.json` | 240 | `d9372172ccdf390e8605be7ed66a1f8f5426075044187fa35bde900001aade7c` | No immutable counterpart mapped |

## Legacy archive: all retained

Every file below `archive/legacy_v1_2025/artifacts/` has the same disposition: no exact R2 key or explicit immutable provenance mapping. The 22 ratings files include six large NetCDF traces and account for most of this directory's bytes. Reports, MLflow evidence, Hydra outputs, and other historical material remain in place.

| First path component | Files | Apparent bytes | Allocated bytes |
| --- | ---: | ---: | ---: |
| `analysis` | 15 | 878,608 | 909,312 |
| `backtest` | 6 | 651,874 | 667,648 |
| `experiment_log.csv` | 1 | 12,113 | 12,288 |
| `features` | 1 | 121,786 | 122,880 |
| `hydra_outputs` | 42 | 392,188 | 487,424 |
| `mlruns` | 27 | 4,605 | 110,592 |
| `plans` | 2 | 3,810 | 8,192 |
| `ratings` | 22 | 185,078,946 | 185,131,008 |
| `reports` | 336 | 5,477,337 | 6,180,864 |
| `research` | 2 | 1,874 | 8,192 |
| `weather_shap_summary.png` | 1 | 64,869 | 65,536 |
| **Total** | **455** | **192,688,010** | **193,703,936** |

## Before and after

| Working-tree area | Before files | After files | Before apparent bytes | After apparent bytes | Before allocated bytes | After allocated bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Preview training | 5 | 5 | 1,154,627,528 | 1,154,627,528 | 1,154,641,920 | 1,154,641,920 |
| Legacy archive | 455 | 455 | 192,688,010 | 192,688,010 | 193,703,936 | 193,703,936 |
| **Ignored artifact total** | **460** | **460** | **1,347,315,538** | **1,347,315,538** | **1,348,345,856** | **1,348,345,856** |

**Artifact bytes reclaimed: 0.** The only source deletion is the tracked `example_flow.py` working-tree copy (1,674 apparent bytes; 4,096 allocated bytes before removal). Git history retains that file's previous content. No MLflow runs, Hydra outputs, logs, CatBoost diagnostics, or model binaries outside the audited archive were changed.
