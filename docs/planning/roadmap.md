# 2026 Season Execution Roadmap

> **Last Updated**: 2026-08-09 | **Status**: Phase 1 complete, Phase 2 next
> **Related**: [Execution Plan](2026_historical_bootstrap_week0_execution.md) | [Decision Log](../decisions/decision_log.md)

This document tracks the tactical plan for launching the 2026 season. The
authoritative execution plan is
[`2026_historical_bootstrap_week0_execution.md`](2026_historical_bootstrap_week0_execution.md).

---

## Timeline

| Milestone | Target | Status |
|---|---|---|
| Data platform modernization | 2026-08-09 | ✅ Complete |
| Phase 1: Encode adjudications | 2026-08-09 | ✅ Complete |
| Phase 2: Historical bootstrap import | 2026-08-10 | ⬜ Next |
| Phase 3: Silver reconciliation | 2026-08-11 | ⬜ Pending |
| Phase 4: Gold + OOF baselines | 2026-08-12 | ⬜ Pending |
| Phase 5: Model selection + refit | 2026-08-15 | ⬜ Pending |
| Phase 6: Week 0 readiness + rehearsal | 2026-08-22 | ⬜ Pending |
| **Week 0 opening slate** | **2026-08-29** | 🏈 Season starts |

---

## Foundation (Completed 2026-08-04 to 2026-08-09)

All foundational infrastructure is code-complete and passing quality gates
(285 tests, contracts, web build):

- **Immutable lake/catalog** — Bronze/Silver/Gold datasets with SHA-256
  checksums, Neon `catalog`/`ops` schemas, migrations 0002–0004.
- **CFBD ingestion hardening** — Client 5.20.1, typed source contracts,
  fail-closed error classification, point-in-time capture.
- **Week 0 regime modeling** — Five completed-game routes (0/1/2/3/4+) × two
  targets, Ridge/CatBoost/blend candidates, temporal folds 2022–2024.
- **Historical bootstrap tooling** — Read-only production R2 access, source
  inventory (36,138 objects → 7,156 eligible), resumable `make import-history`.
- **Resumable operations** — `cks_picks_cfb.ops` state machine for publish,
  freeze, close, replay, reconciliation.
- **Web app readiness** — Next.js reads immutable prediction runs via Neon,
  progressive publish, local Geist fonts.

---

## Execution Phases

### Phase 1: Encode the Adjudications — ✅ COMPLETE

Implemented the two approved data-policy contracts:

- **`legacy_market_references` Silver dataset** — Untimestamped historical
  betting-line exports are preserved as an immutable, inert dataset with
  flags (`exact_replay_eligible=false`, `grading_eligible=false`,
  `lean_eligible=false`, `timestamp_status=missing_authentic_timestamp`).
  They cannot enter canonical `market_quotes`, model features, leans, grades,
  ROI, or model selection. Provider routing (`DATASET_PROVIDERS`) separates
  legacy (`legacy_cfbd_export`) from canonical (`cfbd`) captures.
- **Versioned canonical Week 0 policy** — Silver schedules preserve
  `provider_week` exactly. A versioned `schedule_week_policy` dataset
  assigns `canonical_week` by explicit game-ID assignments
  (`conf/policy/canonical_week_2026_v1.yaml`). The 2026 August 29 opening
  slate (8 games) is assigned canonical Week 0.
- **Exact-market audit mode** — `make audit-data MODE=exact-market` reports
  legacy quarantine status and lineage purity without treating missing
  canonical markets as a structural failure.
- **Contract tests** — 17 new tests proving legacy lines cannot produce
  leans/grades/ROI/features and the Week 0 policy is correct.

**Exit gate**: ✅ Legacy lines preserved without weakening canonical markets;
all Week 0 tests pass while provider weeks remain intact.

### Phase 2: Run the Resumable Historical Bootstrap — ⬜ NEXT

```bash
make import-history   # preview-only; reads prod R2, writes preview R2/Neon
```

- Import 2019 prior inputs and all eligible 2021–2026 objects; reject 2020.
- Verify each preview Bronze object against source SHA-256.
- Resume after recoverable failures (same pipeline-run ID).

**Exit gate**: Every eligible object imported or classified; all checksums
match; no production write possible; no 2020 lineage.

### Phase 3: Build and Reconcile Canonical Silver — ⬜ Pending

- Season-scoped teams, aliases, venues, schedule, games, plays, outcomes,
  weather, preseason inputs, legacy market references.
- Pull missing team-game statistics via hardened CFBD adapter.
- Reconcile completed 2021–2025 games across schedules, plays, box scores.
- Produce combined 2021–2025 training references.

**Exit gate**: Zero unexplained blocking conflicts; complete eligible game
keys and targets; explicit coverage/missingness for every source.

### Phase 4: Build Structural and Model-Ready Gold — ⬜ Pending

- Kickoff-ordered team-side features with completed-game regime routing.
- Deterministic game-wide views for the five regimes.
- Temporal OOF baseline predictions for 2022–2024.
- Model-ready Gold without joining legacy market references.

**Exit gate**: Structural and model-ready audits pass; 2019 only in early-2021
prior lineage; every 2022–2024 row has eligible OOF baselines.

### Phase 5: Select, Lock, Test, and Refit Models — ⬜ Pending

- Ridge, CatBoost, and blend candidates for spread and total in all 5 regimes.
- Select using only 2022–2024 OOF artifacts.
- Freeze design; open 2025 once for locked anti-regression evaluation.
- Mark market-dependent gates as unavailable where authentic quotes absent.
- Refit on 2021–2025 → one checksummed ten-route `model_bundle_v2`.

**Exit gate**: All ten routes exist; predictive gates reproducible; no result
from 2025 influenced design selection.

### Phase 6: Capture and Rehearse Live 2026 Week 0 — ⬜ Pending

- Capture immutable preseason snapshot before first kickoff
  (**external blocker: CFBD talent feed still empty as of 2026-08-08**).
- Capture live market quotes with authentic timestamps via canonical adapter.
- Run Week 0 readiness in preview; publish progressively; freeze validated run.
- Replay 2025 for predictive/site equivalence.
- Verify Vercel preview, health, canonical Week 0 navigation, failure non-activation.

**Exit gate**: Every opening-slate FBS-vs-FBS game appears; run reproducible
from ID; current quotes authentic; site distinguishes preview/published/frozen.

---

## External Blockers

| Blocker | Impact | Status |
|---|---|---|
| CFBD talent feed empty | Gates preseason snapshot (all 5 sources must be nonempty) | Recheck later in August |
| Week 1 betting line coverage | 51/99 games with provider line (as of 2026-08-08) | Expected to fill before kickoff |

---

## Stop Conditions

Stop rather than infer or silently degrade if:

- A source introduces 2020 data or lineage.
- An untimestamped market value routes toward canonical markets, grading,
  ROI, leans, or confidence.
- A completed eligible game has an unresolved blocking reconciliation conflict.
- Source and destination bucket identities match.
- A failed pipeline step would activate a dataset or prediction run.
- The locked 2025 command is invoked without a frozen-design SHA.

---

_Previous sprint-based roadmap (Sprint 4: MLOps Foundation) has been superseded
by this 2026 execution roadmap. See `session_logs/` for historical context._
