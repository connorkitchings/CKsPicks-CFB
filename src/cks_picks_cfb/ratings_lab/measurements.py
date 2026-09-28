"""Versioned measurement recipes over the pinned, game-level corpus."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from .contracts import Game, Observation, Rating, utc
from .corpus import Corpus


@dataclass(frozen=True)
class MeasurementRecipe:
    recipe_id: str = "v5_raw_ppp_game_v1"
    measurement_id: str = "ppp"
    availability_policy: str = "v5_later_week_6h_v1"

    def __post_init__(self) -> None:
        if self.availability_policy != "v5_later_week_6h_v1":
            raise ValueError("unregistered measurement availability policy")


def build_individual(
    corpus: Corpus, recipe: MeasurementRecipe = MeasurementRecipe()
) -> list[Observation]:
    if recipe.measurement_id != "ppp" or recipe.recipe_id != "v5_raw_ppp_game_v1":
        raise ValueError("unknown measurement recipe")
    observations = corpus.individual_observations(recipe.measurement_id)
    games = {(g.season, g.game_id): g for g in corpus.games()}
    for obs in observations:
        game = games.get((obs.season, obs.game_id))
        if game is None or obs.team not in (game.home_team, game.away_team):
            raise ValueError("measurement escapes pinned population")
        if utc(obs.available_utc) != utc(game.kickoff_utc) + timedelta(hours=6):
            raise ValueError("measurement availability policy changed")
    return observations


def build_cumulative(
    games: list[Game], individual: list[Observation]
) -> list[Observation]:
    """Each snapshot replaces all prior evidence; its contributor IDs are explicit."""
    by_team: dict[tuple[int, str, str, str], list[Observation]] = defaultdict(list)
    for obs in individual:
        if obs.kind != "individual":
            raise ValueError("cumulative recipe requires individual observations")
        by_team[(obs.season, obs.team, obs.role, obs.measurement_id)].append(obs)
    output: list[Observation] = []
    for (season, team, role, measurement_id), rows in sorted(by_team.items()):
        ordered = sorted(rows, key=lambda row: (utc(row.available_utc), row.game_id))
        accepted: list[Observation] = []
        for row in ordered:
            if row.value is not None and row.exposure > 0:
                accepted.append(row)
            if not accepted:
                continue
            exposure = sum(item.exposure for item in accepted)
            output.append(
                Observation(
                    season,
                    row.week,
                    row.game_id,
                    team,
                    role,
                    measurement_id,
                    sum(
                        item.value * item.exposure
                        for item in accepted
                        if item.value is not None
                    )
                    / exposure,
                    exposure,
                    row.available_utc,
                    row.timing_class,
                    kind="cumulative",
                    contributors=tuple(item.game_id for item in accepted),
                )
            )
    population = {(g.season, g.game_id) for g in games}
    if any((row.season, row.game_id) not in population for row in output):
        raise ValueError("cumulative snapshot lacks source game")
    return output


def terminal_standardized_seeds(
    individual: list[Observation],
) -> dict[tuple[int, str, str], Rating]:
    """A previous season's complete measured PPP supplies the carryover reference."""
    grouped: dict[tuple[int, str, str], list[Observation]] = defaultdict(list)
    for row in individual:
        if row.value is not None and row.exposure > 0:
            grouped[(row.season, row.team, row.role)].append(row)
    by_role_season: dict[tuple[int, str], dict[str, float]] = defaultdict(dict)
    for (season, team, role), rows in grouped.items():
        exposure = sum(row.exposure for row in rows)
        by_role_season[(season, role)][team] = (
            sum(row.value * row.exposure for row in rows if row.value is not None)
            / exposure
        )
    seeds: dict[tuple[int, str, str], Rating] = {}
    for (season, role), team_values in by_role_season.items():
        values = np.array(list(team_values.values()), dtype=float)
        center, scale = float(values.mean()), max(float(values.std()), 1e-6)
        for team, value in team_values.items():
            seeds[(season, team, role)] = Rating((value - center) / scale, 1.0)
    return seeds


def observation_frame(observations: list[Observation]) -> pd.DataFrame:
    from dataclasses import asdict

    return pd.DataFrame.from_records([asdict(value) for value in observations])
