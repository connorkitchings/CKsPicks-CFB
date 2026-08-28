# Session: R1 Manifest-Declared Play-Coverage Remediation

## TL;DR

- **Worked On:** Implemented the approved R1 reconciliation remediation for
  explicitly recorded CFBD play omissions.
- **Outcome:** The successor R1 path now permits only manifest-declared
  zero-row games to remain visible as `incomplete_source`; all undeclared
  omissions and data conflicts remain blocking. A fresh full-corpus Preview
  run awaits the required user-controlled commit.
- **Plan Contract:**
  `docs/plans/2026-08-28/r1-manifest-declared-play-coverage-remediation.md`
- **Approval / Status:** User approved implementation in Codex on 2026-08-28;
  contract remains `In Progress` until the fresh R1 run and exact rerun finish.
- **Blockers:** R1 preflight requires a clean committed code identity. R2 stays
  blocked pending `tournaments_permitted: true`.
- **Next:** User commits this implementation, then execute a fresh Preview-only
  `prepare-rating-history` run and verify certification plus an exact rerun.

## Context and Decisions

- Failed diagnostic run `r1-full-corpus-20260828-929f331` captured every
  permitted season and closed its source set, but stopped in 2015 derived data
  because seven completed games lacked play-derived team rows.
- Those seven IDs exactly match the completed immutable 2015 play-capture
  manifest's `missing_game_ids`; no manifest reports extra game IDs.
- The R1 contract's 90% play-coverage gate remains unchanged. The corrected
  in-memory reconstruction has 717 covered of 724 completed games (99.03%),
  seven `incomplete_source` rows, and zero blocking conflicts.
- The exception is opt-in and manifest-bound. Standard reconciliation callers,
  V4, production, and all calls without a manifest retain strict behavior.

## Work Completed

- Added `manifest_declared_missing_game_ids()` to validate complete v2 capture
  manifests: season, request/capture identities, expected/returned/missing
  coverage, duplicate IDs, and extra game IDs.
- Extended reconciliation with an optional declared-incomplete allowlist. Only
  a declared zero-row game is nonblocking; partial rows, undeclared omissions,
  and mismatched team-stat identities remain blocking.
- Added `--play-capture-manifest-uri` to the team-game builder and wired it
  only into the successor R1 season-scoped graph.
- Added the builder and reconciliation modules to the R1 committed-code guard.
- Persisted the remediation contract and amended the governing R1 contract.

## Files Modified

- `src/cks_picks_cfb/data/{history_play_capture,reconciliation}.py` — manifest
  validation and strict opt-in classification.
- `scripts/pipeline/build_team_game_dataset.py` — manifest CLI boundary.
- `src/cks_picks_cfb/ops/__main__.py` — R1-only wiring and commit guard.
- `tests/test_{history_play_capture,silver_reconciliation,ops_state_machine}.py`
  — boundary and orchestration coverage.
- `docs/plans/2026-08-28/...`, `docs/plans/index.md`, and the governing R1
  contract — approved execution record.

## Validation

- [x] Focused lint and tests: `46 passed`.
- [x] Full Python suite: `575 passed, 2 skipped`.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `git diff --check`.
- [x] Read-only Preview reconstruction against the failed R1 artifacts:
  724 completed, 717 covered, exactly seven declared omissions, zero blocks.
- [ ] Fresh committed-code R1 Preview capture, certification, and exact rerun.

## Amendments and Blockers

None. The implementation preserves source authority and every existing R1
threshold; it changes only the timing of where the already-approved coverage
gate is evaluated.

## Handoff Notes

- **Resume at:** After the user commits, run the fresh Preview-only R1 command
  from `docs/ops/rating_successor_research.md` with a new
  `r1-full-corpus-20260828-<committed-short-sha>` pipeline ID.
- **Watch out for:** Do not reuse the failed source set as a parent, do not
  weaken any coverage gate, do not include 2020/2026 outcomes, and do not
  start R2 until immutable certification reports `tournaments_permitted: true`.

**tags:** ["r1", "reconciliation", "historical-data", "preview", "ratings"]
