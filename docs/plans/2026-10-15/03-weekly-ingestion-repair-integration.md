# Integrate weekly-ingestion-repair branch remnants

- **Status:** Implemented locally; awaiting owner commit
- **Created:** 2026-10-15
- **Approval source:** Owner reviewed the 2026-10-15 two-week review findings in chat,
  asked for this plan, and approved execution ("proceed").
- **Implementation log:** session_logs/2026-10-15/07-ingestion-repair-integration.md
- **Commit policy:** User-controlled git operations; one commit from an explicit allowlist.

## Goal and acceptance

Integrate the still-unique value of `codex/weekly-ingestion-repair` (`bb2f1fe8`,
committed 2026-10-15 with owner authorization but never merged) into `dev`, reject what
Phase 1 of the review contract (`2807e087`) superseded, and record both decisions.
Documentation and tests only: no serving, database, R2 or runbook-flow changes.

## Background

The branch fixed the same three broken ingestion connections (request inventory, market
capture identity, cumulative input refresh) that Phase 1 of
[01-review-fixes-and-v5-streamline](01-review-fixes-and-v5-streamline.md) fixed in
parallel by automation: `build_season_revision.py`'s controller run performs schedule
re-ingest, per-week request inventories, `plays`/`game_stats` ingest with
`--request-inventory` and the Silver builds, and `build_week_market_snapshot.py` unions
registered captures by `--capture-id`. The operational gap the branch targeted is
therefore already closed on `dev`; the branch's manual lineage.json checklist design is
superseded.

## Adopted

1. **Log-13 correction.** `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md`
   replaced byte-for-byte with the branch's corrected version. Dev's committed version
   (`c48f252e`) was the author's retracted draft claiming "Blockers: None" and passing
   validation for a non-runnable sketch; the replacement retracts those claims.
2. **Fixture tests.** `tests/test_weekly_ingestion_checklist.py` imported, with two
   integration adjustments against Phase 1's hardened builder:
   - Fixture captures are marked `state="registered"` via `dataclasses.replace`;
     `build_week_market_snapshot.py` now refuses anything but registered market
     captures (`SourceCapture.state` defaults to `"staged"`).
   - `test_week8_pending_template_cannot_be_prepared` dropped: its subject was the
     rejected Week 8 template, which does not exist on `dev`. Manifest-refusal
     behavior remains covered by the season/manifest suites.
3. **Contract and logs imported, renumbered** to avoid collisions with the review-fixes
   files of the same date: contract → `02-weekly-ingestion-repair.md` (Status:
   Superseded, with this adopt/reject record), logs → `05-`/`06-` with updated
   references.

## Rejected

1. **Manual-ingestion runbook section.** It contradicts the canonical controller flow
   (runbook step 1c: "Do not run ... by hand"). Nothing ported: the one candidate
   detail, Odds API estimate-before-`--confirm`, is already in step 1b.
2. **`revision_manifest_w8_v1.template.json`.** The builder generates the real manifest
   and refuses overwrite; the cutoff evidence (W7 post-cutoff `2026-10-18T15:00:00Z`,
   W8 pre-cutoff `2026-10-20T18:00:00Z`, 56 games, first kickoff `2026-10-20T23:00:00Z`)
   already lives in runbook step 1a. No stale manifest exists in the main checkout, so
   the runbook's delete-before-regeneration warning is currently precautionary.

## Validation

- `tests/test_weekly_ingestion_checklist.py`: 6 passed (after the two adjustments
  above; the imported file initially failed 2 of 8).
- Season suite, contracts check, quality registry, strict MkDocs, scoped Ruff and
  `git diff --check`: recorded in the implementation log.

## Post-commit cleanup (owner executes)

Delete worktree + branch `codex/weekly-ingestion-repair` (fully integrated or
deliberately rejected by this contract) and worktree + branch `codex/ci-speedup`
(tip `59bb842c` is an ancestor of `dev`).

## Deferred (unchanged by this contract)

The stale "awaiting owner commit" lines for Phase 2 (`docs/status.md`,
`docs/plans/index.md` rows for contracts 2026-10-15/01 and 2026-10-14/01) and the
Phase 2 SHA amendment stay deferred to the Week 8 or Phase 3 session, per session log
`2026-10-15/04`. Week 8 operations remain gated on Sunday 2026-10-18 finals.
