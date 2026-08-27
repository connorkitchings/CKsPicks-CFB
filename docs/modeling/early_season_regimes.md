# 2026 V4 Early-Season Regime Contract

> **Status:** Live 2026 production benchmark. The rating-centric successor is
> research-only until a separately approved promotion succeeds.

V4 predicts spread and total independently for five completed-game routes:
`game_1`, `game_2`, `game_3`, `game_4`, and `established` (four or more
completed games). A matchup uses the route of its least-experienced team while
each team retains its own completed-game count and shrinkage weight.

The live bundle is `week0-2026-v4-strict-20260818-r2`, selected on sealed
2022–2024 temporal out-of-fold evaluation, checked once on locked 2025, and
refit unchanged on 2021–2025. It is the production champion and the comparison
baseline for every rating candidate.

## V4 safeguards

- All feature evidence must be reproducible before kickoff.
- Market prices never enter model features or route selection.
- V4 excludes 2020 and retains its sealed 2021–2025 lineage. Successor-v2
  research separately uses 2015–2019 and 2021–2025; it cannot alter V4.
- Immutable artifact lineage, temporal validation, fail-closed publication, and
  frozen-run rollback remain mandatory.

## Continuous successor direction

Hard route switches solve V4’s sparse-evidence problem safely, but team quality
is still implicit in features, priors, shrinkage, and route-specific models.
The approved successor retains these safeguards while allowing credibility—not
the governing methodology—to change smoothly through the season:

- preseason priors dominate before a team has observed evidence;
- early observed performance enters with strong shrinkage;
- opponent-adjusted performance gains weight as exposure grows; and
- uncertainty contracts only as credible evidence accumulates.

The successor consumes measurement-level opponent-adjusted football evidence
and emits offense, defense, overall quality, and uncertainty-bearing team state.
Any design that also re-estimates schedule strength must explicitly replace, not
duplicate, upstream adjustment. Details are in the
[rating-system requirements](rating_system_requirements.md).

## Isolation rule

Rating research may create immutable shadow artifacts only. It may not modify
V4 bundles, Neon activation, public publication, or rollback authority. A first
promotion review is possible only after six frozen full-slate shadow evaluations
under the [evaluation policy](evaluation.md).
