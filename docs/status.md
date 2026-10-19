# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-19. Production and Preview serve the verified Week 8 candidate: `production-season-2026-b7bc98eb26fa667f6c0941d6` / `preview-season-2026-b7bc98eb26fa667f6c0941d6`. All 56 Week 8 games have spread and total forecasts and lines. Week 7 is scored; cumulative spread 190-188-7 (50.3%), total 192-191-1 (50.1%). Mobile changes are deployed and Charts remains hidden. Evidence: `session_logs/2026-10-19/01-production-release-preflight.md`.

## Product and model

- **Product:** public Vercel site showing every FBS game's spread and total lean
  vs the market. Display-only; staking and wagering are deferred
  ([betting policy](modeling/betting_policy.md)).
- **Serving model family:** V5 possession ratings + Ridge bridge, repaired
  "intended-update" release (2026-09-30). Model development is complete and
  accepted ([V5 status](modeling/v5_status.md)).
- **Rollback:** Atomic rollback via `run_season.py rollback` using Migration 0025 projections.

## Week state (2026 season)

| Week | State | Selected run |
|---|---|---|
| 0–7 | **Scored; 2026 V5 record.** 388 completed FBS games; 769 graded leans including 8 pushes (761 decided). Week 7 spread 26-32-1; total 32-27-0. | Production `production-season-2026-b7bc98eb26fa667f6c0941d6`; Preview `preview-season-2026-b7bc98eb26fa667f6c0941d6`. |
| 8 | **Active Picks slate.** All 56 FBS games predicted and lined for both targets; serving as-of 2026-10-19T14:10:00Z. | Same active releases above. Prior Production rollback target: `production-season-2026-d0272a48d3a0252fd4196db3`; owner-authorized rollback only. |

## Scoreboard

**Primary success metric (decided 2026-10-10):** cumulative 2026 V5 ATS win % from Week 0
onward vs the 52.4% break-even at -110, reported separately for spreads and totals, with
strictly point-in-time inputs ([record methodology](modeling/record_methodology.md)). MAE,
calibration and the pre-registered promotion gates remain diagnostics.

| Record | Spread | Total | Notes |
|---|---|---|---|
| **2026 V5, cumulative (Weeks 0–7)** | 190-188-7 (50.3%) | 192-191-1 (50.1%) | All 388 completed FBS games across Weeks 0–7: 385 graded spreads (190-188-7), 384 graded totals (192-191-1). Week 7 alone: spread 26-32-1 (44.8%), total 32-27-0 (54.2%). Served atomically on Production and Preview. |

Neither target clears 52.4% YTD. In the 2025 holdout the market had
lower error than V5 on both targets, and the docs do not claim V5 beats V4.

## Branches

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

Production migrations 0026/0027 and Preview migration 0027 are applied and read back. Charts publication remains disabled; the live route returns HTTP 404 and Charts navigation is absent. Mobile layouts are deployed on Vercel from `main`; the final response-status correction is commit `3d054c94`, deployment `dpl_FmUf3Wsq9cfaqfzL2bHzS4Cu2sNc` (Ready). The release data candidate was prepared and activated from clean commit `91463923`; no commit occurred between prepare and the last activation.

The prepared `charts_v2` candidate passed all 24 checks. Projection payload SHA-256: `e8b8ef589c33e94abf51d53a8b3c8daf07174dcc6e52d5525ef448922f05a359`. Preview and Production activation readback SHA-256 match: `d8d02ae36baf6eef4b2e770cb5fc71bb43b92a2036aad096808efe90d1e1527f`. Independent read-only verification matched all 22 projection-table counts and the cumulative record. The 888 forecast means/variances, 1,242 rating rows and 776 completed-week grading rows match the prior certified Week 8 snapshot within 1e-9. Only upcoming-market lines/leans changed.

The final release retains all certified football input hashes and historical cutoffs. An unnecessarily started historical CFBD refresh was cancelled during Week 3 and its partial football inputs were not selected. Promotion must never query providers; the [weekly process review](planning/weekly-operations-process-review.md) records the separate defect in the current full-history weekly builder. See the [weekly runbook](ops/weekly_runbook.md) for the new explicit boundary. Historical rehearsal and repair details remain in their session logs and [status history](status_history.md).

## Next weekly update

No provider refresh is required for this completed promotion. The next authorized Week 8 market refresh should occur before 2026-10-20T18:00:00Z, ahead of the first kickoff at 23:00 UTC. October 19 captures at 14:09:11 UTC (CFBD) and 14:09:12 UTC (Odds API) covered all 56 games for spreads and totals; missing IDs: none for either target. This is a recorded follow-up, not a scheduled automation.

Before the next normal week close/open, review and approve an incremental source-ingestion process. Do not repeat the current full-history builder for routine rollover. Use retained certified history and scope any source fetches to new-week observations or an explicitly approved repair. Candidate preparation still requires pinned inputs, a clean commit, exact reconciliation, all verification checks, independent Preview rehearsal and Production readback.

## Deferred backlog

These obligations survive superseding the overlapping repair/cutover contracts. They are outside recurring weekly release prerequisites and need a separately reviewed execution scope; this documentation cleanup does not certify or close them.

- **Historical EPA replacement:** retain the exact-key evidence for 95 stale adjusted rows and the 951 shared EPA rows with differences reported in the original comparison. Define certified replacement and stale-key cleanup with before-state checks, backups, atomic apply, readback and rollback proof. [Investigation and retained evidence](plans/2026-10-10/04-investigate-database-only-adjusted-rows.md).
- **Six quality follow-ups:** independent expected-request inventory/enforcement; ambiguous dataset/version review; Gold checks and Silver builder receipts; reviewed blocking-policy enforcement; durable release-adjacent receipts/readback; legacy validation disposition. The [historical completion matrix](plans/2026-10-08/02-repair-track-certification-and-closure.md#completion-matrix) retains the detailed evidence and unfinished acceptance requirements.
- **Scoring and descendant recertification:** unresolved scoring defects and affected downstream measurements remain data work. Phase 1 exact score reconciliation with declared exceptions is a guard, not evidence that those source defects are repaired.
- **2025 matchup backfill:** complete independent certification, then reviewed publication/readback. Retained [matchup-layer requirements](plans/2026-10-02/01-matchup-data-layer-v2.md) remain evidence; no backfill was performed here.
- **Non-monotonic play-by-play score:** preserve the documented nullable points-per-scoring-opportunity limitation and repair scope in [known data issues](data/known_issues.md).

Dated release, waiver, deployment and repair narratives moved to [status history](status_history.md). Research and repository cleanup remain separate from live operations.

## Where to look next

- [Weekly runbook](ops/weekly_runbook.md) · [V5 status](modeling/v5_status.md) · [Record methodology](modeling/record_methodology.md) · [V4 retrospective](modeling/v4_retrospective.md) · [Implementation contracts](plans/index.md)
