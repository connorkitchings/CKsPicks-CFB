# Session: CFBD retrospective lines, phase 1 (prepared candidate)

## TL;DR

- **Worked On:** Giving three ungraded Week 6 games (Southern Miss at Troy, Jacksonville State at Kennesaw State, New Mexico State at Florida International) `cfbd_retrospective` spread and total grades, up to a prepared Preview candidate.
- **Outcome:** New `historical_lines` Silver version built from the registered Week 6 CFBD capture, `revision_manifest_w11_v2.json` committed, candidate prepared. Nothing activated. The run ID, payload SHA-256 and before/after comparison are in the run manifest under `artifacts/season/2026/preview/` and the hand-off report.
- **Plan Contract:** [`docs/plans/2026-11-09/cfbd-retrospective-lines.md`](../../docs/plans/2026-11-09/cfbd-retrospective-lines.md)
- **Approval / Status:** Owner request, Preview only; contract `In Progress`.
- **Blockers:** None for phase 1.
- **Next:** Orchestrator decides on the Preview release, parity check and Production per the weekly runbook; decide how later weekly manifests carry `historical_lines`.

**tags:** ["season", "grading", "market", "preview"]

## Context and Decisions

- The three games kicked off 2026-10-07 before any capture, so no retained pre-kickoff quote exists and they are ungraded.
- The registered CFBD capture of 2026-10-08T16:19Z already holds their Bovada and DraftKings lines. It was used instead of a fresh fetch: no provider call, no new capture, and no rewrite of the compatibility raw partition that `ingest_week.py` overwrites for the whole week.
- `captured_at` and the Week 11 cutoff of the base manifest were kept, so the live slate is reproduced exactly and only the three games can change.

## Work Completed

- `derive_manifest` generalized to accept `historical_lines`; new `build_historical_lines_revision.py` and tests.
- Built and registered the `historical_lines` Silver version; wrote `revision_manifest_w11_v2.json`.
- Committed, then ran `make season-prepare` for Week 11 from the clean tree.

## Files Modified

- `scripts/pipeline/build_market_revision.py` — optional `quotes_input`, new `historical_lines`.
- `scripts/pipeline/build_historical_lines_revision.py` — new builder.
- `tests/test_build_historical_lines_revision.py` — new tests.
- `conf/season/2026/revision_manifest_w11_v2.json` — new revision.
- `docs/plans/2026-11-09/cfbd-retrospective-lines.md` and this log.

## Validation

- [x] `tests/test_build_historical_lines_revision.py`, `tests/test_build_market_revision.py`, season prepare and projection tests
- [x] `make lint`, `make contracts-check`, `make quality-check`
- [ ] `make check` stops at web lint: this worktree has no `node_modules`, so `eslint` is missing (environment, not code)
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Preview release step of the weekly runbook, after the orchestrator approves.
- **Watch out for:** `build_season_revision.revision_manifest` does not carry `historical_lines`, so the next close-week manifest would drop these three grades.
