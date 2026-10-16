# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-16 (Preview-only chart release activated after all 23 verification checks and numerical parity against the prior release; chart data and live views verified for Weeks 0–6. Local chart organization and PNG focus-outline repairs validated in the worktree, awaiting owner commit/integration. Production remains unchanged and was not accessed.) · **Verified from:**
> `session_logs/2026-10-16/03-preview-chart-rehearsal.md`,
> `session_logs/2026-10-16/04-chart-navigation-and-export-polish.md`,
> `session_logs/2026-10-14/08-stage4-production-migration-and-cutover.md`,
> `session_logs/2026-10-14/07-web-ui-cleanup-and-early-games-reconstruction.md` (see its October 15 correction),
> `session_logs/2026-10-14/06-stages-1-to-3-preview-cutover.md`,
> `docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md`.

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
| 0–6 | **Scored; reconstructed 2026 V5 record** (all 329 FBS games including mid-week games; 657 graded bets: spread 166-157-6, total 163-164-1). Preview additionally serves Migration 0026 chart projections; Production retains its existing release. | Active in release `production-season-2026-d0272a48d3a0252fd4196db3` (Preview: `preview-season-2026-99c518e3bb66e7cc2adcc169`) |
| 7 | **Active Picks slate.** Complete 59-game FBS schedule. Preview reconstructed at the existing pinned pre-week cutoff; forecasts, ratings and grades match the prior release. | Active in release `production-season-2026-d0272a48d3a0252fd4196db3` (Preview: `preview-season-2026-99c518e3bb66e7cc2adcc169`). Production rollback: `run_season.py rollback` (owner login). |

## Scoreboard

**Primary success metric (decided 2026-10-10):** cumulative 2026 V5 ATS win % from Week 0
onward vs the 52.4% break-even at -110, reported separately for spreads and totals, with
strictly point-in-time inputs ([record methodology](modeling/record_methodology.md)). MAE,
calibration and the pre-registered promotion gates remain diagnostics.

| Record | Spread | Total | Notes |
|---|---|---|---|
| **2026 V5, cumulative (Weeks 0–6 full reconstruction)** | 166-157-6 (51.4%) | 163-164-1 (49.8%) | All 329 FBS games across Weeks 0–6: 329 decided spreads (166-157-6), 328 decided totals (163-164-1; 1 unlined total). Served atomically via Migration 0025 release projections |

Neither target clears 52.4% YTD. In the 2025 holdout the market had
lower error than V5 on both targets, and the docs do not claim V5 beats V4.

## Branches

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

**Local UI follow-up (2026-10-16):** the initial PNG focus-outline defect described below is corrected in the working tree. Chart selectors/week navigation and team filters/display actions are grouped responsively. All 67 browser tests pass; a 138-team real-data efficiency export was saved and visually inspected without focus rings. The worktree UI is served on port 3200 against Preview; the primary `dev` checkout still lacks the feature until owner integration. These changes are uncommitted and do not alter the active release or Production. Real-data browser export latency remains a follow-up observation, not a completed performance fix.

**Preview charts (2026-10-16):** prepared and released from clean commit `749ee12c`. Payload SHA-256 `5442a64c89fccd5df54228bc95f5b3e0a66054468fe05c7d4d72b068d3bdbd9b`; activation readback SHA-256 `77dfcc05eaff3e54beeb7593ae62d025084968b8f2722d287d0eddaa934bfcc7`. All 21 `charts_v1` projection tables verified, with 138 roster teams, 658 team-game rows for Weeks 0–6 and 1,378 adjusted rows for Through Weeks 2–6. Existing numerical serving data matches the prior release within `1e-9`, after explicit identity/provenance exclusions and timestamp normalization. Live charts, filters, search, tables, keyboard tooltips and core pages work. Both inspected PNG exports show unwanted blue keyboard-focus outlines, so chart export acceptance and task 8 remain incomplete. Production migration, deployment and activation are not authorized by this rehearsal. Rehearsal evidence is in `session_logs/2026-10-16/03-preview-chart-rehearsal.md`; see the [chart contract](plans/2026-10-16/01-charts-module.md).

The atomic season release in the week table is the serving authority across Picks, Results, Ratings, Performance and matchup views. Migration 0025 cutover was recorded on October 14 in `session_logs/2026-10-14/08-stage4-production-migration-and-cutover.md`; this documentation session performed no new database or deployment readback. V5 Blitzkrieg is the only operational model. Rollback reactivates a retained atomic season release; V4 is historical methodology, not an operational rollback path.

Phase 1 review fixes are committed as `2807e087`: the weekly revision builder, exact reconciliation with manifest-pinned exceptions, release-ID normalization, owner rollback wrapper and active-release health reporting are delivered. Phase 2 documentation consolidation is complete locally and awaiting the owner commit under the [review contract](plans/2026-10-15/01-review-fixes-and-v5-streamline.md); Phase 3 cleanup is deferred.

**Accepted quote rebuild, pending activation:** the owner confirmed registration of the three Week 2–4 CFBD captures in Preview and accepted rebuilt-quote results: spread 164-156-6, total 160-164-1. Week 6 games 401871090, 401871051 and 401871066 become ungraded for both targets because their retained quotes were captured after kickoff. These are candidate results; the active release and published scoreboard above are unchanged. Other unregistered market files still require owner review. Provenance and the retained Week 7 parity evidence are in the review contract and `session_logs/2026-10-15/02-review-fixes-implementation.md`.

## Next weekly update

Week 7 finals/grading remain pending in the recorded serving state. After the complete Week 7 finals and required controller inputs exist, use the [weekly runbook](ops/weekly_runbook.md) to build the Week 8 revision, prepare, rehearse Preview and verify readback. Refresh the score-reconciliation exceptions first. The stale untracked Week 8 manifest still carries Week 7 hashes: remove it before regeneration; the builder refuses to overwrite it. Neither that file nor the unrelated October 14 session log 13 is part of the review-fixes commits.

The Week 8 revision dry run is blocked on those Week 7 inputs and has not passed. The owner must create the Production owner Keychain item before owner rollback; Preview rollback is unsupported. Prepare requires a clean tree and no commit may land between prepare and release.

The [season operations and Week 7 bridge contract](plans/2026-10-14/01-season-operations-and-week7-bridge.md) stays **In Progress**: cutover is complete, but acceptance still requires a subsequent weekly update through the same controller. Documentation delivery does not establish that operational proof. Production activation remains an owner decision under the installed release policy.

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
