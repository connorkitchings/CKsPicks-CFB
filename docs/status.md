# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-25. The four-tab Crest CFB site (Games, Ratings, Graphs, Model) is published to Production with the `dev` to `main` release of 2026-10-25, a web deploy only. Production and Preview still serve the Week 8 line-refresh release: `production-season-2026-125158328e025fb89c96ce0d` / `preview-season-2026-125158328e025fb89c96ce0d`. All 56 Week 8 games have spread and total forecasts and lines, refreshed 2026-10-20 (as of 14:39Z). Week 8 scores have not been ingested as of 2026-10-25, so the site shows Week 8 as awaiting results. Week 7 is scored; cumulative spread 190-188-7 (50.3%), total 192-191-1 (50.1%). Evidence: `session_logs/2026-10-25/01-final-site-review.md`, `session_logs/2026-10-20/02-week8-line-refresh.md`, `session_logs/2026-10-19/04-sos-sor-production-release.md`.

> **2026-10-25 publication:** the four-tab Crest CFB site is on Production, published with the `dev` to `main` release of 2026-10-25: Games (`/`, with `/matchup/[gameId]` detail pages), Ratings (`/ratings`, with team pages at `/teams/[team]`), Graphs (`/stats`) and Model (`/model`, with `/model/method`). Graphs is published with no feature flag; the `CFB_CHARTS_ENABLED` gate was removed from the code. The URL stays `https://c-ks-picks-cfb.vercel.app` (the code previously named `ckspicks-cfb.vercel.app`, which is not this site; `SITE_URL` in `web/src/lib/brand.ts` now matches the live host); repository, package and Python module names are unchanged. The old `/results`, `/matchup`, `/performance`, `/methodology` and `/charts` URLs redirect with 307. No migrations lie between `main` and `dev`, and the active Production release does not change. New display behavior: a kickoff at exactly midnight Eastern shows "Time TBD" (the data has no time-TBD flag; detection is `isTimeTbd` in `web/src/lib/time-et.ts`), games past kickoff with no ingested score show an "Awaiting result" tag and the week tag reads Awaiting results (`gameState` and `weekStatus` in `web/src/lib/slate.ts`), and the team page Next game card skips games already kicked off. Plan: `docs/plans/2026-10-21/01-site-reorganization-and-performance.md`; review log: `session_logs/2026-10-25/01-final-site-review.md`.
>
> <!-- fill after merge: merge commit and deployment id -->

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
| 0–7 | **Scored; 2026 V5 record.** 388 completed FBS games; 769 graded leans including 8 pushes (761 decided). Week 7 spread 26-32-1; total 32-27-0. | Production `production-season-2026-125158328e025fb89c96ce0d`; Preview `preview-season-2026-125158328e025fb89c96ce0d`. |
| 8 | **Active Picks slate.** All 56 FBS games predicted and lined for both targets; serving as-of 2026-10-20T14:39:00Z. Week 8 scores were not yet ingested as of 2026-10-25; the site shows the week as "Awaiting results" until the Week 9 weekly release. | Same active releases above. Production rollback target: `production-season-2026-2cdf8916d915e21b3f25fa71` (SOS/SOR release, Oct 19 lines); owner-authorized rollback only. Earlier rollback target: `production-season-2026-d0272a48d3a0252fd4196db3`. Preview rollback is not supported by the tooling. |

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

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. The four-tab site, including Graphs, was published to Production with the `dev` to `main` release of 2026-10-25; `dev` continues as the working branch. The repository consolidation is recorded in its [plan](plans/2026-10-22/01-repo-consolidation.md). No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

Production migrations 0026/0027/0028 and Preview migrations 0027/0028 are applied and read back. Charts was unpublished through 2026-10-21 (the `/charts` route returned HTTP 404 and navigation was absent); Graphs (`/stats`) is published with the 2026-10-25 release, which changes no data or migration. Mobile layouts are deployed on Vercel from `main`; the final response-status correction is commit `3d054c94`, deployment `dpl_FmUf3Wsq9cfaqfzL2bHzS4Cu2sNc` (Ready). The prior Week 8 release candidate was prepared and activated from clean commit `91463923`; no commit occurred between prepare and the last activation.

The SOS/SOR release (2026-10-19) was prepared from clean commit `5060aa60` with `run_season.py prepare --revision-manifest conf/season/2026/revision_manifest_w8_v2.json --through-week 7 --next-week 8 --as-of 2026-10-19T14:10:00Z`, passed all 32 checks (including eight `resume_*` checks), and was activated on Preview, then Production. Its `team_resume` table has 1,242 rows (138 teams x 9 periods, including preseason). Serving payload SHA-256: `b04544766245f8c40b48323ca9bab2f9a5a44a73c920df77127c47d428838e20`. Activation readback SHA-256 on both databases: `6b52cdf0a1c464c9873968fc58088eb431afcc82e65f3c47b1ed8eacdbe10429`. Preview's independent read-only check against the prior Week 8 release matched all game, market and system tables, and every value column of predictions, grades and rating snapshots; only release-ID identity columns differ. Live Production checks on 2026-10-19 passed for `/`, `/results`, `/ratings`, `/performance` and `/api/health` (200), and `/charts` (404); those routes are now redirects or published pages as described above.

Week 8 line refresh (2026-10-20): market-only. CFBD betting lines (112 records) and Odds API quotes (404, ~2 credits) were captured for Week 8 only, last capture 14:33:30Z. `scripts/pipeline/build_market_revision.py` (commit `97d5b979`) built `conf/season/2026/revision_manifest_w8_v3.json` (commit `e94cf35a`, `revision_id` `season-2026-w8-preview-r3`, Week 8 cutoff 2026-10-20T14:39:00Z); football inputs and completed-week cutoffs are identical to `w8_v2`. Coverage 56/56 spread and 56/56 total. `run_season.py prepare` ran from a clean worktree pinned to `e94cf35a` and passed all 32 checks; the release is `season-2026-125158328e025fb89c96ce0d`, projection payload SHA-256 `eae0069973b97dc523d9af728ee090c0654e0f49b8492973c10f39c4082c799d`. Preview, then Production, activated with readback SHA-256 `43349ac3cb1e477be4541e23bcdb1179dd11b4c9aa00bb5ad999df67df8bc348` on both. Parity against the prior release: predictions, variances, ratings and completed-week grades identical within 1e-9; only market rows changed. Live Production on 2026-10-20 (before publication): `/`, `/results`, `/ratings`, `/performance`, `/api/health` 200; `/charts` 404; health reports Week 8, 56/56 predicted and lined, data as of 2026-10-20T14:39:00Z.

Ratings résumé columns (commit `5060aa60`, `feat(web): simplify ratings résumé columns`): `/ratings` shows "Post-Week 0..7" period labels, FBS W-L, SOR rank, and SOS Played/Remaining/Full. SOR is shown as rank only; WAA and overall uncertainty are not displayed; SOS uses one measure (average FBS team). Elite SOS is stored but not shown. Source contract: `docs/plans/2026-10-19/02-sos-sor-release-projection.md`.

The prior Week 8 `charts_v2` candidate passed all 24 checks. Projection payload SHA-256: `e8b8ef589c33e94abf51d53a8b3c8daf07174dcc6e52d5525ef448922f05a359`. Preview and Production activation readback SHA-256 match: `d8d02ae36baf6eef4b2e770cb5fc71bb43b92a2036aad096808efe90d1e1527f`. Independent read-only verification matched all 22 projection-table counts and the cumulative record. The 888 forecast means/variances, 1,242 rating rows and 776 completed-week grading rows match the prior certified Week 8 snapshot within 1e-9. Only upcoming-market lines/leans changed.

The final release retains all certified football input hashes and historical cutoffs. An unnecessarily started historical CFBD refresh was cancelled during Week 3 and its partial football inputs were not selected. Promotion must never query providers; the [weekly process review](planning/weekly-operations-process-review.md) records the separate defect in the current full-history weekly builder. See the [weekly runbook](ops/weekly_runbook.md) for the new explicit boundary. Historical rehearsal and repair details remain in their session logs and [status history](status_history.md).

## Next weekly update

The Week 8 line refresh is complete (captured 2026-10-20 before the 18:00Z deadline and the 23:00Z first kickoff). Any further mid-week refresh uses the same market-only builder and needs an authorized, scoped capture. This is not a scheduled automation.

Before the next normal week close/open, review and approve an incremental source-ingestion process. Do not repeat the current full-history builder for routine rollover. Use retained certified history and scope any source fetches to new-week observations or an explicitly approved repair. Candidate preparation still requires pinned inputs, a clean commit, exact reconciliation, all verification checks, independent Preview rehearsal and Production readback.

## Deferred backlog

These obligations survive superseding the overlapping repair/cutover contracts. They are outside recurring weekly release prerequisites and need a separately reviewed execution scope; this documentation cleanup does not certify or close them.

- **Historical EPA replacement:** retain the exact-key evidence for 95 stale adjusted rows and the 951 shared EPA rows with differences reported in the original comparison. Define certified replacement and stale-key cleanup with before-state checks, backups, atomic apply, readback and rollback proof. [Investigation and retained evidence](plans/2026-10-10/04-investigate-database-only-adjusted-rows.md).
- **Six quality follow-ups:** independent expected-request inventory/enforcement; ambiguous dataset/version review; Gold checks and Silver builder receipts; reviewed blocking-policy enforcement; durable release-adjacent receipts/readback; legacy validation disposition. The [historical completion matrix](plans/2026-10-08/02-repair-track-certification-and-closure.md#completion-matrix) retains the detailed evidence and unfinished acceptance requirements.
- **Scoring and descendant recertification:** unresolved scoring defects and affected downstream measurements remain data work. Phase 1 exact score reconciliation with declared exceptions is a guard, not evidence that those source defects are repaired.
- **2025 matchup backfill:** complete independent certification, then reviewed publication/readback. Retained [matchup-layer requirements](plans/2026-10-02/01-matchup-data-layer-v2.md) remain evidence; no backfill was performed here.
- **Non-monotonic play-by-play score:** preserve the documented nullable points-per-scoring-opportunity limitation and repair scope in [known data issues](data/known_issues.md).

Dated release, waiver, deployment and repair narratives moved to [status history](status_history.md). Research remains separate from live operations. Repository cleanup (V4, Hydra, Nx and one-off tooling removed; plans and September logs archived) is complete and merged: [plan](plans/2026-10-22/01-repo-consolidation.md).

## Where to look next

- [Weekly runbook](ops/weekly_runbook.md) · [V5 status](modeling/v5_status.md) · [Record methodology](modeling/record_methodology.md) · [V4 retrospective](modeling/v4_retrospective.md) · [Implementation contracts](plans/index.md)
