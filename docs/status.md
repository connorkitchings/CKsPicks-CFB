# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-02 · **Verified from:**
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
| Retrospective replay, Weeks 0–4 | 93-103-3 (47.4%) | 82-77-0 (51.6%) | Not prospective evidence |

Neither retrospective target clears 52.4%. In the 2025 holdout the market had
lower error than V5 on both targets, and the docs do not claim V5 beats V4.

## Branches

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

`main` and `dev` were synced at `53d346b` on 2026-10-02 and production is serving that release (CI green): self-hosted WebP logos on the real Picks/Results cards, venue data in the page payload, and the fixed optional-table checks. On `dev`, the Picks/Results prototype port is implemented and pending release: city/state and sportsbook-behind-the-line now render on the production slate cards (rank badges stay off the cards by design), and the `/test-picks` and `/test-results` prototype routes are removed. Production keeps serving the previous cards until `main` is fast-forwarded. Built but closed in production: `/matchup/[gameId]` (until `CFB_MATCHUP_ENABLED=1`). Later commits on `dev` land here first; release by fast-forwarding `main` (see `AGENTS.md`, Branching).

## In flight

- Week 5: wait for certified finals, then score
  ([weekly operator](ops/v5_weekly_operator.md)).
- Approved, in progress: [authentic team stats pipeline](plans/2026-10-01/10-authentic-team-stats-pipeline.md). **Code released to `main` (`53d346b`); data live on Preview and production** as of 2026-10-02 (Silver promoted, migrations 0019/0020 applied, team stats weeks 1-5 = 10,460 rows, venues = 271), run by the user and verified read-only; checked against CFBD (Amendment 1). Remaining: set `CFB_MATCHUP_ENABLED=1` when the matchup page is approved, then mark the contract Implemented; re-run team stats for week 6 after Week 5 finals.
- Draft contract: production-boundary refactor
  (`plans/2026-10-01/04-production-boundary-refactor.md`).
- Done 2026-10-01: [dead-code prune](plans/2026-10-01/05-dead-code-prune.md) and [docs cleanup/archive](plans/2026-10-01/06-docs-cleanup-and-archive.md) (Implemented).
- Approved, in progress: [matchup data layer v2](plans/2026-10-02/01-matchup-data-layer-v2.md): everything the V5 ratings use per team per week (raw V5 metrics shown on matchups, separate adjusted values, per-game log, rating decomposition), bound to the served rating manifest. **Phase A (2026) is live on Preview and production** (user-run 2026-10-02): migration 0021, the four data tables published with Preview's payload hash `a4a1062d…71215` and verified read-only (0 rows differing, 11 gates ok), and the Silver stats republished with the V5 play filter. Pending: release `dev` to `main` (web code reading the new tables), `CFB_MATCHUP_ENABLED=1` when the matchup page is approved, Phase B (2025).
- Open data issue: the play-by-play running score is non-monotonic for about a third of team-games, which blanks some points-per-scoring-opportunity values; documented in [known data issues](data/known_issues.md), investigation deferred.
- Matchup Share button (`32efe35` on `dev`): exports a fixed 1080x1350 card per matchup; pending release with the rest of `dev`; e2e not yet run (local server holds Next's lock).
- Team stats punt-leak fix ([plan](plans/2026-10-02/03-team-stats-feeds-ratings.md)): code on `dev` (`5acd051`, `8065c56`), Preview republished 2026-10-02 (weeks 1-5, hand-check exact). **Pending: user-run production republish and release of the PPA/play web change together** (production still shows the pre-fix conversion, explosive and turnover rates). Known issue until the planned rating rebuild: V5 `epa_per_play` / `plays_per_possession` still count returned punts (stored, not shown); `ppp` and `epa_per_possession` are unaffected.
- Approved: [game venue location](plans/2026-10-01/08-game-venue-location.md): venue data live in production (271 games); the city/state UI exists only in the closed prototypes until they are ported to the real cards.
- V6 ratings lab: closed 2026-09-30 (`RETAINED_AS_BENCHMARK`); research only.

## Where to look next

- [V5 status](modeling/v5_status.md) · [Weekly operator](ops/v5_weekly_operator.md)
  · [Weekly pipeline](ops/weekly_pipeline.md) · [Production runbook](ops/production_runbook.md)
  · [Implementation contracts](plans/index.md)
