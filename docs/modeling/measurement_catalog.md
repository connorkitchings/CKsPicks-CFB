# Measurement Catalog

> **Status:** Initial catalog for the approved 2026 rating transition. It does
> not change V4 feature inputs.

This catalog organizes observed football performance before it becomes team
state. Current V4 uses a strict, point-in-time feature reference; the future
rating baseline will select from the same lineage under a separate contract.

## Responsibility boundary

```text
observed football performance → measurement-level opponent adjustment
→ rating/state → game prediction
```

A measurement describes performance. Adjustment evaluates performance against
opponent and context. Ratings accumulate adjusted evidence. Prediction compares
two states plus legitimate game context. Market data is excluded until the
market-decision stage.

## Families

| Family | Football interpretation | Primary exposure | Adjustment posture | Rating role |
| --- | --- | --- | --- | --- |
| Efficiency | Down-to-down ability to create or prevent value and stay on schedule | Plays | Eligible before rating | Core offense/defense evidence |
| Explosiveness | Frequency and magnitude of high-value plays | Plays and opportunities | Eligible, with sparse-event shrinkage | Separate from efficiency to avoid proxy duplication |
| Drives and finishing | Possession conversion, field-goal range, and points per scoring opportunity | Drives and scoring opportunities | Eligible with opportunity basis recorded | Supplements efficiency with possession outcomes |
| Field position | Starting field position, hidden-yardage context, and opponent starting position | Drives | Contextual; avoid crediting offense or defense twice | Context and possible special-teams attribution |
| Pace | Plays, drives, and possession tempo | Game time, plays, drives | Usually prediction context, not team-quality duplicate | Total/score translation input |
| Turnovers and luck | Volatile fumbles, interceptions, recoveries, and outcome residuals | Plays, drives, events | Separate signal with strong shrinkage | Reliability/context, not raw quality reward |
| Special teams | Kicking, punting, returns, and field-position contribution | Attempts and returns | Include only when reliable coverage exists | Deferred component or explicit context |

## Required provenance for every selected measurement

- Source dataset and immutable version/checksum.
- Team-side, game, season, and effective-before-kickoff identifiers.
- Numerator, denominator, and exposure basis.
- Missingness, coverage, and reconciliation behavior.
- Whether opponent adjustment is permitted, plus context already accounted for.
- Transform, shrinkage, and aggregation lineage.
- Known overlap with another measure and the rationale for retaining it.

## Baseline adjustment and redundancy policy

The baseline performs opponent adjustment before rating estimation. A candidate
may not silently adjust schedule strength again in the rating layer. Any
rating-assisted adjustment must name which upstream transformation it replaces,
the incremental evidence it uses, and how double-counting is prevented.

Measurements are evaluated within and across families for correlated exposure,
shared numerator/denominator, and predictive redundancy. The initial rating
baseline favors a small interpretable set over a wide feature matrix.

## Current source position

Canonical Bronze/Silver/Gold datasets and point-in-time assembly are the source
of truth. CFBD, timestamped market quotes, and weather are ingested under the
[data platform](../architecture/data_platform_2026.md) and
[ingestion guide](../data/ingestion_guide.md). Historical raw and transformed
schema snapshots are retained in the [archive](../archive.md); they are
not current schema authority.
