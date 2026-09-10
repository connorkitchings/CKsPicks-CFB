# Session: Phase 3 v2 Preflight Performance Repair

## TL;DR

- **Worked On:** Required no-write Preview preflight for the compact-state
  Phase 3 v2 contract, followed by a contained replay-performance correction.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** User explicitly authorized Phase 3 execution on
  2026-09-10. Contract remains `In Progress`.
- **Outcome:** The preflight made no R2 writes and was stopped before completion
  after revealing a row-wise availability filter at every weekly cutoff. The
  equivalent vectorized filter and regression coverage now pass locally.
- **Blockers:** A new user-created committed checkpoint is required before retrying
  the no-write preflight with its matching `--expected-code-sha`.
- **Next:** Commit the two Phase 3 repair paths and this log, then rerun the
  exact no-write Preview preflight.

## Context and Decision

- The bounded compact-state design was correct about retained memory, but
  `_history_for_cutoff` still evaluated the sealed six-hour availability rule
  row-by-row over a season's observations for every target-week cutoff. The
  full historical preflight remained in this repeated pandas `apply` path and
  did not emit its final report during the bounded observation window.
- This is a mechanical performance repair, not a change to Phase 3 mathematics,
  lineage, timing, candidate registry, output schema, or acceptance criteria.
  The new predicate preserves prior-week-only admission and inclusive
  `source_kickoff + 6h <= target_cutoff` behavior.
- The interrupted command did not include `--apply`; it created no Preview R2,
  Neon, production, or V4 changes. The traceback was captured while computing
  the read-only historical replay.

## Files Modified

- `src/cks_picks_cfb/ratings/phase3_v2.py` - Vectorize cutoff admission using
  the sealed shared availability-buffer constant.
- `tests/test_data_first_phase3_v2.py` - Cover the replay's inclusive cutoff
  and same-week exclusion through the vectorized history path.
- `session_logs/2026-09-10/16-phase3-v2-preflight-performance-repair.md` -
  execution evidence and retry handoff.

## Validation

- [x] `uv run pytest -q -W error tests/test_data_first_phase3_v2.py tests/test_data_lake.py` — 29 passed.
- [x] `uv run pytest -q -W error` — 832 passed, 2 skipped.
- [x] Ruff format check and lint for the changed Phase 3 files.
- [x] `git diff --check`.

## Handoff Notes

- **Resume at:** After the user commits this correction, use the resulting full
  `git rev-parse HEAD` value in the no-write preflight command.
- **Watch out for:** Do not use `--apply` until the preflight exits successfully
  and its count, digest, and selection report have been inspected.
- **Suggested commit:** `fix(research): vectorize phase3 replay availability`

```text
PYTHONPATH=.:src uv run python scripts/research/run_data_first_phase3_v2.py \\
  --repair-manifest-uri artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json \\
  --run-id phase3-v2-compact-state-20260910 \\
  --expected-code-sha "$(git rev-parse HEAD)" \\
  --environment preview \\
  --as-of 2026-09-10T00:00:00Z
```

**tags:** ["phase3", "preview", "performance", "research", "lineage"]
