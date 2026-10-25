# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-25. Production serves the Week 8 line-refresh release `production-season-2026-125158328e025fb89c96ce0d`. Preview has advanced to the Week 9 incremental rollover release `preview-season-2026-7a59b8a92d0f7a85ca0a377b` (Week 8 scored, Week 9 picks, as of 2026-10-25T16:00:00Z); Production is unchanged. All 56 Week 9 games predicted (30 with spread and total lines today; partial coverage to be topped up by the mid-week market refresh before Tuesday's kickoff). Week 8 is now scored; cumulative spread 190-188-7 (50.3%), total 192-191-1 (50.1%) through Week 7 (Week 8 results to be folded into the cumulative record at the Week 9 close). Charts remains hidden. Evidence: `session_logs/2026-10-25/02-incremental-close-week-rollover.md`.

> **2026-10-21 site reorganization (on `dev`, not on Production):** the site is reorganized into four tabs: Games (`/`, Picks and Results merged into one week view with a phase chip; `/matchup/[gameId]` detail pages unchanged), Ratings (`/ratings`, with team pages at `/teams/[team]`), Stats (`/stats`, formerly `/charts`) and Model (`/model`, formerly `/performance`, and `/model/method`, formerly `/methodology`). Old URLs redirect with 307 for now. Phases 1-4 code is on `dev` (pushed; head `d1c3ed04`, including follow-up review fixes). Production still serves the older route set until Monday's merge. Plan: `docs/plans/2026-10-21/01-site-reorganization-and-performance.md`; log: `session_logs/2026-10-21/01-site-reorganization-and-performance.md`.

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
| 0–7 | **Scored; 2026 V5 record.** 388 completed FBS games; 769 graded leans including 8 pushes (761 decided). Week 7 spread 26-32-1; total 32-27-0. | Production `production-season-2026-125158328e025fb89c96ce0d` (unchanged). |
| 8 | **Scored.** All 56 FBS games complete; closed into the Week 9 revision on 2026-10-25. Week 8 results to be folded into the cumulative record at the Week 9 close. | Production `production-season-2026-125158328e025fb89c96ce0d`; Preview `preview-season-2026-7a59b8a92d0f7a85ca0a377b`. |
| 9 | **Active Picks slate (Preview).** All 56 FBS games predicted; 30 with spread and total lines as of 2026-10-25T16:00:00Z (partial; mid-week market refresh recommended before Tuesday's 23:00Z kickoff). | Preview `preview-season-2026-7a59b8a92d0f7a85ca0a377b`. Production unchanged (`production-season-2026-125158328e025fb89c96ce0d`). |

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

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. Current focus of `dev` (owner, 2026-10-22): review of the repository consolidation (branch `connorkitchings/repo-consolidation`, [plan](plans/2026-10-22/01-repo-consolidation.md)), then testing and preparing the Stats tab (formerly Charts) for publication; see [Charts pre-publication verification](plans/2026-10-20/03-charts-pre-publication.md). Charts stays unpublished until the owner decides. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

Production migrations 0026/0027/0028 and Preview migrations 0027/0028 are applied and read back. Charts publication remains disabled; the live route returns HTTP 404 and Charts navigation is absent. Mobile layouts are deployed on Vercel from `main`; the final response-status correction is commit `3d054c94`, deployment `dpl_FmUf3Wsq9cfaqfzL2bHzS4Cu2sNc` (Ready). The prior Week 8 release candidate was prepared and activated from clean commit `91463923`; no commit occurred between prepare and the last activation.

The SOS/SOR release (2026-10-19) was prepared from clean commit `5060aa60` with `run_season.py prepare --revision-manifest conf/season/2026/revision_manifest_w8_v2.json --through-week 7 --next-week 8 --as-of 2026-10-19T14:10:00Z`, passed all 32 checks (including eight `resume_*` checks), and was activated on Preview, then Production. Its `team_resume` table has 1,242 rows (138 teams x 9 periods, including preseason). Serving payload SHA-256: `b04544766245f8c40b48323ca9bab2f9a5a44a73c920df77127c47d428838e20`. Activation readback SHA-256 on both databases: `6b52cdf0a1c464c9873968fc58088eb431afcc82e65f3c47b1ed8eacdbe10429`. Preview's independent read-only check against the prior Week 8 release matched all game, market and system tables, and every value column of predictions, grades and rating snapshots; only release-ID identity columns differ. Live Production checks passed for `/`, `/results`, `/ratings`, `/performance` and `/api/health` (200), and `/charts` (404).

Week 9 incremental rollover (2026-10-25): the first run of the new `make season-close-week` path (RUN_ID `w9-incremental-202610251459`, commit `81565333`). Only Week 8 observations were fetched; the certified Weeks 0–7 Bronze captures (8 each) were carried into the new `plays`/`team_game_stats` Silver versions; the stop gate confirmed completed weeks 0–7 match the certified Week 8 revision (provenance and CFBD-recomputed postgame Elo excluded, documented); weeks 0–7 cutoff history is byte-identical to `revision_manifest_w8_v3.json`. Two Week 8 score-reconciliation exceptions were declared (Ole Miss 3 vs 27, Eastern Michigan 0 vs 20). `run_season.py prepare` passed all 24 `charts_v2` checks from clean commit `81565333` with `--as-of 2026-10-25T16:00:00Z`; candidate release `season-2026-7a59b8a92d0f7a85ca0a377b`, serving-projections SHA-256 `ebd6531221636113227ae9198805bc27eabb6bd6e039c7ee21e40eb9d64d5bf2`. Parity against the prior release: predictions, variances, ratings and completed-week grades identical within 1e-9 (only `source_ref`/`run_id` identity columns differ). Activated on Preview with readback SHA-256 `de7659e0b6d0f8f211b968281ea2461b7afa158a7a2a0b76efd419739bb5db42`; Preview health reports Week 9, 56/56 predicted, 30 lined, data as of 2026-10-25T16:00:00Z. Production is unchanged (`production-season-2026-125158328e025fb89c96ce0d`); Production activation and the `dev`→`main` merge remain separate owner decisions. Evidence: `session_logs/2026-10-25/02-incremental-close-week-rollover.md`.

## Next weekly update

The incremental close/open path is now implemented and certified on this rollover: `make season-close-week` (builder `--incremental`, controller `advance-week`) fetches only the completed week's observations, carries certified earlier-week captures, and gates completed-week history against the previous manifest. `make season-revision` refuses without `FULL_HISTORY=1` and is reserved for approved history repairs. The mid-week market refresh (`make season-market-revision`) is the recommended next step to top up Week 9 line coverage (30/56) before Tuesday's 23:00Z kickoff, owner-triggered at ~2 Odds API credits. Production activation of the Week 9 release and the `dev`→`main` merge remain separate owner decisions. Charts stays unpublished until the owner decides.

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

Dated release, waiver, deployment and repair narratives moved to [status history](status_history.md). Research remains separate from live operations. Repository cleanup (V4, Hydra, Nx and one-off tooling removed; plans and September logs archived) is complete on the consolidation branch pending owner review: [plan](plans/2026-10-22/01-repo-consolidation.md).

## Where to look next

- [Weekly runbook](ops/weekly_runbook.md) · [V5 status](modeling/v5_status.md) · [Record methodology](modeling/record_methodology.md) · [V4 retrospective](modeling/v4_retrospective.md) · [Implementation contracts](plans/index.md)
