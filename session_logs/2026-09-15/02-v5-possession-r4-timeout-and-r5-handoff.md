# Session: V5 Possession R4 Bounded Apply Outcome

## TL;DR

- **Worked On:** Executed the committed `b6ec5fc` V5-02 Preview preflight and
  its evidence-bound apply under the approved 30-minute invocation cap.
- **Outcome:** The dry preflight passed. The apply was intentionally stopped
  mid-replay before the cap because synchronous immutable child-part writes
  made timely finalization impossible. The `r4` prefix is failed and
  ineligible; it contains only its immutable publication plan, not a manifest.
  Amendment 3 adds bounded concurrent child-part materialization for a new
  SHA-bound `r5` attempt.
- **Plan Contract:**
  `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md`
  (Amendment 3).
- **Approval / Status:** User's prior implementation authorization remains in
  scope. Contract remains **In Progress**.
- **Blockers:** The Amendment 3 checkpoint requires a user-controlled commit,
  then a complete fresh r5 preflight/apply/verifier/idempotency sequence.

## Evidence

- Clean committed code before r4: `b6ec5fc2882cc886867d8a82d865c0a79fef6bea`.
- Frozen r4 identity: `possession-v1-measurements-20260915-b6ec5fc-r4`,
  `as_of=2026-09-15T14:03:45Z`, Preview R2, with the immutable Repair v2
  parent `repair-v2-20260909T1417Z`.
- R4 no-write preflight passed with identity SHA
  `d0836e580e61774d069d739ba6d2597848c2e27c0aff80fdbeb7de307fb57563`,
  certification SHA
  `be4fcb6ec1e50356f1230b5831bb775e5383507f2c51cc736476a15badd15fa1`,
  and the expected 8,936/8,935 population invariant.
- Its eight row counts and record digests exactly matched the reviewed r3
  preflight and preserved diagnostic producer evidence.
- The r4 target prefix was empty before apply. After the bounded stop, it held
  only `publication-plan.json` (50,173 bytes, ETag
  `b6dbc97bfae6c97cf2af8505b32da584`). It has no measurement manifest and is
  permanently ineligible as a V5-03 parent.

## Decision

The evidence-bound writer still reconstructed exactly once, but it performed
R2 child-part writes synchronously within that replay. The dry run completed
within its cap while the apply reached only 2019 replay near the limit. The
new bounded eight-worker materialization preserves every ordered-plan and
per-part integrity gate while allowing independent immutable writes to overlap
the same replay. No failed prefix or manifest will be reused.

## Files Modified

- `src/cks_picks_cfb/data/lake.py` — optional bounded concurrent immutable
  part materialization, preserving ordered manifest construction.
- `scripts/research/run_data_first_possession_measurements.py` — V5-02 uses
  the bounded writer mode only for Preview apply.
- `tests/test_data_lake.py` — parallel writer order/identity regression.
- `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md` —
  Amendment 3.
- `session_logs/2026-09-15/02-v5-possession-r4-timeout-and-r5-handoff.md` —
  this record.

## Resume

1. Commit the Amendment 3 checkpoint and capture its full SHA.
2. Select a new unused
   `possession-v1-measurements-20260915-<sha7>-r5` prefix and fresh shared UTC
   `as_of` value.
3. Repeat the no-write preflight, review it, then run the identical
   evidence-bound Preview apply with the 30-minute cap.
4. Continue only on successful apply to independent verification and exact
   idempotency evidence.

**tags:** ["v5", "possession", "certification", "r2", "preview", "timeout"]
