# Session: Repository architecture review and risk-stratified engineering plan

## TL;DR

- **Worked On:** Full repository technical review across Neon storage and release lifecycle, Python season preparation (`prepare`) performance, PostgreSQL/Drizzle web query execution, 2026 holdout replay readiness, V5/V6 modeling roadmap, and CI/Makefile guardrails; reconciliation of post-PR #39 (`a7d03f2d`) release authority and risk-isolated split of the 2026 holdout replay contract.
- **Outcome:** Persisted the approved review and engineering plan contract, reconciled `docs/status.md`, `docs/plans/index.md` and seven PR #39 contract headers, amended `05-holdout-replay-readiness.md` and `01-data-architecture-operational-safeguards.md` to keep the live `dev` weekly pipeline untouched during Weeks 13–15, and documented all offseason code/database/web findings and shadow-verification gates in `01-web-read-performance.md` and `offseason-2027-backlog.md`.
- **Plan Contract:** [`docs/plans/2026-11-18/repo-review-and-offseason-engineering.md`](../../docs/plans/2026-11-18/repo-review-and-offseason-engineering.md) and [`docs/plans/2026-11-12/05-holdout-replay-readiness.md`](../../docs/plans/2026-11-12/05-holdout-replay-readiness.md)
- **Approval / Status:** Owner approved Phase A1 (authority sync), Phase A2 (read-only holdout replay split) and full documentation of all findings (Phase A3 / Phase B) on 2026-11-18 ("1) A1 - yes, A2 - yes. 2) Yes. Also, you can document all of your findings despite the constraints I added").
- **Blockers:** None
- **Next:** Open a fresh Terra task to implement Phase 1 (Tasks 1 and 3 only: read-only git-pin recovery verification and standalone `scripts/research/export_2026_holdout.py`) of [`docs/plans/2026-11-12/05-holdout-replay-readiness.md`](../../docs/plans/2026-11-12/05-holdout-replay-readiness.md).

**tags:** ["planning", "architecture", "review", "performance", "operations"]

## Context and Decisions

- Starting state: clean `dev` at `aae08563`; `origin/main` at `a7d03f2d` (`Merge pull request #39 from connorkitchings/dev`, merging `1036c7e1`).
- Owner constraints recorded 2026-11-18:
  1. **No Neon storage or database pruning changes in-season:** Weeks 13–15 ride on existing headroom; the release prune/compaction CLI (`prune_season_releases.py`) and dropping the redundant 420-byte/row `source_versions` JSONB on `team_season_stats` (~36,432 rows/release) are deferred to the offseason.
  2. **Isolate the live weekly pipeline (`weekly-season-update.yml` on `dev`) during Weeks 13–15:** Defer any live controller or season-engine code edits (`weekly_automation.py`, `refresh_score_exceptions.py`, `offsets.py`, `inputs.py`) until after the 2026-12-13 final regular-season close, and enforce a strict shadow parity gate (100% byte-identical `serving-projections.json` SHA-256 for Python changes; loader JSON snapshot parity + `EXPLAIN (ANALYZE, BUFFERS)` verification for web CTE changes) when they run in the offseason.

## Work Completed

- Created [`docs/plans/2026-11-18/repo-review-and-offseason-engineering.md`](../../docs/plans/2026-11-18/repo-review-and-offseason-engineering.md) recording all technical findings, file/line references, quantified measurements and offseason shadow-verification gates.
- Reconciled [`docs/status.md`](../../docs/status.md), [`docs/plans/index.md`](../../docs/plans/index.md) and seven November contract status headers with PR #39 (`a7d03f2d` on `main`).
- Amended [`docs/plans/2026-11-12/05-holdout-replay-readiness.md`](../../docs/plans/2026-11-12/05-holdout-replay-readiness.md) and [`docs/plans/2026-10-28/01-data-architecture-operational-safeguards.md`](../../docs/plans/2026-10-28/01-data-architecture-operational-safeguards.md) to approve Phase 1 (Tasks 1 & 3: read-only git-pin verification and standalone holdout export CLI) now while deferring Task 2 / Stage 1a controller exception pinning to post-2026-12-13.
- Amended [`docs/plans/2026-10-29/01-web-read-performance.md`](../../docs/plans/2026-10-29/01-web-read-performance.md) and [`docs/planning/offseason-2027-backlog.md`](../../docs/planning/offseason-2027-backlog.md) with the PostgreSQL double-referenced CTE materialization findings (`tie-sql.ts`, `getCurrentRatings`, correlated `prediction_grades` subqueries), eager `/stats` chart loading, `offsets.py` ~460,000 inner-loop DataFrame scans, `measurement-cache` git-HEAD invalidation, and Neon per-row `source_versions` JSONB bloat.

## Files Modified

- `docs/plans/2026-11-18/repo-review-and-offseason-engineering.md` — new approved review and risk-stratified engineering contract
- `docs/status.md` — updated release state and open items for PR #39 (`a7d03f2d`)
- `docs/plans/index.md` — linked new 2026-11-18 contract and reconciled PR #39 merged contract states
- `docs/plans/2026-11-12/05-holdout-replay-readiness.md` — approved Phase 1 (Tasks 1 & 3) and deferred Task 2 controller changes to post-2026-12-13
- `docs/plans/2026-10-28/01-data-architecture-operational-safeguards.md` — recorded post-2026-12-13 deferral of live controller exception pinning
- `docs/plans/2026-10-29/01-web-read-performance.md` — added PostgreSQL double-referenced CTE materialization, `/stats` lazy loading, and loader snapshot parity gates
- `docs/planning/offseason-2027-backlog.md` — added Neon release prune/provenance slimming, `prepare` speedup, Stage 1a deferral, and web CTE items
- `docs/plans/2026-11-16/final-site-corrections.md`, `docs/plans/2026-11-15/site-redesign-and-analytical-usability.md`, `docs/plans/2026-11-12/06-monday-kickoff-time-refresh.md`, `docs/plans/2026-11-12/04-score-attribution-investigation.md`, `docs/plans/2026-11-12/03-prediction-error-diagnostics.md`, `docs/plans/2026-11-12/01-near-kickoff-line-capture.md`, `docs/plans/2026-11-11/regular-season-end-state.md` — updated `Status:` lines to reflect PR #39 (`a7d03f2d`)

## Validation

- [x] `git diff --check`
- [x] `.venv/bin/mkdocs build --strict -d /tmp/mkdocs-site` (passes; existing INFO notices only)
- [x] `.venv/bin/python contracts/validation.py` (`Contracts validation passed.`)
- [x] `PYTHONPATH=src .venv/bin/python -m cks_picks_cfb.quality --verify-registry` (`32 checks, 0 problems`)

## Amendments and Blockers

- Amended `docs/plans/2026-11-12/05-holdout-replay-readiness.md`, `docs/plans/2026-10-28/01-data-architecture-operational-safeguards.md`, and `docs/plans/2026-10-29/01-web-read-performance.md` as described above. No blockers.

## Handoff Notes

- **Resume at:** Open a fresh Terra session for Phase 1 (Tasks 1 and 3) of `docs/plans/2026-11-12/05-holdout-replay-readiness.md`, or complete the Preview capture check for `docs/plans/2026-11-12/01-near-kickoff-line-capture.md` ahead of Saturday 2026-11-21.
- **Watch out for:** Do not modify `scripts/ops/weekly_automation.py`, `scripts/pipeline/refresh_score_exceptions.py`, or `scripts/pipeline/build_season_revision.py` during Weeks 13–15.

## Terra Handoff Prompt

```text
Use the repository-local implement-plan skill and implement Phase 1 (Tasks 1 and 3 only: read-only git-pin recovery check and standalone read-only holdout export script) of the approved contract at:

docs/plans/2026-11-12/05-holdout-replay-readiness.md

Treat it as authoritative. Do not edit scripts/ops/weekly_automation.py, scripts/pipeline/refresh_score_exceptions.py, or scripts/pipeline/build_season_revision.py (Task 2 is deferred until after 2026-12-13). Preserve its architectural decisions, run its validation, and stop for any material conflict. This request explicitly authorizes Phase 1 implementation.
```
