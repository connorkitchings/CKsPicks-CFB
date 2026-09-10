# Session: Phase 3 v2 Preflight Scalar Conversion Repair

## TL;DR

- **Worked On:** Second no-write Preview preflight attempt and the remaining
  contained replay-performance repair.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** User explicitly authorized Phase 3 execution on
  2026-09-10. Contract remains `In Progress`.
- **Outcome:** The retry passed vectorized cutoff admission but was stopped
  before its final report when scalar finite-value normalization allocated a
  Pandas Series for every source-history value. The equivalent scalar converter
  and repeated-value reuse now pass locally.
- **Blockers:** A new user-created committed checkpoint is required before the
  next no-write preflight. No Preview evidence is accepted yet.
- **Next:** Commit this repair and retry the exact no-write preflight using the
  resulting SHA.

## Context and Decision

- The second interrupted preflight did not include `--apply`; it created no R2,
  Neon, production, or V4 changes. Its traceback showed the replay inside
  `_finite()` while building transient adjusted-history evidence.
- Replace the one-element `pd.Series`/`pd.to_numeric` allocation with direct
  scalar `float()` conversion, returning null for invalid, missing, and nonfinite
  values exactly as before. Store the source raw value once before reusing it in
  the raw, iteration-zero, and iteration-four history fields.
- This is a mechanical performance repair. It preserves the sealed availability,
  adjustment, candidate, timing, lineage, output, and selection contracts.

## Files Modified

- `src/cks_picks_cfb/ratings/phase3_v2.py` - Scalar finite conversion and
  repeated raw-value reuse in transient history records.
- `tests/test_data_first_phase3_v2.py` - Numeric, missing, invalid, and
  nonfinite scalar conversion coverage.
- `session_logs/2026-09-10/17-phase3-v2-preflight-scalar-repair.md` - This
  execution record and retry handoff.

## Validation

- [x] `uv run pytest -q -W error tests/test_data_first_phase3_v2.py tests/test_data_lake.py` — 30 passed.
- [x] `uv run pytest -q -W error` — 833 passed, 2 skipped.
- [x] Ruff format check and lint for the changed Phase 3 files.
- [x] `git diff --check`.

## Handoff Notes

- **Resume at:** Commit the listed paths, then retry the no-write preflight with
  the resulting full `git rev-parse HEAD` value as `--expected-code-sha`.
- **Watch out for:** Do not use `--apply` until a successful preflight emits and
  the operator inspects its count, digest, and selection evidence.
- **Suggested commit:** `fix(research): streamline phase3 replay scalars`

**tags:** ["phase3", "preview", "performance", "research", "lineage"]
