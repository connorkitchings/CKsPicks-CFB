# 2026 Operations and Ratings Research Roadmap

> **Last updated:** 2026-08-26
> **Production champion:** V4 ten-route bundle `week0-2026-v4-strict-20260818-r2`

## Direction

V4 remains the live, rollback-safe 2026 production system. The approved
successor makes a point-in-time team rating/state—not a matchup feature row—the
canonical representation of team quality.

```text
source data → Bronze/Silver/Gold → football measurements
→ measurement-level opponent adjustment → team ratings/state
→ structured game prediction → optional ML residual → probabilistic output
→ market decision
```

The successor may be promoted during 2026 only through a later, separately
approved evidence and promotion review. It is not activation-eligible today.
The active research authority is the
[historical expansion and ratings methodology reset](../plans/2026-08-26/historical-expansion-ratings-methodology-reset.md).
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

### Research track

| Stage | Deliverable | Boundary |
| --- | --- | --- |
| R1 | Expanded, certified historical corpus: 2015–2019 and 2021–2025 | 2020 is forbidden; 2026 outcomes are protected and excluded. |
| R2 | Sealed between-season prior tournament | 2025 is locked; 2019→2021 is a two-year stress transition, not a normal fit example. |
| R3 | Sealed within-season state-update tournament | R2 winner is locked before selection. |
| R4 | Structured predictor tournament and candidate-v2 freeze | Candidate v2 only freezes if every historical gate passes. |

### 2026 operations track

| Stage | Deliverable | Boundary |
| --- | --- | --- |
| O1 | Unchanged V4 production operations | V4 remains champion, rollback authority, and public system. |
| O2 | Candidate-v1 diagnostic evidence from `ac1fba1` | Isolated worktree; diagnostic-only; it cannot block R1–R4. |
| O3 | Candidate-v2 protected evidence and later promotion review | New prospective lane; no evidence transfers or backdating. |

## Operational milestones

| Window | Deliverable | Promotion status |
| --- | --- | --- |
| By 2026-08-28 | Documentation audit, measurement catalog, initial rating requirements, uncertainty and shadow-evaluation requirements, and follow-on contracts | No rating activation |
| After kickoff | Measurement/adjustment implementation contract and simple point-in-time rating baseline | Isolated research artifacts only |
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

## Research rules

R1 reconstructs history only under new successor-v2 identities. It must certify
completed-game play coverage, score reconciliation, schemas, and zero 2020
lineage before R2 can begin. R2, R3, and R4 are sequential sealed tournaments:
each winning stage is locked before the next stage is evaluated. Football
measurements, admitted preseason football context, venue, and weather are
eligible inputs; bookmaker data is evaluation-only. 2025 is evaluated once as
the locked confirmation year. A failed gate publishes an immutable diagnostic,
not a relaxed candidate.

Candidate-v2 prospective evidence begins only after its committed identity is
frozen. It has a new six-slate counter and cannot inherit candidate-v1 evidence.
Authentic timestamped market evaluation follows football-model evaluation; a
calendar date cannot bypass a failed gate.

## Planning and execution protocol

- This roadmap controls sequencing; the active task-level authority is the
  historical-expansion plan linked below.
- The O2 candidate-v1 lane remains reproducible only from its pinned `ac1fba1`
  worktree and is never an input to candidate-v2 selection.
- No 2026 outcome is a development input. Missing a candidate-v2 prospective
  window is acceptable and never permits a retrospective freeze.

## Phase contract queue

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
  — **In Progress.** Governing R1–R4 research contract: 2015–2019 plus
  2021–2025, universal 2020 exclusion, staged methodology tournament, and a
  future candidate-v2 evidence lane.

## Invariants and open decisions

All work preserves immutable lineage, strict point-in-time provenance, temporal
validation, 2020 exclusion, market separation, sealed/frozen evaluation,
research-production isolation, and fail-closed operations.

The exact baseline estimator, rating scale, prior model, uncertainty mechanism,
and artifact schema are selected in their phase contracts. Special-teams
treatment, rating-assisted adjustment, and residual ML remain deferred
challenger decisions.
