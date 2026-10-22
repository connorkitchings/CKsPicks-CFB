# Experiment and Model Lineage

## Live champion

The live 2026 champion is V4:
`week0-2026-v4-strict-20260818-r2`. It was selected by sealed 2022–2024 temporal
out-of-fold comparison, checked once against locked 2025, and refit unchanged
on 2021–2025. See the [V4 regime contract](../modeling/early_season_regimes.md).

Historical market exports are quarantined and cannot affect selection, refit,
or promotion.

| Lineage | Role | Status |
| --- | --- | --- |
| V2 preview | Early display fallback | Historical |
| V3 games-ordinal | Rehearsal and V4 baseline lineage | Historical |
| V4 strict | Production champion and rollback-safe benchmark | Live |
| Rating baseline | Future point-in-time research/shadow candidate | Not implemented |

## Rating-transition experiment policy

Rating candidates use the [rating-system requirements](../modeling/rating_system_requirements.md)
and [evaluation policy](../modeling/evaluation.md). They must preserve the same
immutable lineage and point-in-time cutoffs as V4 comparisons, freeze before
eligible 2026 outcomes, and remain outside public publication.

After six full frozen shadow slates, a separate approved promotion contract may
evaluate a candidate. Residual ML is tested only as an incremental layer over a
structured rating prediction.

V2 experiment details are retained in the [archive](../archive.md).

## Market-line retention

Canonical timestamped market quotes (2026 onward) persist to R2 Silver and Neon
`market_quotes`/`market_snapshot_quotes` atomically with every publish
(`docs/plans/2026-09-03/market-line-retention.md`). An opt-in live The Odds API
capture (`CFB_ODDS_API_ENABLED=1` + `THE_ODDS_API_KEY`) adds per-book quotes and
degrades softly to CFBD-only on provider failure. A budget-gated exploration of
recovering 2021–2025 timestamped lines via The Odds API historical endpoint
lives in [odds-api-historical-backfill-2026.md](odds-api-historical-backfill-2026.md).
