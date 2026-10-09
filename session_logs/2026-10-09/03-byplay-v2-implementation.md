# Session: byplay_v2 Task 1 (shadow impact diff and clock census)

## TL;DR
- **Worked On:** Task 1 of the byplay_v2 contract, read-only.
- **Outcome:** Delivered the shadow impact diff and the clock-reversal census as a checksummed, deterministic report. Task 2 has not started; it waits for the user's confirmation of the numbers.
- **Plan Contract:** `docs/plans/2026-10-09/01-byplay-v2-play-identity.md` (In Progress; Amendment 1 records the receipt)
- **Approval / Status:** Contract Approved by the user 2026-10-09; user directed "Task 1 only".
- **Blockers:** None. Stop gate by design.
- **Next:** User reviews the findings below, then decides on Task 2 and on the two open questions.

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
