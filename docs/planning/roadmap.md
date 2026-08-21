# 2026 Season Execution Roadmap

> **Last Updated**: 2026-08-21 | **Status**: Week 0 launch in progress — production is live; game-week operations (Aug 25–29) remain
> **Related**: [Modernization & Refactoring Plan](2026_codebase_modernization_and_refactoring_plan.md) | [Execution Plan](2026_historical_bootstrap_week0_execution.md) | [Active Launch Contract](../plans/2026-08-18/week0-launch-execution.md) | [Decision Log](../decisions/decision_log.md)

The 2026 season buildout is complete. The authoritative remaining-work document is the
Week 0 launch contract,
[`docs/plans/2026-08-18/week0-launch-execution.md`](../plans/2026-08-18/week0-launch-execution.md)
(Stages 4–5 pending game week).

---

## Timeline

| Milestone | Target | Status |
|---|---|---|
| Data platform modernization | 2026-08-09 | ✅ Complete |
| Phase 1: Encode adjudications | 2026-08-09 | ✅ Complete |
| Phase 2: Historical bootstrap import | 2026-08-10 | ✅ Complete (2026-08-13) |
| Phase 3: Silver reconciliation | 2026-08-11 | ✅ Complete (2026-08-14) |
| Phase 4: Gold + OOF baselines | 2026-08-12 | ✅ Complete (2026-08-14) |
| Phase 5: Model selection + refit | 2026-08-15 | ✅ Complete (2026-08-18, V4 tournament) |
| Phase 6: Week 0 readiness + launch | 2026-08-22 | 🟡 In progress — production live 2026-08-18 |
| **Week 0 opening slate** | **2026-08-29** | 🏈 Game week ops Aug 25–29 |

---

## Current State (2026-08-19)

**Production is live.** The Vercel app at
`https://c-ks-picks-cfb.vercel.app` is deployed in fail-closed `market`
publication mode. The active immutable run is authoritative only through
`/api/health` and `current_week.active_run_id`; progressive publishes replace
that pointer without mutating prior runs.

**Launch model:** the V4 ten-route bundle `week0-2026-v4-strict-20260818-r2`
(design SHA `ae34ddc7…`), selected via sealed 2022–2024 OOF tournament, validated
on locked 2025 (all 8 routes passed anti-regression), and refit on 2021–2025.
Launch config: `conf/weekly_bets/v4_2026.yaml`. All 8 Week 0 games route to
`game_1` (spread: direct CatBoost; total: prior-quality baseline fallback).
2025 betting simulation (research only, legacy lines): +17.9 units (+3.1% ROI).

**Production topology:** Neon production branch (migrations 0002–0008; catalog
hydrated from Preview via COPY — 7,163 source captures, 85 dataset versions;
`cks_prod_web` read-only LOGIN role for Vercel). Production R2 shares the
Preview bucket `cks-picks-cfb-preview` (immutable artifacts are checksummed and
environment-neutral); environment separation is by Neon branch.

### Remaining Work (launch contract Stages 4–5)

- **Stage 4 — Game week (Aug 25–29):** progressive `publish-week ENV=production`
  reruns as lines arrive; Aug 28 final publish → user review → `freeze-week`
  before kickoff → user-approved flip of `CFB_PUBLICATION_MODE` from `market`
  to `predictions` → redeploy + smoke test. Optional CFBD Pick'em submission
  (requires `CFBD_PREDICTION_TOKEN`; dry-run reconciliation then explicit
  approval of game IDs and margins).
- **Stage 5 — Post-slate (Aug 30+):** `close-week` + scoring, health freshness
  checks, launch retrospective, and the Week 1 operating cadence.

---

## Foundation (Completed 2026-08-04 to 2026-08-18)

All foundational infrastructure is code-complete and passing quality gates
(355 tests passed / 2 skipped, contracts, web build):

- **Immutable lake/catalog** — Bronze/Silver/Gold datasets with SHA-256
  checksums, Neon `catalog`/`ops` schemas, migrations 0002–0008.
- **CFBD ingestion hardening** — Client 5.20.1, typed source contracts,
  fail-closed error classification, point-in-time capture.
- **Week 0 regime modeling** — Five completed-game routes (`game_1`–`game_4`,
  4+ = established) × two targets, Ridge/CatBoost/blend candidates, temporal
  folds 2022–2024.
- **Historical bootstrap tooling** — Read-only production R2 access, source
  inventory (36,138 objects → 7,156 eligible), resumable `make import-history`
  (executed to completion 2026-08-13).
- **Resumable operations** — `cks_picks_cfb.ops` state machine for publish,
  freeze, close, replay, reconciliation.
- **Web app** — Next.js reads immutable prediction runs via Neon, progressive
  publish, local Geist fonts, fail-closed publication modes (`market` /
  `predictions`).

---

## Execution Phases — All Buildout Phases Complete

### Phase 1: Encode the Adjudications — ✅ COMPLETE (2026-08-09)

- **`legacy_market_references` Silver dataset** — Untimestamped historical
  betting-line exports preserved as an immutable, inert dataset
  (`exact_replay_eligible=false`, `grading_eligible=false`,
  `lean_eligible=false`). They cannot enter canonical `market_quotes`, model
  features, leans, grades, ROI, or model selection.
- **Versioned canonical Week 0 policy** — Silver schedules preserve
  `provider_week`; a versioned `schedule_week_policy` dataset assigns
  `canonical_week` by explicit game-ID assignments
  (`conf/policy/canonical_week_2026_v1.yaml`). The 2026 August 29 opening
  slate is canonical Week 0.
- **Exact-market audit mode** + 17 contract tests.

### Phase 2: Resumable Historical Bootstrap — ✅ COMPLETE (2026-08-13)

All 7,156 eligible objects imported to Preview Bronze with verified source
SHA-256 checksums (2019 prior inputs + 2021–2026; 2020 rejected). The
`import-history` pipeline was modularized (`--skip-imports`,
`make import-history-silver`) and completed end-to-end after Silver contract
fixes. No production write occurred; no 2020 lineage exists.

### Phase 3: Canonical Silver Reconciliation — ✅ COMPLETE (2026-08-14)

Season-scoped teams, aliases, venues, schedule revisions, games, plays,
outcomes, weather, preseason inputs, and legacy market references built and
reconciled across schedules, plays, and box scores for completed 2021–2025
games, with combined 2021–2025 training references produced.

### Phase 4: Structural and Model-Ready Gold — ✅ COMPLETE (2026-08-14)

Kickoff-ordered team-side features with completed-game regime routing,
deterministic game-wide views for all five regimes, strictly temporal OOF
baseline predictions for 2022–2024, and model-ready Gold without legacy
market references. Audited preview Gold was rebuilt and frozen as the input
lineage for the model tournaments.

### Phase 5: Select, Lock, Test, and Refit Models — ✅ COMPLETE (2026-08-18)

Executed as the V4 tournament under the
[Week 0 launch contract](../plans/2026-08-18/week0-launch-execution.md):

- **Model lineage:** V2 display-fallback preview bundle
  (`week0-2026-preview-20260814`, published/frozen 2026-08-14) → V3 games-ordinal
  rehearsal (2026-08-16, prediction-only) → **V4 strict bundle
  `week0-2026-v4-strict-20260818-r2`** (selected 2026-08-18).
- **Selection (sealed 2022–2024 OOF):** 4 of 8 challenger routes beat baseline
  (spread/game_1 direct_catboost −1.43 MAE; total/game_2–4 blends −0.5 to
  −1.5 MAE). Design SHA frozen at `ae34ddc7…`.
- **Locked 2025:** all 8 routes passed anti-regression.
- **Refit:** ten-route bundle refit unchanged on 2021–2025; V4 readiness passed
  in Preview; V4 published and activated.
- **Feature posture:** `prior_core` only (`prior_only_fallback`) — CFBD talent
  feed is empty; the user decided to launch without additive preseason
  families and stop rechecking (2026-08-18).

### Phase 6: Capture and Rehearse Live 2026 Week 0 — 🟡 IN PROGRESS

Complete so far:

- ✅ 2026 schedule refresh + available preseason capture (prior-only posture).
- ✅ Live market quotes captured with authentic timestamps via the canonical
  adapter (The Odds API); missing lines stay visible but cannot create leans.
- ✅ Preview rehearsal (V2/V3/V4 comparison CSV) and Preview publish
  (run `2026w0-3e4fa1b07d`).
- ✅ Production setup: Neon production branch (0002–0008), `cks_prod_web`
  role, catalog hydration, R2 routing, production publish (run
  `2026w0-79ec2aebcb00`), Vercel production deploy in `market` mode, health
  verification.
- ⬜ Stage 4 game-week operations (progressive publishes, freeze,
  predictions-mode flip on approval, optional Pick'em).
- ⬜ Stage 5 post-slate close-out and Week 1 cadence.

Note: exact historical market replay/grading of 2025 remains blocked by design
(legacy lines are untimestamped); predictive/site equivalence was replayed
instead.

---

## External Blockers

| Item | Impact | Status |
|---|---|---|
| ~~CFBD talent feed empty~~ | Would have gated preseason snapshot | **Resolved by decision (2026-08-18):** launch with `prior_only_fallback`; no further rechecks this season |
| Week 0/1 betting line coverage | Games without lines display without leans (fail-closed) | Expected to fill before kickoff; watch during game-week publishes |
| `CFBD_PREDICTION_TOKEN` | Blocks authenticated Pick'em reconciliation/submission | User to supply before Stage 4 Pick'em (optional path) |

---

## Stop Conditions

Stop rather than infer or silently degrade if:

- A source introduces 2020 data or lineage.
- An untimestamped market value routes toward canonical markets, grading,
  ROI, leans, or confidence.
- A completed eligible game has an unresolved blocking reconciliation conflict.
- Source and destination bucket identities match.
- A failed step would activate a dataset or prediction run.
- The locked 2025 command is invoked without a frozen-design SHA.

---

_Previous sprint-based roadmap (Sprint 4: MLOps Foundation) was superseded by
the 2026 execution roadmap; the 6-phase buildout itself is now complete and
this roadmap tracks the launch. See `session_logs/` for historical context._
