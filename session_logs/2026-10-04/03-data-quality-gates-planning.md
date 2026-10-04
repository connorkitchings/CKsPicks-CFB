# Session: Data-quality gates planning

## TL;DR
- **Worked On:** Surveyed existing pipeline validation and drafted a contract for ingestion, Silver/Gold, publish-boundary and web read-side quality gates.
- **Outcome:** Draft contract `docs/plans/2026-10-04/01-pipeline-data-quality-gates.md`. No code changed.
- **Approval / Status:** Approved 2026-10-04 by the user after review, with stipulations: (1) implementation starts only after Window 1 code is committed; (2) Task 5 parsers use `rowsOf()`/`existsFrom()` from `web/src/lib/db-result.ts` and support `CFB_UI_TEST_MODE=1`; (3) re-verify the unverified survey entry points before Tasks 2 and 3.
- **Next:** Finish and commit Window 1, then start Task 1.

## Evidence
- Survey was delegated and is **agent-reported**; four claims were re-checked by me: `utils/validation.py` has no callers beyond its tests; `validate_frame` is called in `data/lake.py:219-222`; `require_reconciled` is called only by the phase2c build and `build_team_game_dataset.py`; `make audit-data` and `make contracts-check` exist. The other file and line references are unverified.
- Gap list: no Bronze checks, no data checks in CI, no publish-boundary uniqueness/null/range assertions, no web row parsing, gate 6 missing, gates 2 and 4 not persisted.

## Files
- New: the contract and this log. Edited: `docs/plans/index.md` (one row).

## Handoff
- Commit message if kept: `docs: draft pipeline data-quality gates contract`
