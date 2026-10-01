# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-01 · **Verified from:**
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

## In flight

- Week 5: wait for certified finals, then score
  ([weekly operator](ops/v5_weekly_operator.md)).
- Approved, in progress: [authentic team stats pipeline](plans/2026-10-01/10-authentic-team-stats-pipeline.md) (matchup pages stay hidden until approved; data steps run locally).
- Draft contract: production-boundary refactor
  (`plans/2026-10-01/04-production-boundary-refactor.md`).
- Done 2026-10-01: [dead-code prune](plans/2026-10-01/05-dead-code-prune.md) and [docs cleanup/archive](plans/2026-10-01/06-docs-cleanup-and-archive.md) (Implemented).
- Approved, to run locally: [high-quality team logos](plans/2026-10-01/07-high-quality-team-logos.md) (the current 32 px logos look pixelated).
- Approved, data steps to run locally: [game venue location](plans/2026-10-01/08-game-venue-location.md) (UI is on `dev`; run migration `0019` and the venue publish on Preview, then production).
- V6 ratings lab: closed 2026-09-30 (`RETAINED_AS_BENCHMARK`); research only.

## Where to look next

- [V5 status](modeling/v5_status.md) · [Weekly operator](ops/v5_weekly_operator.md)
  · [Weekly pipeline](ops/weekly_pipeline.md) · [Production runbook](ops/production_runbook.md)
  · [Implementation contracts](plans/index.md)
