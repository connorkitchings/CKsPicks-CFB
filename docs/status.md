# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-14 (Migration 0025 applied and atomic season release `production-season-2026-d0272a48d3a0252fd4196db3` activated in Production; Preview release `preview-season-2026-d0272a48d3a0252fd4196db3`; full historical reconstruction Weeks 0–6 with complete mid-week coverage for Weeks 6 and 7) · **Verified from:**
> `session_logs/2026-10-14/07-web-ui-cleanup-and-early-games-reconstruction.md`,
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
| 0–6 | **Scored; reconstructed 2026 V5 record** (all 329 FBS games including mid-week games; 657 graded bets: spread 166-157-6, total 163-164-1). Served via Migration 0025 atomic release projections. | Active in release `production-season-2026-d0272a48d3a0252fd4196db3` (Preview: `preview-season-2026-d0272a48d3a0252fd4196db3`) |
| 7 | **Active Picks slate (2026-10-14).** Complete 59-game FBS schedule including mid-week games (Delaware @ MTSU, FIU @ Jax State, etc.). Clean display without disclaimer banner or retrospective badge on active slate. Served via Migration 0025 atomic release projections. | Active in release `production-season-2026-d0272a48d3a0252fd4196db3` (Preview: `preview-season-2026-d0272a48d3a0252fd4196db3`). Rollback: `run_season.py rollback` (owner login). |

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

**Note (2026-10-11):** `dev` is 11 commits ahead of `origin/dev` and of `main` (cutover tooling, unified Performance page, grades-policy fixes, extender); none is deployed. Historical: `main` was fast-forwarded to `dev` at the 2026-10-02 close-out (previous release `53d346b`). That release carries the Picks/Results prototype port (city/state and sportsbook-behind-the-line on the production slate cards; rank badges stay off the cards by design; the `/test-picks` and `/test-results` routes are removed), the unconstrained-grading pipeline changes, the team-stats punt fix (code), and the matchup refinements including the Share card. Matchup pages are default-on; `CFB_MATCHUP_ENABLED=0` is the emergency opt-out. Their remaining data-integrity work is governed by the [repair-track contract](plans/2026-10-08/02-repair-track-certification-and-closure.md). CI's browser suite now runs with `CFB_PUBLICATION_MODE=predictions` set by `web/playwright.config.ts` (see `web/README.md`). **Picks/Results card redesign (complete, released 2026-10-02):** the bet-cell cards ("Best bets" panel, team filter, grid/list toggle) replace the old slate cards. Closing it out fixed two regressions the browser suite caught (Results cards had lost their Matchup button; the Best-bets columns overflowed a 390px phone) and updated the e2e tests to the new controls and card text; the suite is 43/43.

**Track 1 release (2026-10-07, user-run; `main` has since advanced, see the Week 6 release below):** `main` was `0cd0a3c0`; previous release `562319aa` (deployment `dpl_FiycAhixbCrDsZK638CVXtdq9XNM`) is the retained rollback target. The release carries the Stage 7A/7B read paths, the Performance page split into a replay section and a separate, explicitly designated prospective section (Week 5 only, labeled retrospectively attested), independent loading of those two sections, and the pinned venue publisher. No database or serving state changed in the release; Production venues were not rewritten. Live Production routes (`/api/health`, Picks hold screen, Results, Performance, Ratings, `/matchup/401856819`) return 200 with the audited Week 5 numbers. **Known visible limits:** the Preview database role is an unverified report; the Production team stats were republished afterwards (below). Production matchup pages previously used the pre-fix team stats. Docs-only commits on `dev` after `0cd0a3c0` are not part of the release.

**Production team stats republished (2026-10-07 17:05:40Z, user-run):** `team_season_stats` for as-of weeks 1-5 was rebuilt with the punt-return fix from the same pinned Silver inputs as before (games `31a337df…`, byplay `443019a9…`, drives `862815e2…`, teams `590e9865…`, game_outcomes `d9a37cf4…`). Production now holds 11,506 rows and equals Preview on every column except `updated_at`: +1,046 `ppa_per_play` rows and corrected `conv_rate_3rd_4th`, `explosive_rate` and `turnover_rate` (2,291 value changes, 479 rank-only, 153 play-count-only; explosive-rate ranks moved by up to 52 places). Independent CFBD comparison passes at as-of weeks 4 and 5; no other serving state changed. The pre-apply table is retained as the rollback source (`before-production.json.gz`). The as-of-6 snapshot was published on 2026-10-09 after the post-Week-5 Silver promotion (see the Week 6 row and the [release contract](plans/2026-10-09/02-week6-display-production-release.md)); as-of 7 is the next step. Evidence: [team-stats-republish](plans/2026-10-07/team-stats-republish/summary.md).

## Week 6 release (2026-10-09, user-run applies)

The display-only Week 6 run was published and selected in Production on 2026-10-09 ([contract `02`](plans/2026-10-09/02-week6-display-production-release.md), Amendment 7). `main` and `dev` carry the same contents (`656cf320`; `main`'s tip is the merge commit `b26ecca4`) and CI on `main` passed. Basic live-site checks were confirmed by the user, but contract `02` Task 6 (deployed revision, visual check, notice setting, post-grade readback) is not closed. **Still open:** `CFB_DISPLAY_ONLY_NOTICE=0` in Vercel, the post-finals grades-only backfill, and contract `02` Tasks 6-7. Week 6 is never frozen or closed.

## Open work

- **Week 7 display-only release (2026-10-14):** published and selected in Production and Preview; evidence in `session_logs/2026-10-14/02-season-operations-implementation.md` and the [bridge contract](plans/2026-10-14/01-season-operations-and-week7-bridge.md). Open: the 4 spread-only games (the totals were absent from the market snapshot though CFBD listed them), stale kickoff times for 401858492 and 401858494 in the source lock, grading after finals, and the corrected Weeks 0-6 replay cutover.

- **Week 6 closeout and Week 7 hold (2026-10-11, read-only execution preflight):** [Closeout contract](plans/2026-10-11/01-week6-closeout-and-transition-review.md) is In Progress; [retained evidence and transition review](plans/2026-10-11/week7-transition-review.md) confirm all 58 Week 6 games final at 14:08:13Z, but both databases still have zero loaded Week 6 finals/grades. Actual Week 5 loader parity passes in both environments (56 unchanged, zero inserts/conflicts). No verified 24-hour stability receipt was established in this preflight; absent earlier retained evidence, recheck after October 12 14:08:13Z (10:08 AM New York). Three provider kickoff changes require disposition; the [bounded extender repair](plans/2026-10-11/01-bounded-source-lock-extender-repair.md) now passes fixture-only append and successor-helper tests (271 + 58 = 329). No operational lock was generated; downstream successor CLI week coverage still needs disposition. **Superseded 2026-10-11 (later):** the user lifted the Week 7 hold, waived the Sunday checkpoint and integrity-first rule for the Week 7 cutover only, and removed the 24-hour finals-stability rule ([contract 02](plans/2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md), repair Amendment 14). The "recheck after October 12 14:08:13Z" gate above is now monitoring only. **Executed 2026-10-11 ~16:00Z:** Week 6 finals (58) and grades (110) are loaded in Preview and Production after pre-write exports, with independent readback; the scoreboard below now includes Week 6. No selection changed.

- **Unified-record audit (2026-10-10, read-only):** the corrected Weeks 0–5 candidates pass all seven point-in-time rules for 271 games. Including the existing display Week 6 run fails the forecast/state cutoff and 58-game coverage gates; no future outcome was found in its rating histories. The CFBD re-fetch comparison matched 19/59 stored pre-kickoff provider/target lines, so the three early-game late-quote exceptions remain disabled. Audit tooling and the unified Performance UI are implemented locally; a complete passing Week 6 replay receipt is still required for cutover. See [record methodology](modeling/record_methodology.md#audit-execution-and-october-10-findings). No serving selection changed.

- **Data repair (the one open data contract):** [repair-track certification and closure](plans/2026-10-08/02-repair-track-certification-and-closure.md) (In Progress; its completion matrix is the authority). The 2026-10-08 c2/B2 readback, baseline CI and deployed-revision checks do not establish corrected Production activation or closure. Current sub-track: play identity complete and verified ([byplay_v2 contract](plans/2026-10-09/01-byplay-v2-play-identity.md); provider-keyed identity, invariance proven across 148.5M cells). Remaining repair milestones: the six quality follow-ups, scoring defects, the 95 database-only adjusted rows, the 2025 matchup backfill and Week 6 certification (needs stable finals).
- **Release timing (revised 2026-10-11):** the Sunday-checkpoint outcome was *not met* (the successor CLI had fixed Weeks 0-5 mappings; now fixed locally). The user waived the checkpoint and the integrity-closure-first rule for the Week 7 cutover only and removed the 24-hour finals rule, so the cutover is attempted for Week 7 with the Tuesday 14:00Z pivot gate (rehearsal incl. owner-login rollback proof not verified by then bars cutover; fallback: frozen standalone Week 7, which needs its own contract) and the 22:00Z freeze deadline. Items still open after the waiver: EPA replacement (95 stale keys + 951 differing rows), the six quality follow-ups, scoring/descendant recertification, and the 2025 matchup candidate. Production activation of corrected replays remains a separate exact approval. Earlier text on this point (03:00Z estimate, Sunday checkpoint) is historical. [Run sheet](plans/2026-10-10/01-week7-cutover-run-sheet.md).
- **Week 5:** closed and scored 2026-10-04 (56 spread + 56 total grades, 112 total). **Week 6:** see the week table.
- **Matchup pages and team stats:** released and default-on (`CFB_MATCHUP_ENABLED=0` is the emergency opt-out). Preview and Production `team_season_stats` both hold 11,506 rows for as-of weeks 1-5 after the 2026-10-07 republish, plus the 3,036-row as-of-6 snapshot published 2026-10-09. Corrected repinning and the 2025 backfill belong to the repair contract; limitations stay in [known issues](data/known_issues.md).
- Open data issue: the play-by-play running score is non-monotonic for about a third of team-games, which blanks some points-per-scoring-opportunity values; documented in [known data issues](data/known_issues.md). Step 5 admitted corroborated historical changes only; residual baseline errors remain, and the corrected durable rebuild is pending.
- **Historical, superseded 2026-10-09: pre-Week-6 audit (2026-10-07, read-only, restricted roles; the active-run, selection-count and team-stats-row facts below were true then and no longer are; [evidence](plans/2026-10-07/pre-week6-audit-evidence/checksums.txt)):** Preview and Production agree on serving state (`current_week` (2026, 6) with no active run, six selections, all rollback runs present), Week 5 grades (56 predictions, 112 grades, spread 28-27-1, total 25-30-1; identical row hashes), schema (23 migrations through 0024, same ledger), venues (271/271 with city) and the Week 5 `prospective_week_records` row (legacy attestation hashes: Preview `9b3d04f3…`, Production `9f022418…`). The Production registration's operator and time are not recorded in any session log (open). Known differences: Preview `team_season_stats` has 11,506 rows against Production's 10,460, because Preview carries the 2026-10-02 punt-return fix (extra `ppa_per_play` metric, lower play counts in three rate metrics; Production waits for the Window 1 republish); the Preview copy of the Week 4 rollback run is `published` and ungraded where Production's is `scored`. **Correction (2026-10-09):** the Production team-stats republish at 17:05:40Z the same day (see Release state) closed the 11,506 vs 10,460 row difference; the other differences stand as audited.
- Stage 7B foundations are complete: migrations 0023/0024 are applied in Preview and Production and the Week 5 attestations are registered; cutover execution waits for the certified packet ([Stage 7B plan](plans/2026-10-06/02-stage7b-exact-release-and-cutover.md)).

## Where to look next

- [V5 status](modeling/v5_status.md) · [Weekly operator](ops/v5_weekly_operator.md)
  · [Weekly pipeline](ops/weekly_pipeline.md) · [Production runbook](ops/production_runbook.md)
  · [Implementation contracts](plans/index.md)
