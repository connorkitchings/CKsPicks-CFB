# 2026 Season and Rating-Centric Transition Roadmap

> **Last updated:** 2026-08-23
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

The successor may be promoted during 2026 only through the evidence gate below.
It is not implemented or activation-eligible today. See the
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

## Transition milestones

| Window | Deliverable | Promotion status |
| --- | --- | --- |
| By 2026-08-28 | Documentation audit, measurement catalog, initial rating requirements, uncertainty and shadow-evaluation requirements, and follow-on contracts | No rating activation |
| After kickoff | Measurement/adjustment implementation contract and simple point-in-time rating baseline | Isolated research artifacts only |
| Subsequent weeks | Structured rating-to-game prediction, then frozen candidate shadow scoring | No Neon activation or publication |
| Six completed full slates | First promotion review, if every candidate prediction was frozen before kickoff | Separate approval required |
| Any later point in 2026 | Operational rehearsal, rollback proof, and evidence-based promotion decision | V4 remains fallback |

Week 0 does not count as a full slate. A full slate has normal schedule coverage
and both V4 and candidate predictions frozen before its first kickoff.

## Transition phases

### 0. Preserve production

Do not change V4 weights, routes, bundles, publication policy, weekly workflow,
or rollback behavior as part of rating research. V4 is the production benchmark
for every challenger.

### 1. Requirements before Week 0

Complete the as-built responsibility audit and publish measurement, provenance,
opponent-adjustment, state, uncertainty, prediction, and shadow-isolation
requirements. The estimator, scale, priors, and artifact schema stay open.

### 2. Measurement and adjustment contracts

Formalize selected measurement families, coverage, exposure, redundancy, and
point-in-time behavior. The baseline applies schedule adjustment at the
measurement layer. Rating-assisted adjustment is a separately attributable
future challenger.

### 3. Minimum viable rating baseline

Under a new implementation contract, produce offense, defense, overall, and
uncertainty-bearing state snapshots before each game. Translate those states
into margin and total predictions without residual ML. Emit immutable shadow
artifacts only.

### 4. Candidate research

Compare regularized, empirical-Bayes, hierarchical, state-space, and related
candidates only against the same temporal lineage and V4 baseline. Preseason
priors, special teams, uncertainty, and residual ML are independently
attributable decisions.

### 5. Protected prospective evidence and promotion

2021–2025 supports historical temporal development; it is not a new untouched
test set for this architecture. Each 2026 candidate must freeze its identity,
lineage, configuration, cutoff, and predictions before eligible outcomes are
observed. After six full shadow slates, promotion requires a separate approved
contract and evidence of rating quality, prediction quality, calibration,
operational readiness, rollback, and no material regression versus V4.

Authentic timestamped market evaluation follows football-model evaluation. A
failed gate cannot be bypassed for schedule reasons.

## Invariants and open decisions

All work preserves immutable lineage, strict point-in-time provenance, temporal
validation, 2020 exclusion, market separation, sealed/frozen evaluation,
research-production isolation, and fail-closed operations.

The final estimator, rating scale, prior model, uncertainty mechanism,
special-teams treatment, residual model, and artifact schema are intentionally
deferred to later approved contracts.
