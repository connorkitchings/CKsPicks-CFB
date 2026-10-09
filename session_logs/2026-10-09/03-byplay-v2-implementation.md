# Session: byplay_v2 Tasks 1 and 2 (impact diff, then versioned identity contracts)

## TL;DR
- **Worked On:** Task 1 (read-only shadow impact diff and clock census, committed as `f1807135`), then Task 2 (versioned identity contracts) after the user's decisions.
- **Outcome:** Task 2 delivered. `byplay_v2` and `drives_v2` are registered beside v1; the pipeline, drives aggregation and the 6A silver stage can build them (opt-in); v2 builds refuse v1 parents. Real-data runs reproduce the Task 1 predictions exactly. Task 3 is gated on the period-label diagnostic.
- **Plan Contract:** `docs/plans/2026-10-09/01-byplay-v2-play-identity.md` (In Progress; Amendments 1 and 2)
- **Approval / Status:** Contract Approved 2026-10-09. The user decided on Task 1: keep the unresolved rule, run the period diagnostic before Task 3, proceed with Task 2.
- **Blockers:** None for Task 2. Task 3 waits for the diagnostic.
- **Next:** read-only diagnostic of the 310 period-reset plays, then Task 3.

## Context and Decisions
- The only storage access was reads of pinned Preview R2 parents (`conf/rebuild/phase2c_silver_parents_v1.json`, `silver_2026_parents_w5_v1.json`) through the existing `get_storage` path. No R2, database or serving write occurred.
- The retained variant is a shadow: the unchanged v1 pipeline runs on the collision games with shadow sequence numbers that follow `(period, drive_number, play_number)`. It sizes the change; it is not the v2 implementation. Ties are ordered by file row order inside the shadow only and are reported as unresolved.
- Added a variant that removes the 6 unresolved plays from the shadow input, to bound the effect of the exclusion rule.
- The clock census treats the clock as diagnostic only and applies no exclusion. A split was added after finding corrupt clock values (39 regulation rows above 15 minutes in 2021) and period-boundary resets.

## Work Completed
- `scripts/analysis/play_identity_impact.py`: source-ID typing (string, floats rejected), unresolved-play rule, clock census, collision classification, drive-reuse census, shadow retention, cell-level frame diff, token remapping.
- `scripts/analysis/play_identity_shadow.py`: runs the real pipeline and `build_measurements` on the collision games for the historical, retained and retained-excluding-unresolved variants, checks fidelity to the pinned legacy by-play and drives, and reports descendants by key.
- `tests/test_play_identity_impact.py`: 19 tests covering same-second plays, reversals, impossible clocks, ties, cross-period reuse, missing periods, renumbering, string typing, drive reuse, diff and remapping.
- `docs/plans/2026-10-08/repair-track-evidence/play-identity-impact.json` (341 KB) plus its `checksums.json` entry; the 14-file manifest verifies.

## Files Modified
- New: the two scripts, the test file, the evidence report, this log.
- Modified: `docs/plans/2026-10-08/repair-track-evidence/checksums.json` (one entry), `docs/plans/2026-10-09/01-byplay-v2-play-identity.md` (status, log path, Amendment 1).

## Validation
- [x] `uv run pytest tests/test_play_identity_impact.py -q -W error`: 19 passed.
- [x] Two full report runs are byte-identical.
- [x] The evidence manifest verifies all 14 files.
- [x] The stop conditions did not fire: unresolved plays equal the same-period collision groups (6 plays in 3 groups), and no game outside the 4 collision games shows drive-number reuse. Invariance outside the collision keys is Task 5's proof, not claimed here.
- [x] `ruff format --check .` (738 files), `ruff check .`, `git diff --check` and `mkdocs build --strict` pass; 82 tests passed in the focused run (this file plus `test_new_features.py` and `test_ledger_conversion.py`). The full suite was not rerun: no `src/` file changed this session.

## Amendments and Blockers
- Amendment 1 in the contract (receipt and findings; no change of approach).

## Handoff Notes
- **Resume at:** user decision on Task 2. If confirmed, Task 2 starts from the draft patch with the strict string conversion.
- **Watch out for:** the period label is wrong for at least some plays (310 resets to a fresh 15:00 clock), and 1,702 valid-clock reversals exceed 60 seconds. The period-first ordering assumes the period label is right; this deserves its own read-only check before Task 3 relies on it.
- **Commit proposal (user-run):** `feat(analysis): add read-only play-identity impact diff and clock census`. It covers the two scripts, the test file, the evidence report and checksum entry, the contract edits and this log. Do not include `02-week6-display-production-*` files; they belong to another session.

**tags:** ["integrity", "pipeline", "analysis"]

## Task 2 (this session, second half)

### Work Completed
- New `src/cks_picks_cfb/data/play_identity.py`; v2 schemas and Silver contract revisions; v2 path in `allplays_to_byplay`, `aggregate_drives` and `build_preaggregation_pipeline`; lineage guard in `build_dataset_version`; opt-in `play_identity` policy in the 6A silver stage with a key-joined comparison. Details and the real-data table are in Amendment 2 of the contract.
- Found and fixed a design error before it landed: `drives_v2` keyed on `drive_id` alone would have merged 8,959 kickoff rows in 2021. The 2021 smoke run (`drives_rows_equal` false) exposed it; the key now includes offense and defense.
- Corrected a Task 1 statement: the `field_position_bin` difference is a missing-value representation (NaN vs the string `'nan'`), not a code change. The correction is recorded in the contract next to the original claim.

### Files Modified
- New: `src/cks_picks_cfb/data/play_identity.py`, `tests/test_play_identity_v2.py`.
- Modified: `src/cks_picks_cfb/data/{schema_contracts,lake}.py`, `src/cks_picks_cfb/data/silver/contracts.py`, `src/cks_picks_cfb/features/{pipeline.py,byplay/enrichment.py,aggregations/drives.py}`, `src/cks_picks_cfb/rebuild/silver.py`, `tests/test_rebuild_silver.py`, `tests/test_schema_contracts.py`, the contract and this log.

### Validation
- [x] Full suite with `-W error`: 2,294 passed, 14 skipped (was 2,239 before Task 1; the difference is the new tests).
- [x] `ruff check .` and `git diff --check` pass. `ruff format --check .` flags one file I did not change, `src/cks_picks_cfb/data/matchup_publish.py`, which belongs to the separate matchup 6A bridge work (also modified: `publish_matchup_data.py`, `verify_matchup_data.py`, `03-matchup-6a-bridge.md`). All files from this session are formatted.
- [x] All 83 pre-existing schema hashes unchanged; v1 hashes pinned by a test.
- [x] Real-data smoke for 2021, 2022 (control) and 2025, plus the stage `verify`: see the contract table.
- [x] `mkdocs build --strict`, `make contracts-check` and the quality registry listing pass after the final doc edits.

### Handoff Notes
- **Resume at:** the read-only diagnostic of the 310 plays that reset to a fresh 15:00 clock: do they sit in drives that are fragmented or cross a quarter boundary under `(period, drive_number, play_number)`? Then Task 3.
- **Watch out for:** do not stage the matchup-bridge files with this work. Task 4 must add the v2 possession, ledger and observation versions to `REQUIRES_V2_PLAY_IDENTITY`. Net punt yards still pairs drives by number.
- **Commit proposal (user-run):** `feat(identity): add byplay_v2 and drives_v2 provider-keyed play identity`. Stage `src/cks_picks_cfb/data/play_identity.py`, the modified `data/{schema_contracts,lake}.py`, `data/silver/contracts.py`, `features/{pipeline.py,byplay/enrichment.py,aggregations/drives.py}`, `rebuild/silver.py`, the three test files, the contract and this log.

