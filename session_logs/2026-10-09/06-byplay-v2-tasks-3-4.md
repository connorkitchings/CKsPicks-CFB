# Session: byplay_v2 diagnostic evidence and Task 3 (ordering), then Task 4

## TL;DR
- **Worked On:** Step 1 (persist the period-label diagnostic, Amendment 3, known issues 16 and 17) and Task 3 (shared play order, persisted unresolved flags, v1 golden regression).
- **Outcome:** Both delivered and validated. Task 4 has not started; this is the Task 3 stop gate.
- **Plan Contract:** `docs/plans/2026-10-09/01-byplay-v2-play-identity.md` (In Progress; Amendments 3 and 4)
- **Approval / Status:** The user approved the Tasks 3–4 plan (decisions: neutrality rule, Task 4 includes envelope/evidence/Gold wiring via re-keying, net punt yards preserved outside collision games). Format/lint stop gates are scoped so the other session's files cannot mask results.
- **Blockers:** None.
- **Next:** Task 4, in two commits: 4.1–4.4 (identity, ledger, verifier, Gold converters), then 4.5–4.7 (admission re-key, rebuild wiring, net punt yards).

## Context and Decisions
- Baseline confirmed clean: Task 2 committed as `a226c56f`; the other session's matchup bridge is committed too (`3e20f2ce`), so the earlier `ruff format` warning on `matchup_publish.py` is gone.
- v1 was frozen before any edit: the golden digests and eight v1 schema hashes were recorded from untouched source and still pass.
- The diagnostic was persisted rather than left in chat: 310 plays on a fresh 15:00 clock (289 at a drive boundary); 245 games with backwards drive numbers where period-first is not worse than drive-first (75 / 75 / 95). `(period, drive_number, play_number)` stays the order.

## Work Completed
- `scripts/analysis/play_order_diagnostic.py`, `tests/test_play_order_diagnostic.py`, `repair-track-evidence/period-label-diagnostic.json` (two runs byte-identical; 15-file manifest verifies), known issues 16 (net punt yards) and 17 (stale period labels / clock disagreement), contract Amendments 3 and 4.
- `src/cks_picks_cfb/data/play_order.py` and its tests; flags persisted on `byplay_v2`; `drives_v2` boundary-tie handling; helper adopted in `possession_measurements.py` and `metrics/ledger.py`; period-first score-stream check for v2 only; `require_v1_byplay` in `observations.py` and `score_envelope_r1.py`.

## Files Modified
- New: `src/cks_picks_cfb/data/play_order.py`, `scripts/analysis/play_order_diagnostic.py`, `tests/test_play_order.py`, `tests/test_play_order_diagnostic.py`, `tests/test_v1_play_order_invariance.py`, `docs/plans/2026-10-08/repair-track-evidence/period-label-diagnostic.json`, this log.
- Modified: `data/{play_identity,schema_contracts}.py`, `data/silver/contracts.py`, `features/byplay/enrichment.py`, `features/aggregations/drives.py`, `ratings/{possession_measurements,observations,score_envelope_r1}.py`, `metrics/ledger.py`, `quality/silver.py`, `tests/test_play_identity_v2.py`, `repair-track-evidence/checksums.json`, `docs/data/known_issues.md`, the contract.

## Validation
- [x] Full suite `-W error`: 2,344 passed, 15 skipped (the added skip is the other session's disposable-PostgreSQL test; none of this work's tests skip).
- [x] `ruff format --check .` (747 files) and `ruff check .` clean; `git diff --check`, `make contracts-check`, `mkdocs build --strict` pass.
- [x] Real-data acceptance (contract Amendment 4): 6 unresolved plays (2021: 2, 2025: 4), 0 missing periods, row and drive counts equal the Task 2 run, 0 drive edges nulled.
- [x] v1 golden digests and schema hashes unchanged.

## Handoff Notes
- **Resume at:** Task 4.1 — `data/data_first_possession_v2.py`, possession/Gold schema revisions, lineage set. Confirm the commit of this work first.
- **Watch out for:** the independent verifier must not import `data.play_order` (add it to the banned-import test); never edit a v1 schema entry or pin; the v1-pinned rebuild modules are guarded in 4.6, not before.
- **Commit proposal (user-run):** `feat(ordering): add shared play order, unresolved-play flags and v1 golden regression` — stage the new and modified files listed above.

**tags:** ["integrity", "pipeline", "ordering"]

## Task 4.1–4.4 (second half of this session)

### Work Completed
- Identity module, schema revisions and lineage set; builder v2 with the tie-neutrality rule; the independent verifier's own v2 path (it recomputes tie flags from raw columns and rejects forged ones); Gold converters and contract validators. Details, decisions and the real-data table are in Amendment 5 of the contract.
- A shared logic bug (the "next event" marker consumed inside the tie group) was found by a scenario test and fixed in both implementations; the agreement test could not have caught it.
- The stop-gate comparison is now reproducible evidence: `scripts/analysis/possession_v2_comparison.py` and `repair-track-evidence/possession-v2-comparison.json` (two final runs identical; 16-file manifest verifies).

### Files Modified
- New: `src/cks_picks_cfb/data/data_first_possession_v2.py`, `scripts/analysis/possession_v2_comparison.py`, `tests/test_possession_v2.py`, `tests/test_gold_v2.py`, `tests/test_possession_v2_comparison.py`, `repair-track-evidence/possession-v2-comparison.json`.
- Modified: `data/{play_identity,schema_contracts}.py`, `metrics/{ledger,contracts}.py`, `ratings/{possession_measurements,possession_verification}.py`, `tests/ratings/test_possession_verification.py`, `repair-track-evidence/checksums.json`, the contract and this log.

### Validation
- [x] Full suite `-W error`: 2,384 passed, 15 skipped; ruff (752 files), `git diff --check` and `make contracts-check` clean.
- [x] v1 golden digests and eight v1 schema hashes unchanged throughout.
- [x] Real data: producer equals verifier on all four frames in 2021, 2022 and 2025; 2022 identical to v1; 2021 and 2025 differ only in the collision games, with the exact observation counts Task 1 predicted; no differing shared event and no scoring point moves.

### Handoff Notes
- **Resume at:** 4.5 — `scripts/analysis/rekey_admission_v2.py` and the v2 paths in `score_envelope_r1.py`, `admission.py`, `metrics/evidence.py`, `build_admitted_ledger_5c.py` and `possession_verification.verify_admitted_ledger`.
- **Watch out for:** `web/*` and `README` changes in the worktree belong to another session; do not stage them. The 94% season guard means any real-season run needs an explicit population.
- **Commit proposal (user-run):** `feat(identity): add provider-keyed possession ledger, independent verifier and Gold converters`.

