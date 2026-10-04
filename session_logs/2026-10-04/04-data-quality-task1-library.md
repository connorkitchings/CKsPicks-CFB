# Session: Data-quality Task 1 (check library, receipts, CLI)

## TL;DR
- **Worked On:** Task 1 of `docs/plans/2026-10-04/01-pipeline-data-quality-gates.md` and the Window 1 venue fix that blocked the receipt.
- **Outcome:** `src/cks_picks_cfb/quality/` (check registry, severity policy, deterministic immutable receipts, CLI), Make targets, 9 tests. Venue publisher can pin a Silver venues version. No data checks are registered yet.
- **Approval / Status:** User authorized Task 1 on 2026-10-04 (Window 1 code in `850ca38`). Task 4 stays held until the Preview venue dry run passes on the pin and the Window 1 receipt is signed off.

## Decisions (recorded as Amendment 1 in the contract)
- CLI is standalone (`python -m cks_picks_cfb.quality`), not an `ops` subcommand.
- `utils/validation.py` left in place, not ported; removal is a separate prune after Tasks 2–3.

## Venue finding (verified, read-only)
Silver `venues` is one version per capture year; the publisher took the last created (`ac36e3e4`, year 2025). `b569d242e8c4c53b416bfe14` (year 2026) covers all 8 missing venue IDs. `--venues-version` pins it; pinned dry run: 271/271 cities, 269 states. This is also a Task 2 candidate check: a dataset with many same-`as_of` versions needs an explicit pin or a coverage assertion.

## Validation
- Full suite: 1654 passed, 9 skipped. `ruff check .` clean. `mkdocs build` clean. `make quality-check` passes (0 checks).
- Not run: Preview venue write; CI wiring (Task 6).

## Files
- New: `src/cks_picks_cfb/quality/{__init__,checks,receipt,__main__}.py`, `tests/test_quality_library.py`.
- Edited: `Makefile`, `.gitignore` (`artifacts/quality/`), `scripts/pipeline/publish_game_venues.py`, `tests/test_game_venues.py`, the contract, the Window 1 log.
