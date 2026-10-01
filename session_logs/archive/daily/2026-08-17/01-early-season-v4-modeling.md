# Session: Early-Season V4 Modeling Foundation

## TL;DR

- **Worked On:** Implemented the approved V4 Games 1-4 modeling foundation and Game-4 handoff contract.
- **Outcome:** Canonical routing, ten-route bundle support, optional-talent source policy, result-only established comparator, numerical warning failure, schema migration, comparison tooling, tests, and documentation are in place.
- **Plan Contract:** `docs/plans/2026-08-17/early-season-v4-modeling.md`
- **Approval / Status:** User explicitly authorized implementation; contract remains `In Progress` pending an immutable V4 tournament and Preview rehearsal.
- **Blockers:** A real V4 selection/refit requires a new immutable point-in-time feature snapshot and Preview R2/Neon operation.  No operational artifact was created in this session.

## Work Completed

- Added `game_4` canonical routing, storage contract migration `0008`, publication validation, web display/type support, data-audit coverage, and legacy-label compatibility.
- Extended the ordinal candidate/evaluation/refit path to Games 1-4; Game 4 now evaluates an unchanged established-Ridge comparator as a candidate.
- Added optional-talent V4 snapshot validation and all-or-nothing preseason feature-family availability helpers.
- Made numerical runtime warnings and non-finite model output fatal in candidate fitting and bundle inference.
- Extended private comparison tooling to accept V2, V3, and V4 artifacts.

## Validation

- [x] `.venv/bin/pytest -q` — 348 passed, 2 skipped.
- [x] `.venv/bin/ruff check src/cks_picks_cfb scripts/pipeline tests`.
- [x] `.venv/bin/python contracts/validation.py`.
- [x] `npm run typecheck`, `npm run lint`, and `npm run build` in `web/`.
- [x] `.venv/bin/mkdocs build --quiet`.
- [x] `git diff --check`.

## Handoff Notes

- **Resume at:** Assemble the immutable V4 point-in-time feature reference, run sealed selection and locked 2025 validation, refit a new bundle, then generate the private V2-V3-V4 comparison and Preview rehearsal.
- **Watch out for:** Preserve `artifacts/preview/` as user-owned.  Do not activate a V4 run or submit Pick'em entries without the remaining Preview and explicit approval gates.

**tags:** ["modeling", "early-season", "game-ordinal", "v4"]
