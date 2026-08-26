# 2026 Season and Rating-Centric Transition Roadmap

> **Last updated:** 2026-08-24
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
for every challenger. Rating work has no path to Neon activation, public
publication, or production rollback selection before a separate promotion
contract is approved.

### 1. Measurement and opponent-adjustment foundation

Audit the actual 2021–2026 Gold fields and formalize a deliberately small,
versioned team-game measurement interface. Every selected measurement carries
its exposure, effective-time status, immutable source lineage, missingness, and
quality flags. The baseline performs schedule adjustment once at the
measurement layer and records which contexts are already represented.

The phase exits only when adjusted measurements are reproducible and pass
coverage, redundancy, point-in-time, and schedule-strength double-counting
checks. No rating estimator is introduced before this gate.

**Current disposition:** The initial implementation is retained as immutable
research history but is under corrective v2 remediation before it can satisfy
this gate. See `docs/plans/2026-08-24/phase1-rating-measurement-remediation.md`.

### 2. Minimum viable team-state baseline

Select the simplest viable estimator under a dedicated implementation contract.
Produce pregame offense, defense, overall-quality, and uncertainty-bearing team
states whose meaning remains stable throughout the season. Preseason priors
lose influence smoothly as credible exposure accumulates. Historical state
snapshots retain exact input, configuration, code, and cutoff lineage.

### 3. Structured margin and total prediction

Map two frozen team states plus legitimate venue and game context directly to
expected margin and total, with non-null predictive uncertainty for both. The
first baseline excludes residual ML and market inputs. Historical expanding
temporal evaluation compares the candidate to V4 on identical games, and all
prospective gates are registered before the candidate identity freezes.

### 4. Isolated shadow operations

Add a research-only weekly workflow that builds states, generates predictions,
validates schedule coverage, and freezes immutable artifacts before kickoff.
Postgame scoring pairs candidate and V4 outputs for the same games and cutoff.
Missing data, partial coverage, duplicates, late execution, or checksum failure
must fail closed. Week 1 is the first target only if Phases 1–4 pass without
weakening a gate.

### 5. Protected prospective evidence

2021–2025 supports historical temporal development; it is not a new untouched
test set for this architecture. Each 2026 candidate must freeze its identity,
lineage, configuration, cutoff, and predictions before eligible outcomes are
observed. Run the unchanged baseline through normal-coverage slates and evaluate
rating behavior, prediction quality, uncertainty calibration, and only then
authentic timestamped market value. Week 0 does not count.

### 6. Attributable challenger research

After the simple baseline freezes, investigate estimator families, priors,
special teams, alternative uncertainty methods, rating-assisted adjustment,
and optional residual ML as separately attributable changes. Every revision
receives a new candidate identity and later untouched prospective window; it
cannot alter the baseline evidence lane.

### 7. Promotion review and operationalization

After one unchanged candidate accumulates six eligible full slates, a separate
approved contract may review paired V4 results, calibration, reproducibility,
operational rehearsal, fail-closed behavior, and rollback proof. Promotion is
never automatic, and V4 remains the fallback.

Authentic timestamped market evaluation follows football-model evaluation. A
failed gate cannot be bypassed for schedule reasons.

## Planning and execution protocol

- This roadmap controls sequencing; it does not authorize implementation of all
  phases as one change.
- Each phase receives a decision-complete Sol contract and a fresh Terra
  implementation task. A phase cannot begin implementation before its prior
  exit gate is satisfied or an approved amendment explicitly changes the order.
- The initial baseline is deliberately end-to-end and simple. Richer research
  begins only after the first candidate identity is frozen so prospective
  evidence is not delayed or contaminated.
- Week 1 is a conditional target. Production Week 0 operations and evidence
  integrity take precedence over the date.

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
  — In Progress. Phase 1 v3 is certified. Phase 2 v2 uses representative
  normal-coverage location gates before refreshed foundation certification and
  a sealed v3 tournament; Phase 4 remains blocked.

## Invariants and open decisions

All work preserves immutable lineage, strict point-in-time provenance, temporal
validation, 2020 exclusion, market separation, sealed/frozen evaluation,
research-production isolation, and fail-closed operations.

The exact baseline estimator, rating scale, prior model, uncertainty mechanism,
and artifact schema are selected in their phase contracts. Special-teams
treatment, rating-assisted adjustment, and residual ML remain deferred
challenger decisions.
