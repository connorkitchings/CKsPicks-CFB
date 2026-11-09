# Session: CFBD retrospective lines, phase 2 (carry-forward, parity allowance, Preview release)

## TL;DR

- **Worked On:** Finishing the CFBD retrospective-line change for three Week 6 games: carry the `historical_lines` input forward, teach the parity gate the one-off grade additions, re-prepare the candidate, and release it to Preview.
- **Outcome:** Preview serves the new release (id in [`docs/status.md`](../../docs/status.md)); the three games carry six `cfbd_retrospective` grades. Preview record: spread 273-280-9 (562 graded), total 269-290-2 (561). Production untouched.
- **Plan Contract:** [`docs/plans/2026-11-09/cfbd-retrospective-lines.md`](../../docs/plans/2026-11-09/cfbd-retrospective-lines.md)
- **Approval / Status:** Owner approved a Preview release; contract `Implemented` (Preview only).
- **Blockers:** None.
- **Next:** Owner decision on a Production release (weekly runbook section 3).

**tags:** ["season", "grading", "market", "preview", "parity"]

## Context and Decisions

- The phase 1 candidate pinned code commit `cbac0d36`; adding code changes made it stale, so the candidate was re-prepared from the clean committed tree (`make season-prepare WEEK=11 AS_OF=2026-11-08T18:03:33Z MANIFEST=conf/season/2026/revision_manifest_w11_v2.json`) and all 32 checks passed again.
- The allowance lives in `scripts/pipeline/check_release_parity.py` and turns on automatically when the candidate's `revision-manifest.json` carries `historical_lines`, so the weekly automation needs no new flag. It applies in both modes. A game qualifies only while the active release holds no market rows for it; afterwards the grades compare strictly.
- Observed gap, not changed: the parity key normalization masks hex ids, so `market_quotes`, `market_snapshots` and `market_snapshot_quotes` keys collapse and those tables are effectively not compared by the existing gate (they did not show the six new rows). The allowance validates the three games' quote, snapshot, selection and grade rows itself.

## Work Completed

- `revision_manifest` carries `historical_lines` when the previous manifest has it; tests for present (byte-identical) and absent.
- Parity allowance with tests: allowed case passes in both modes; another game, prediction mean, variance, rating snapshot, non-matching grade, foreign quote or snapshot, incomplete rows and a `system_stats` movement that does not match the grades all fail.
- Parity of the candidate against the active Preview release passed in `market-refresh` mode; Preview release made with `EXPECTED_PREVIOUS` set to the active Preview release; read-only checks confirmed the active release, six snapshots and six grades for the three games, the new records, and that without the allowance the only differing games are the three.
- Docs: decision log, record methodology, weekly runbook, `docs/status.md`, contract.

## Files Modified

- `scripts/pipeline/build_season_revision.py`, `tests/test_build_season_revision.py` — carry-forward.
- `scripts/pipeline/check_release_parity.py`, `tests/test_check_release_parity.py` — allowance.
- `docs/decisions/decision_log.md`, `docs/modeling/record_methodology.md`, `docs/ops/weekly_runbook.md`, `docs/status.md`, `docs/plans/2026-11-09/cfbd-retrospective-lines.md` and this log.

## Validation

- [x] `make check` (ruff, contracts, quality registry, 2380 tests, mkdocs strict, web lint, typecheck, publication tests, build) before the code commits
- [x] `make season-prepare` (32 checks passed), parity PASS, Preview release, read-only SQL checks
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Owner decision on Production.
- **Watch out for:** The docs commit changes `HEAD` after the code pin; a Production release of this candidate would need a re-prepare from the final commit.
