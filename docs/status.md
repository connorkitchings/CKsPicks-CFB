# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-10 (history moved to [`status_history.md`](status_history.md); serving facts as of 2026-10-09: the display-only Week 6 run, corrected post-Week-5 ratings and as-of-6 team stats are applied in Production; Weeks 0-5 selections unchanged) · **Verified from:**
> `session_logs/2026-10-09/08-week6-production-release.md` and [Week 6 release contract](plans/2026-10-09/02-week6-display-production-release.md) Amendment 7,
> `session_logs/2026-10-07/03-pre-week6-audit.md` (read-only audit of Preview and Production),
> `session_logs/2026-09-30/01-verify-deploy-freeze-week5-close-contract.md`,
> the Step 5 close-out and pre-6A planning records (2026-10-04; no new cloud-state verification), and the [repaired-V5 release packet](plans/2026-09-29/v5-intended-update-production-release-packet.md).

## Product and model

- **Product:** public Vercel site showing every FBS game's spread and total lean
  vs the market. Display-only; staking and wagering are deferred
  ([betting policy](modeling/betting_policy.md)).
- **Serving model family:** V5 possession ratings + Ridge bridge, repaired
  "intended-update" release (2026-09-30). Model development is complete and
  accepted ([V5 status](modeling/v5_status.md)).
- **Rollback:** V4 ten-route bundle `week0-2026-v4-strict-20260818-r2`
  (frozen V4 runs) and the prior V5 best-quote replay runs.
- **V6 ratings lab:** closed 2026-09-30, `RETAINED_AS_BENCHMARK`; does not
  affect production.

## Corrected lineage (Preview; Week 6 slice also in Production, 2026-10-09)

The corrected lineage through Week 5 is published in Preview R2/catalog and not served: 6A `6a-rebuild-w5-20261007-r2` (root raw sha `7865d353…`), Task 4 `6a-task4-w5-r2` (receipt `1cd439de…`), and 6B `6b-replay-w5-20261008-r2` (root `c253022a…`; it uses the successor bundle B2, which supersedes `-r1`). On that lineage the successor chain produced the Weeks 0-5 replay set `2026w{0..5}-v5repair-20261008-c2` with provider team names (packaged in the Preview namespace; release records validated by dry run, none registered) and the display-only Week 6 run `2026w6-v5repair-20261008-d2` (selected in Preview and, since 2026-10-09, in Production). Corrected team stats as-of 1-5 and the matchup candidate payloads for Weeks 0-5 exist locally and are verified, not applied; the as-of-6 stats (3,036 rows), corrected ratings snapshots and Week 6 matchup data are applied in Preview and Production. Production still serves the uncorrected Weeks 0-4 replays and the frozen Week 5. **Route (updated 2026-10-09):** Week 6 is released display-only to Production under [contract `02`](plans/2026-10-09/02-week6-display-production-release.md), superseding the earlier hold-until-cutover choice for Week 6 only; the rest of the corrected lineage reaches Production at the cutover (Week 7 at the earliest, Week 8 or later if integrity closure slips; see Open work) using the packet builder and staging tool (Amendments 10 and 11 of the [Stage 1 contract](plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md); [decision brief](plans/2026-10-08/01-stage1-decision-brief.md)).

## Week state (2026 season)

| Week | State | Selected run |
|---|---|---|
| 0–4 | Scored; part of the unified 2026 V5 record (generated retrospectively from point-in-time inputs) | `2026w{0..4}-v5repair-20260929-p1` |
| 5 | **Scored** 2026-10-04, 56/56/56, 112 grades (56 spread, 56 total).  Part of the unified record; frozen before kickoff (immutable receipt). | `2026w5-v5repair-20260929-p2` |
| 6 | **Production: display-only run active (2026-10-09).** The Week 6 run `2026w6-v5repair-20261008-d2` covers the 55 of 58 games that had not started when it was built (Oct 8, 16:53Z; market capture 16:19Z, so Saturday lines may have moved; 3 games kicked off Oct 6-7 are omitted). Evidence class `pending`, never frozen (a post-kickoff freeze would be fabricated; it has no freeze receipt, [Amendments 9-10](plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md), [Amendment 12](plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md)). **Graded into the unified record** (2026-10-10 policy): the grades-only backfill follows the finals. `current_week` is (2026, 6) with the run active; Weeks 0-5 selections are unchanged. Selecting it moved the site-wide rating source to the corrected post-Week-5 manifest `c83b1423…`, so Weeks 0-5 matchup pages show "Forecast and rating snapshots use different published lineages" until the cutover rebinds them (accepted 2026-10-09). Its corrected replay (all 58 games, three on a declared CFBD line) replaces it in the counted record at the cutover; Week 6 joins the corrected replay set after its finals stabilize ([Stage 7B plan](plans/2026-10-06/02-stage7b-exact-release-and-cutover.md)). | `2026w6-v5repair-20261008-d2` in Preview and Production. Rollback: `scripts/pipeline/rollback_week6_display.py` (owner login; rehearsed in Preview 2026-10-09). |

**Rollback set (exact):** `2026w{0..4}-v5replay-bestquote-20260926-r3` and
`2026w5-5d436e58c072`. An earlier Week 5 run, `2026w5-d6366e59fd43`, is
superseded and kept only as an audit record.

## Scoreboard

**Primary success metric (decided 2026-10-10):** cumulative 2026 V5 ATS win % from Week 0
onward vs the 52.4% break-even at -110, reported separately for spreads and totals, with
strictly point-in-time inputs ([record methodology](modeling/record_methodology.md)). MAE,
calibration and the pre-registered promotion gates remain diagnostics.

| Record | Spread | Total | Notes |
|---|---|---|---|
| **2026 V5, cumulative (Weeks 0–5 as served)** | 128-139-4 (47.9%) | 137-132-1 (50.9%) | Sum of the served runs (Weeks 0–4 `p1`, Week 5 `p2`): 267 decided spreads, 269 decided totals; 1 unlined W3 total. Week 6 is added after finals; Weeks 0–6 are replaced by the corrected replays at the cutover |

Neither target clears 52.4% YTD. In the 2025 holdout the market had
lower error than V5 on both targets, and the docs do not claim V5 beats V4.

## Branches

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

`main` was fast-forwarded to `dev` at the 2026-10-02 close-out (previous release `53d346b`). That release carries the Picks/Results prototype port (city/state and sportsbook-behind-the-line on the production slate cards; rank badges stay off the cards by design; the `/test-picks` and `/test-results` routes are removed), the unconstrained-grading pipeline changes, the team-stats punt fix (code), and the matchup refinements including the Share card. Matchup pages are default-on; `CFB_MATCHUP_ENABLED=0` is the emergency opt-out. Their remaining data-integrity work is governed by the [repair-track contract](plans/2026-10-08/02-repair-track-certification-and-closure.md). CI's browser suite now runs with `CFB_PUBLICATION_MODE=predictions` set by `web/playwright.config.ts` (see `web/README.md`). **Picks/Results card redesign (complete, released 2026-10-02):** the bet-cell cards ("Best bets" panel, team filter, grid/list toggle) replace the old slate cards. Closing it out fixed two regressions the browser suite caught (Results cards had lost their Matchup button; the Best-bets columns overflowed a 390px phone) and updated the e2e tests to the new controls and card text; the suite is 43/43.

**Track 1 release (2026-10-07, user-run; `main` has since advanced, see the Week 6 release below):** `main` was `0cd0a3c0`; previous release `562319aa` (deployment `dpl_FiycAhixbCrDsZK638CVXtdq9XNM`) is the retained rollback target. The release carries the Stage 7A/7B read paths, the Performance page split into a replay section and a separate, explicitly designated prospective section (Week 5 only, labeled retrospectively attested), independent loading of those two sections, and the pinned venue publisher. No database or serving state changed in the release; Production venues were not rewritten. Live Production routes (`/api/health`, Picks hold screen, Results, Performance, Ratings, `/matchup/401856819`) return 200 with the audited Week 5 numbers. **Known visible limits:** the Preview database role is an unverified report; the Production team stats were republished afterwards (below). Production matchup pages previously used the pre-fix team stats. Docs-only commits on `dev` after `0cd0a3c0` are not part of the release.

**Production team stats republished (2026-10-07 17:05:40Z, user-run):** `team_season_stats` for as-of weeks 1-5 was rebuilt with the punt-return fix from the same pinned Silver inputs as before (games `31a337df…`, byplay `443019a9…`, drives `862815e2…`, teams `590e9865…`, game_outcomes `d9a37cf4…`). Production now holds 11,506 rows and equals Preview on every column except `updated_at`: +1,046 `ppa_per_play` rows and corrected `conv_rate_3rd_4th`, `explosive_rate` and `turnover_rate` (2,291 value changes, 479 rank-only, 153 play-count-only; explosive-rate ranks moved by up to 52 places). Independent CFBD comparison passes at as-of weeks 4 and 5; no other serving state changed. The pre-apply table is retained as the rollback source (`before-production.json.gz`). The as-of-6 snapshot was published on 2026-10-09 after the post-Week-5 Silver promotion (see the Week 6 row and the [release contract](plans/2026-10-09/02-week6-display-production-release.md)); as-of 7 is the next step. Evidence: [team-stats-republish](plans/2026-10-07/team-stats-republish/summary.md).

## Week 6 release (2026-10-09, user-run applies)

The display-only Week 6 run was published and selected in Production on 2026-10-09 ([contract `02`](plans/2026-10-09/02-week6-display-production-release.md), Amendment 7). `main` and `dev` carry the same contents (`656cf320`; `main`'s tip is the merge commit `b26ecca4`) and CI on `main` passed. Live-site verification is confirmed by the user. **Still open:** `CFB_DISPLAY_ONLY_NOTICE=0` in Vercel, the post-finals grades-only backfill, and contract `02` Tasks 6-7. Week 6 is never frozen or closed.

## Open work

- **Data repair (the one open data contract):** [repair-track certification and closure](plans/2026-10-08/02-repair-track-certification-and-closure.md) (In Progress; its completion matrix is the authority). The 2026-10-08 c2/B2 readback, baseline CI and deployed-revision checks do not establish corrected Production activation or closure. Current sub-track: play identity complete and verified ([byplay_v2 contract](plans/2026-10-09/01-byplay-v2-play-identity.md); provider-keyed identity, invariance proven across 148.5M cells). Remaining repair milestones: the six quality follow-ups, scoring defects, the 95 database-only adjusted rows, the 2025 matchup backfill and Week 6 certification (needs stable finals).
- **Release timing:** Week 6 is live as a display-only run in Production (2026-10-09). Integrity closure still precedes the corrected-lineage cutover for the rest of the lineage: Week 7 is the target only if the successor Week 6 certification integration is built and tested by the Sunday 2026-10-11 checkpoint; otherwise the cutover moves to Week 8 or later. Production activation of the corrected Weeks 0-5 replays is a separate exact approval. **Checkpoint (2026-10-10):** the cutover tooling is built and tested (advance mode, registered-release rollback, bundle gates, Week 6 market-sources lock, Week 7 packet validated against the real Week 5 record; contract [`02`](plans/2026-10-08/02-repair-track-certification-and-closure.md) Amendments 3-7, [run sheet](plans/2026-10-10/01-week7-cutover-run-sheet.md)). The Week 6 data steps (finals, pins, 6A/Task 4/6B extension, replay chain, certification) cannot start before the Week 6 finals have been stable for 24 hours (about Oct 12 03:00Z), so the successor Week 6 certification integration is built only as tooling, not yet run. The 2026-10-09 decision that integrity closure precedes the cutover still stands: the contract's completion-matrix items for the six quality follow-ups, scoring defects, the 95 database-only adjusted rows, the 2025 matchup backfill and descendant recertification of statistics and matchup features are open, so whether Week 7 can go ahead is a user decision at the Tuesday 14:00Z pivot gate (fallback: frozen standalone Week 7).
- **Week 5:** closed and scored 2026-10-04 (56 spread + 56 total grades, 112 total). **Week 6:** see the week table.
- **Matchup pages and team stats:** released and default-on (`CFB_MATCHUP_ENABLED=0` is the emergency opt-out). Preview and Production `team_season_stats` both hold 11,506 rows for as-of weeks 1-5 after the 2026-10-07 republish, plus the 3,036-row as-of-6 snapshot published 2026-10-09. Corrected repinning and the 2025 backfill belong to the repair contract; limitations stay in [known issues](data/known_issues.md).
- Open data issue: the play-by-play running score is non-monotonic for about a third of team-games, which blanks some points-per-scoring-opportunity values; documented in [known data issues](data/known_issues.md). Step 5 admitted corroborated historical changes only; residual baseline errors remain, and the corrected durable rebuild is pending.
- **Historical, superseded 2026-10-09: pre-Week-6 audit (2026-10-07, read-only, restricted roles; the active-run, selection-count and team-stats-row facts below were true then and no longer are; [evidence](plans/2026-10-07/pre-week6-audit-evidence/checksums.txt)):** Preview and Production agree on serving state (`current_week` (2026, 6) with no active run, six selections, all rollback runs present), Week 5 grades (56 predictions, 112 grades, spread 28-27-1, total 25-30-1; identical row hashes), schema (23 migrations through 0024, same ledger), venues (271/271 with city) and the Week 5 `prospective_week_records` row (legacy attestation hashes: Preview `9b3d04f3…`, Production `9f022418…`). The Production registration's operator and time are not recorded in any session log (open). Known differences: Preview `team_season_stats` has 11,506 rows against Production's 10,460, because Preview carries the 2026-10-02 punt-return fix (extra `ppa_per_play` metric, lower play counts in three rate metrics; Production waits for the Window 1 republish); the Preview copy of the Week 4 rollback run is `published` and ungraded where Production's is `scored`. **Correction (2026-10-09):** the Production team-stats republish at 17:05:40Z the same day (see Release state) closed the 11,506 vs 10,460 row difference; the other differences stand as audited.
- Stage 7B foundations are complete: migrations 0023/0024 are applied in Preview and Production and the Week 5 attestations are registered; cutover execution waits for the certified packet ([Stage 7B plan](plans/2026-10-06/02-stage7b-exact-release-and-cutover.md)).

## Where to look next

- [V5 status](modeling/v5_status.md) · [Weekly operator](ops/v5_weekly_operator.md)
  · [Weekly pipeline](ops/weekly_pipeline.md) · [Production runbook](ops/production_runbook.md)
  · [Implementation contracts](plans/index.md)
