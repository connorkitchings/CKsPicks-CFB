# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-03 · **Verified from:**
> `session_logs/2026-09-30/01-verify-deploy-freeze-week5-close-contract.md`
> and the [repaired-V5 release packet](plans/2026-09-29/v5-intended-update-production-release-packet.md).

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

## Week state (2026 season)

| Week | State | Selected run |
|---|---|---|
| 0–4 | Scored; **retrospective replay** (not prospective evidence) | `2026w{0..4}-v5repair-20260929-p1` |
| 5 | **Frozen** 2026-09-30T12:34:06Z, 56/56/56, ungraded. First kickoff 2026-10-02 00:00Z. Score only after certified finals + 24 h stabilization. | `2026w5-v5repair-20260929-p2` |
| 6 | Not opened | — |

**Rollback set (exact):** `2026w{0..4}-v5replay-bestquote-20260926-r3` and
`2026w5-5d436e58c072`. An earlier Week 5 run, `2026w5-d6366e59fd43`, is
superseded and kept only as an audit record.

## Scoreboard

**Primary success metric:** prospective ATS win % vs the 52.4% break-even at
-110, reported separately for spreads and totals. MAE, calibration and the
pre-registered promotion gates remain diagnostics.

| Evidence class | Spread | Total | Notes |
|---|---|---|---|
| **Prospective (frozen before kickoff)** | 0 graded | 0 graded | Week 5 is the first live V5 slate |
| Retrospective replay, Weeks 0–4 | 100-112-3 (47.2%) | 112-102-0 (52.3%) | Not prospective evidence (unconstrained; 212 decided spreads, 214 decided totals; 1 unlined W3 total) |

Neither retrospective target clears 52.4%. In the 2025 holdout the market had
lower error than V5 on both targets, and the docs do not claim V5 beats V4.

## Branches

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

`main` was fast-forwarded to `dev` at the 2026-10-02 close-out (previous release `53d346b`). That release carries the Picks/Results prototype port (city/state and sportsbook-behind-the-line on the production slate cards; rank badges stay off the cards by design; the `/test-picks` and `/test-results` routes are removed), the unconstrained-grading pipeline changes, the team-stats punt fix (code), and the matchup refinements including the Share card. Built but closed in production: `/matchup/[gameId]` (until `CFB_MATCHUP_ENABLED=1`), so the PPA/play change and the Share button are not visible there yet. CI's browser suite now runs with `CFB_PUBLICATION_MODE=predictions` set by `web/playwright.config.ts` (see `web/README.md`). **Picks/Results card redesign (complete, released 2026-10-02):** the bet-cell cards ("Best bets" panel, team filter, grid/list toggle) replace the old slate cards. Closing it out fixed two regressions the browser suite caught (Results cards had lost their Matchup button; the Best-bets columns overflowed a 390px phone) and updated the e2e tests to the new controls and card text; the suite is 43/43.

## In flight

- Week 5: wait for certified finals, then score
  ([weekly operator](ops/v5_weekly_operator.md)). **Close gate:** after certified finals the close must produce 56 spread and 56 total grades (minus any unlined); because the frozen Week 5 predictions hold null leans on 7 spreads and 8 totals, grade with `scripts/pipeline/backfill_v5_unconstrained_grades.py --week 5 --grades-only` (it never writes `predictions` or `prediction_market_selections` for a non-replay run). Plan: [remove edge constraints, grade all games](plans/2026-10-02/04-remove-edge-constraints-grade-all-games.md): implemented; Weeks 0-4 backfilled on Preview and production (user-run 2026-10-02).
- Approved, in progress: [authentic team stats pipeline](plans/2026-10-01/10-authentic-team-stats-pipeline.md). **Code released to `main` (`53d346b`); data live on Preview and production** as of 2026-10-02 (Silver promoted, migrations 0019/0020 applied, team stats weeks 1-5 = 10,460 rows, venues = 271), run by the user and verified read-only; checked against CFBD (Amendment 1). Remaining: set `CFB_MATCHUP_ENABLED=1` when the matchup page is approved, then mark the contract Implemented; re-run team stats for week 6 after Week 5 finals.
- Draft contract: production-boundary refactor
  (`plans/2026-10-01/04-production-boundary-refactor.md`).
- Done 2026-10-01: [dead-code prune](plans/2026-10-01/05-dead-code-prune.md) and [docs cleanup/archive](plans/2026-10-01/06-docs-cleanup-and-archive.md) (Implemented).
- Approved, in progress: [matchup data layer v2](plans/2026-10-02/01-matchup-data-layer-v2.md): everything the V5 ratings use per team per week (raw V5 metrics shown on matchups, separate adjusted values, per-game log, rating decomposition), bound to the served rating manifest. **Phase A (2026) is live on Preview and production** (user-run 2026-10-02): migration 0021, the four data tables published with Preview's payload hash `a4a1062d…71215` and verified read-only (0 rows differing, 11 gates ok), and the Silver stats republished with the V5 play filter. Web code reading the new tables is released to `main`; pending: `CFB_MATCHUP_ENABLED=1` when the matchup page is approved, Phase B (2025).
- **Next session:** run the [unified data fix and matchup rollout](plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md) (approved 2026-10-03; supersedes the 2026-10-02 review-and-rerun draft and bundles plan 03 Phase 2 and plan 01 Phase B as decision gates D1–D6). Read-only Phase 1 first, then decisions, then one Preview-then-production rerun.
- Open data issue: the play-by-play running score is non-monotonic for about a third of team-games, which blanks some points-per-scoring-opportunity values; documented in [known data issues](data/known_issues.md) with a review-and-rerun checklist; investigation deferred.
- Matchup Share button (released to `main` with the matchup page, closed in production): exports a fixed 1080x1350 card per matchup (`ShareCard`/`ShareButton`); e2e covers the export size and canvas fit.
- Team stats punt-leak fix ([plan](plans/2026-10-02/03-team-stats-feeds-ratings.md)): code released to `main`, Preview republished 2026-10-02 (weeks 1-5, hand-check exact). **Production republish is on hold and bundled with the [unified data fix and matchup rollout](plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md)** ([known data issues](data/known_issues.md)): production still shows the pre-fix conversion, explosive and turnover rates and has no `ppa_per_play` rows; the matchup page, which reads them, is closed in production and must stay closed until the batch is done. Known issue until the planned rating rebuild: V5 `epa_per_play` / `plays_per_possession` still count returned punts (stored, not shown); `ppp` and `epa_per_possession` are unaffected.
- Approved: [game venue location](plans/2026-10-01/08-game-venue-location.md): venue data live in production (271 games); the city/state UI now renders on the real Picks/Results cards (prototype port released).
- V6 ratings lab: closed 2026-09-30 (`RETAINED_AS_BENCHMARK`); research only.

## Where to look next

- [V5 status](modeling/v5_status.md) · [Weekly operator](ops/v5_weekly_operator.md)
  · [Weekly pipeline](ops/weekly_pipeline.md) · [Production runbook](ops/production_runbook.md)
  · [Implementation contracts](plans/index.md)
