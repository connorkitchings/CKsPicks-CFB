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

## Approved Phase 1 baseline (v2 remediation in progress)

The original Phase 1 implementation is preserved as immutable research history,
but its review found lineage, season-boundary, weighting, and timing defects.
The corrected v2 interface is in progress and does not alter V4 inputs:

| Measurement | Roles | Adjustment posture | Phase 2 role |
| --- | --- | --- | --- |
| `epa_per_play` | Offense, defense | Iterative additive | Core candidate evidence |
| `success_rate` | Offense, defense | Iterative additive | Diagnostic challenger to EPA/play |
| `explosive_rate_20` | Offense, defense | Iterative additive | Core candidate evidence |
| `points_per_scoring_opportunity` | Offense, defense | Iterative additive | Core candidate evidence |
| `average_start_field_position` | Offense, defense | None | Context only |
| `plays_per_drive` | Offense | None | Pace context only |
| `turnover_rate` | Offense, defense | None | Reliability context only |

Eligible plays are exactly canonical byplay rows with `is_drive_play == 1` and
`garbage == 0`; missing either flag fails coverage. Eligible drives contain at
least one eligible play. Values with zero exposure stay null with a recorded
reason rather than receiving a substituted denominator.

Two exposure-basis details are binding for Phase 2:

- `success_rate` divides successful plays by eligible plays with computable
  success. About 2% of eligible plays (dead-ball markers such as End of
  Half/Game and a small number of return/completion rows) carry null success;
  these are excluded from both numerator and denominator and flagged in
  `quality_flags` (`success_missing_on_eligible_plays`, 3,551 of 3,731
  historical games).
- `explosive_rate_20` counts eligible plays gaining at least 20 yards
  (`yards_gained >= 20`), not the play-type-threshold `explosive` flag.

The baseline uses four fixed, league-centered additive adjustment iterations
for adjustment-eligible measures, retaining iteration zero and four for audit.
Historical 2021–2025 reconstruction supports development only; protected 2026
evidence requires authentic source timing before kickoff.

### Phase 1 audit disposition

The v1 observation version `b1da5e85a0438fab109937bf`, snapshot version
`312917237b7b60cb10d61150`, and audit report are superseded for Phase 2
consumption. They remain immutable history. Phase 2 may consume only the
replacement v2 observation, season-to-date snapshot, terminal snapshot, and
passing audit produced under
`docs/plans/2026-08-24/phase1-rating-measurement-remediation.md`.

Built 2026-08-24 in Preview from the canonical history lineage (byplay/drives
lake versions matched to each season's `reconciled_team_game` parent set;
`games-2021-2026`, `game_outcomes-2021-2025` + `game_outcomes-2026`,
`reconciled_team_game-2021-2025` refs):

- Measurement design ID (`sha256` of `conf/ratings/measurement_baseline_v1.yaml`):
  `5c4d5cc4d6a46d4b3d830b50607f7fa0f8984cc63ab6ee64b6a7e626b415f95f`.
- Observations `rating_measurement_observations_v1`: version
  `b1da5e85a0438fab109937bf`, content SHA-256
  `71775752723acecf1f410b9ce438ae65674f497953e58fb6f724d639aec1581c` —
  96,954 rows, all reconstructed 2021–2025 development evidence.
- Snapshots `rating_adjusted_measurement_snapshots_v1`: version
  `312917237b7b60cb10d61150`, content SHA-256
  `ed1a549d93833ca58007b1ae022c51a2627a456843437bd88197503cc6b3b454` —
  116,792 pregame rows covering 2021–2026 scheduled games (2026 rows use
  2025 reconstructed evidence only).
- Audit report SHA-256
  `05fe64f101773aff2f6ad46c40e9afaceb516e633d89ac226ab9a2bdc5a542de` at
  `artifacts/research/rating-successor/measurements/{design_id}/runs/2026-08-24T1830Z/audit-report.json`.

Coverage: every adjustment-eligible and context measurement observed for all
14,916 two-role team-games (7,458 offense-only `plays_per_drive` rows); only
`points_per_scoring_opportunity` has 158 zero-exposure missing rows
(opportunity-less defensive/offensive performances). Snapshot missingness is
confined to 2,062 first-game team-measurement states with no prior evidence.
Redundancy (Spearman vs `epa_per_play`, 2025 pregame, n=1,522):
success rate 0.92–0.94, explosive rate 0.78–0.79, points per opportunity
0.72–0.74 — success rate remains the designated diagnostic challenger. All
uniqueness, two-team symmetry, source reconciliation, 2020/2019 exclusion,
future-row, no-double-counting, and market-free checks pass. The builder is
byte-idempotent on identical parents and configuration.

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

Phase 2 may consume only the final corrected Phase 1 audit's named immutable refs and
checksums. It cannot promote contextual measures, add special teams, or apply a
second schedule-strength adjustment without a separate approved contract.

## Current source position

Canonical Bronze/Silver/Gold datasets and point-in-time assembly are the source
of truth. CFBD, timestamped market quotes, and weather are ingested under the
[data platform](../architecture/data_platform_2026.md) and
[ingestion guide](../data/ingestion_guide.md). Historical raw and transformed
schema snapshots are retained in the [archive](../archive.md); they are
not current schema authority.
