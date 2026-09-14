# 2026 Operations and Ratings Research Roadmap

> **Last updated:** 2026-09-13
> **Production champion:** V4 ten-route bundle `week0-2026-v4-strict-20260818-r2`

> **Authority note (2026-09-05):** This page remains the current V4 operations
> authority and historical record of the R1/R2 successor work. The pending R3/R4
> sequence and unfinished research portion are superseded by the
> [data-first football forecasting roadmap](data-first-football-forecasting-roadmap.md).
> Completed artifacts remain immutable evidence subject to its Phase 1 audit.

> **Current research checkpoint (2026-09-13):** V5 ratings successor research
> is distinct from the V4 feature schema v5 diagnostic. Repair v2 is verified;
> Phase 3 v2 is certified. The possession methodology is specified and amended;
> possession measurements remain uncertified. The next ratings task is
> 02: possession measurement certification. See the
> [data-first roadmap](data-first-football-forecasting-roadmap.md) for the active
> 00–06 queue. Contract 01 closes the independent V4 diagnostic. The original
> Phase 4B retained manifest remains prohibited as a forecasting parent.

## Direction

V4 remains the live, rollback-safe 2026 production system. The approved
successor makes a point-in-time team rating/state—not a matchup feature row—the
canonical representation of team quality.

```text
source data → Bronze/Silver/Gold → football measurements
→ measurement-level opponent adjustment → team ratings/state
→ rating-to-margin/total Ridge bridge → probabilistic output
→ timestamped line comparison
```

No successor is activation-eligible today. The active research authority is the
[data-first football forecasting roadmap](data-first-football-forecasting-roadmap.md).
See the
[rating-system requirements](../modeling/rating_system_requirements.md),
[measurement catalog](../modeling/measurement_catalog.md), and
[evaluation policy](../modeling/evaluation.md).

## Current production

- V4 uses five completed-game regimes (`game_1` through `game_4` and
  `established`) for spreads and totals. Its sealed 2022–2024 temporal
  selection, locked-2025 anti-regression check, and 2021–2025 refit remain its
  authoritative lineage.
- Production runs use immutable R2 artifacts, Neon run state, and fail-closed
  publication. The [weekly pipeline](../ops/weekly_pipeline.md) and
  [production runbook](../ops/production_runbook.md) govern operations.
- Market quotes are timestamped decision inputs after prediction; they never
  enter football-model inputs or selection.

## Two explicit tracks

### Historical R1–R4 research track (superseded)

| Stage | Deliverable | Boundary |
| --- | --- | --- |
| R1 | Expanded, certified historical corpus: 2015–2019 and 2021–2025 | 2020 is forbidden; 2026 outcomes are protected and excluded. |
| R2 | Sealed between-season prior tournament | 2025 is locked; 2019→2021 is a two-year stress transition, not a normal fit example. |
| R3 | Sealed within-season state-update tournament | Superseded before implementation; retained as historical planning evidence. |
| R4 | Structured predictor tournament and candidate-v2 freeze | Superseded before implementation; retained as historical planning evidence. |

### 2026 operations track

| Stage | Deliverable | Boundary |
| --- | --- | --- |
| O1 | Unchanged V4 production operations | V4 remains champion, rollback authority, and public system. |
| O2 | Candidate-v1 diagnostic evidence from `ac1fba1` | Isolated worktree; diagnostic-only; it cannot block R1–R4. |
| O3 | Candidate-v2 protected evidence and later promotion review | New prospective lane; no evidence transfers or backdating. |

## Operational milestones

| Window | Deliverable | Status |
| --- | --- | --- |
| By 2026-08-28 | Documentation audit, measurement catalog, initial rating requirements, uncertainty and shadow-evaluation requirements, and follow-on contracts | ✅ Complete |
| **2026-08-29–31 (Week 0 close)** | Week 0 games scored; freeze + close-week; Week 0 launch contract closed | ✅ Complete |
| **Week 1** | Published, frozen, and scored | ✅ Verified 2026-09-10: 43 games / 86 grade rows |
| **Week 2** | Scored | ✅ Recorded 2026-09-13: `2026w2-43b25511a100`, 49 games; 90 graded targets |
| **Week 3** | Published | Recorded 2026-09-13: `2026w3-68fe6a815bd6`, 57/57/56; freeze pending at that checkpoint |
| Current research | 02: possession measurement certification, then rating and bridge selection | Preview-only; approved downstream contracts require verified parents |
| Subsequent weeks | Structured rating-to-game prediction, then frozen candidate shadow scoring | No Neon activation or publication |
| Six completed full slates | First promotion review, if every candidate prediction was frozen before kickoff | Separate approval required |
| Any later point in 2026 | Operational rehearsal, rollback proof, and evidence-based promotion decision | V4 remains fallback |

Week 0 does not count as a full slate. A full slate has normal schedule coverage
and both V4 and candidate predictions frozen before its first kickoff.

## Preserved production invariant

Do not change V4 weights, routes, bundles, publication policy, weekly workflow,
or rollback behavior as part of rating research. V4 is the production benchmark
for every challenger. Rating work has no path to Neon activation, public
publication, or production rollback selection before a separate promotion
contract is approved.

## Historical successor rules

The superseded successor design required R1 reconstruction under new identities
and sequential R2–R4 sealed tournaments, with 2025 as locked confirmation.
Those rules remain attached to existing experiment identities only. Under the
new program, 2025 is development evidence, every admitted input is audited
before modeling, and future frozen forecasts provide prospective evidence.

Candidate-v2 prospective evidence begins only after its committed identity is
frozen. It has a new six-slate counter and cannot inherit candidate-v1 evidence.
Authentic timestamped market evaluation follows football-model evaluation; a
calendar date cannot bypass a failed gate.

## Planning and execution protocol

- The data-first roadmap controls research sequencing; the September 13 V5
  contracts 00–06 are the active task-level authority.
- The O2 candidate-v1 lane remains reproducible only from its pinned `ac1fba1`
  worktree and is never an input to candidate-v2 selection.
- No outcome may be claimed as prospective evidence unless its prediction was
  frozen before kickoff. Missing a prospective window never permits a
  retrospective freeze.

## Historical phase contract queue (not current execution authority)

These entries retain their dated findings and former lifecycle states. Use the
[data-first roadmap](data-first-football-forecasting-roadmap.md) for current
contracts; historical approvals below do not authorize execution.

- [Approved high-level roadmap](../plans/2026-08-24/rating-centric-successor-high-level-roadmap.md)
  — sequencing and governance authority; not a single Terra implementation task.
- [Phase 1 measurement foundation](../plans/2026-08-24/phase1-rating-measurement-foundation.md)
  — Approved documentation and planning contract. Its seven-measurement
  catalog, four-iteration adjustment, temporal-status policy, and Preview-only
  registration policy are frozen; implementation remains a separate Terra task.
- [Phase 2 minimum viable team-state baseline](../plans/2026-08-24/phase2-minimum-viable-team-state-baseline.md)
  — Implemented 2026-08-25 from the bounded Phase 1 v2 handoff
  ([completion contract](../plans/2026-08-24/phase1-phase2-completion.md));
  Preview state artifacts pass all audit gates with byte-identical reruns.
- [Phase 3 score-model tournament v2](../plans/2026-08-25/phase3-score-model-tournament-v2.md)
  — In Progress. v1 is immutable failed research. v2 completed its sealed
  linear-versus-NB2 selection after one mechanical bounded-fit correction, but
  neither complete family passed every frozen gate. Only the immutable
  diagnostic exists; no candidate froze, locked-2025 confirmation ran, or
  Phase 4 work may begin.
- [True-PPSO Phase 1/2 remediation and Phase 3 v3](../plans/2026-08-26/phase1-phase2-true-ppso-remediation-and-phase3-v3.md)
  — Implemented 2026-08-26. Phase 1 v3 is certified, Phase 2 v2 passed its
  representative location gates and byte-identical rerun, and the sealed v3
  tournament froze `negative_binomial_scores` as candidate v1 (locked-2025:
  margin MAE 13.30 vs V4 15.52 with positive paired lift; total at parity; all
  calibration gates true). Phase 4 shadow operations are implemented: the
  Preview-only all-2025 rehearsal passed all 15 weeks and byte-identical rerun
  (summary SHA-256 `b755b585…`); no production interface changed. Phase 5
  protected-evidence tooling is amended into the O2 diagnostic lane under
  [its operations contract](../plans/2026-08-26/phase5-protected-prospective-evidence.md).
- [Historical expansion and ratings methodology reset](../plans/2026-08-26/historical-expansion-ratings-methodology-reset.md)
  — **Superseded after completed R1/R2 evidence.** Historical R1–R4 research contract: 2015–2019 plus
  2021–2025, universal 2020 exclusion, staged methodology tournament, and a
  future candidate-v2 evidence lane. The remediated R1 run
  `r1-full-corpus-20260831-5f2a384` is certified: its immutable
  `coverage.json` sets `tournaments_permitted: true`. The fresh, code-bound
  Preview admission at `early-week-context-20260904-786580ec-r2` admits only
  reconstructed returning production, recruiting, and coaching; direct
  early-game research and R2 used only that passing report. The R2
  between-season prior tournament completed 2026-09-04 at
  `r2-prior-20260904-4c6e610` (winner `continuity_ridge_alpha_0_1` via the
  0.5% simplicity tie; all gates passed; reconstructed and
  activation-ineligible — see the
  [cross-report memo](../research/2026-09-04-early-week-context-cross-report.md)).
  Its completed R1/R2 evidence remains available for audit. The data-first
  program now requires the 2026-09-08 corrective sequence; prior
  engineering completion does not establish predictive eligibility.

## Invariants and deferred challengers

All work preserves immutable lineage, strict point-in-time provenance, temporal
validation, 2020 exclusion, market separation, frozen evaluation, and research
isolation. The V5 package specifies the rating definitions, priors, updates,
uncertainty, bridge and artifact interfaces. Possession arithmetic, clock tempo,
field-position normalization, NB2 and residual ML are later challengers; production
promotion remains a separate contract. Fixed constants and fitting windows are
specified in the [methodology](../modeling/possession_rating_methodology.md).
