"""``season_level_features_v1``: terminal season aggregates under explicit populations.

Aggregation reuses ``aggregate_through_week`` (summed numerators and denominators, missing
games withhold the aggregate). The two populations are never unified:

* ``website``: regular-season FBS-vs-FBS games, as the public team-stat pages.
* ``v5``: the accepted repair population, i.e. games with a valid outcome and usable
  measurements, including FBS-vs-FCS and postseason games.
"""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.metrics.builders import aggregate_through_week

POPULATIONS = ("website", "v5")
OUTPUT_COLUMNS = (
    "season",
    "team",
    "role",
    "metric",
    "population",
    "games",
    "games_missing",
    "numerator",
    "denominator",
    "value",
    "coverage_status",
    "missing_reason",
    "as_of_week",
)


def population_game_ids(games: pd.DataFrame, population: str) -> set[tuple[int, int]]:
    """Game keys in one population; ``games`` carries the flags used to define it."""
    if population == "website":
        mask = (
            (games["season_type"].astype(str).str.casefold() == "regular")
            & games["home_fbs"].astype(bool)
            & games["away_fbs"].astype(bool)
        )
    elif population == "v5":
        mask = games["forecast_eligible"].astype(bool) & games[
            "measurement_usable"
        ].astype(bool)
    else:
        raise ValueError(f"unknown population {population}")
    keys = games.loc[mask, ["season", "game_id"]]
    return {(int(s), int(g)) for s, g in keys.itertuples(index=False, name=None)}


def season_features(metrics: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for population in POPULATIONS:
        keys = population_game_ids(games, population)
        member = pd.Series(
            [
                (int(s), int(g)) in keys
                for s, g in zip(metrics["season"], metrics["game_id"])
            ],
            index=metrics.index,
        )
        subset = metrics[member]
        if subset.empty:
            continue
        aggregated = aggregate_through_week(
            subset, as_of_week=int(subset["week"].max()) + 1
        )
        aggregated["population"] = population
        frames.append(aggregated)
    result = pd.concat(frames, ignore_index=True)
    return (
        result[list(OUTPUT_COLUMNS)]
        .sort_values(["season", "team", "role", "metric", "population"])
        .reset_index(drop=True)
    )
