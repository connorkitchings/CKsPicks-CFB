# Session: Phase 3 v2 Adjusted-History Count Amendment

## TL;DR

- **Worked On:** Implemented the user-approved correction to the active Phase
  3 v2 adjusted-history count gate.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** User explicitly authorized the amendment on
  2026-09-11. The contract remains `In Progress` until Preview preflight,
  apply, independent verification, and idempotent rerun pass.
- **Outcome:** The expected retained adjusted-history count is now 3,067,048,
  the exact result of the six-component four-pass replay. No measurement,
  candidate, fold, timing, selection, or tournament-mathematics rule changed.
- **Next:** Commit this narrow checkpoint, then repeat the exact no-write
  Preview preflight using that committed SHA.

## Amendment Basis

The first no-write Preview preflight produced all required compact and
tournament headline invariants but failed solely because the inherited
adjusted-history count, 6,777,120, had never been supported by a completed
replay. The read-only reconstruction recorded 3,067,048 rows. The replay's
long-standing retained scope is `ADJUSTED_COMPONENTS`, the six measurements
that receive the four-pass opponent adjustment; diagnostic measurements do not
belong in adjusted history.

The corrected invariant is exposed from the Phase 3 data contract and consumed
by the runner. Regression coverage proves the replay history contains only
adjusted components and pins the expected count. The independent verifier still
recomputes the entire preflight and compares output rows, digests, selection,
certification, and compact evidence.

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase3_v2.py` - canonical adjusted-history
  count invariant.
- `scripts/research/run_data_first_phase3_v2.py` - certification consumes the
  canonical invariant.
- `tests/test_data_first_phase3_v2.py` - retained-component scope and invariant
  regression coverage.
- `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md` - approved
  amendment and scope record.
- `docs/plans/index.md` - current Phase 3 status.

## Validation

- [x] `uv run pytest -q -W error tests/test_data_first_phase3_v2.py tests/test_data_lake.py tests/test_data_first_documentation_authority.py` — 36 passed.
- [x] `uv run pytest -q -W error` — 834 passed, 2 skipped.
- [x] Ruff format check and lint for changed Python paths.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `git diff --check`.

## Handoff Notes

- **Resume at:** Commit the listed files, capture `git rev-parse HEAD`, and run
  the exact Phase 3 no-write Preview preflight with that SHA.
- **Watch out for:** Do not use `--apply` until the matching-SHA preflight
  passes and its counts, digests, and selection evidence have been inspected.

**tags:** ["phase3", "preview", "certification", "amendment", "research"]
