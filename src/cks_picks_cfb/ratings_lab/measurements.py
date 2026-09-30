"""Versioned measurement recipes over the pinned, game-level corpus."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from .contracts import Game, Observation, Rating, utc
from .corpus import Corpus

_REGISTERED_AVAILABILITY_POLICIES: set[str] = {"v5_later_week_6h_v1"}


def register_availability_policy(policy_id: str) -> None:
    _REGISTERED_AVAILABILITY_POLICIES.add(policy_id)


@dataclass(frozen=True)
class MeasurementRecipe:
    recipe_id: str = "v5_raw_ppp_game_v1"
    measurement_id: str = "ppp"
    availability_policy: str = "v5_later_week_6h_v1"
    description: str = ""

    def __post_init__(self) -> None:
        if self.availability_policy not in _REGISTERED_AVAILABILITY_POLICIES:
            raise ValueError("unregistered measurement availability policy")


def _build_ppp(corpus: Corpus, recipe: MeasurementRecipe) -> list[Observation]:
    if recipe.measurement_id != "ppp":
        raise ValueError(
            f"recipe {recipe.recipe_id!r} expects measurement_id='ppp', got {recipe.measurement_id!r}"
        )
    observations = corpus.individual_observations(recipe.measurement_id)
    games = {(g.season, g.game_id): g for g in corpus.games()}
    for obs in observations:
        game = games.get((obs.season, obs.game_id))
        if game is None or obs.team not in (game.home_team, game.away_team):
            raise ValueError("measurement escapes pinned population")
        if utc(obs.available_utc) != utc(game.kickoff_utc) + timedelta(hours=6):
            raise ValueError("measurement availability policy changed")
    return observations


_FOUR_FACTORS: tuple[str, ...] = (
    "rush_success_rate",
    "rush_explosiveness",
    "pass_success_rate",
    "pass_explosiveness",
    "rush_explosiveness_margin",
    "pass_explosiveness_margin",
)

_DEAD_MARKERS: tuple[str, ...] = (
    "spike",
    "kneel",
    "end period",
    "end of half",
    "end of game",
    "timeout",
    "placeholder",
    "uncategorized",
)


def _build_4factor(corpus: Corpus, recipe: MeasurementRecipe) -> list[Observation]:
    from cks_picks_cfb.preseason_features import canonical_team

    byplay = corpus.read_byplay()
    if byplay.empty:
        raise ValueError(
            "byplay dataframe is empty; cannot compute 4-factor measurements"
        )

    required_cols = {
        "season",
        "game_id",
        "quarter",
        "down",
        "offense",
        "defense",
        "play_type",
        "rush_attempt",
        "dropback",
        "yards_gained",
        "distance",
        "yards_to_goal",
    }
    missing = sorted(required_cols - set(byplay.columns))
    if missing:
        raise ValueError(f"byplay frame missing required columns: {missing}")

    target_ids = set(_FOUR_FACTORS)
    if recipe.measurement_id not in {"4factor", "all"}:
        norm = {
            "rush_sr": "rush_success_rate",
            "rush_expl": "rush_explosiveness",
            "pass_sr": "pass_success_rate",
            "pass_expl": "pass_explosiveness",
        }.get(recipe.measurement_id, recipe.measurement_id)
        if norm in target_ids:
            target_ids = {norm}

    games_by_id = {(g.season, g.game_id): g for g in corpus.games()}
    observations: list[Observation] = []

    df = byplay.copy()
    for col in ("season", "game_id", "quarter", "down"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in (
        "st",
        "penalty",
        "twopoint",
        "garbage",
        "rush_attempt",
        "dropback",
        "yards_gained",
        "distance",
        "yards_to_goal",
    ):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    is_regulation = df["quarter"].isin([1, 2, 3, 4])
    is_scrimmage = (df["st"] == 0) & (df["twopoint"] == 0) & (df["penalty"] == 0)
    is_non_garbage = df["garbage"] == 0
    play_type_str = df["play_type"].astype(str).str.casefold()
    is_live = ~play_type_str.str.contains("|".join(_DEAD_MARKERS), regex=True)

    eligible = df[is_regulation & is_scrimmage & is_non_garbage & is_live].copy()
    if eligible.empty:
        return []

    eligible["offense_canon"] = eligible["offense"].map(canonical_team)
    eligible["defense_canon"] = eligible["defense"].map(canonical_team)

    downs = eligible["down"].values
    ytfs = eligible["distance"].values
    ytgs = eligible["yards_to_goal"].values
    yards = eligible["yards_gained"].values

    neededs = np.where((ytfs <= 0) | ((ytgs > 0) & (ytfs >= ytgs)), ytgs, ytfs)

    # Fail-closed guard: down must be in 1..4 and needed yards must be strictly positive
    valid_down_dist = (downs >= 1) & (downs <= 4) & (neededs > 0)
    eligible = eligible[valid_down_dist].copy()
    if eligible.empty:
        return []

    downs = eligible["down"].values
    neededs = neededs[valid_down_dist]
    yards = eligible["yards_gained"].values

    thresholds = np.zeros(len(eligible), dtype=float)
    thresholds[downs == 1] = 0.50 * neededs[downs == 1]
    thresholds[downs == 2] = 0.70 * neededs[downs == 2]
    thresholds[(downs == 3) | (downs == 4)] = (
        1.00 * neededs[(downs == 3) | (downs == 4)]
    )

    successes = (yards >= thresholds).astype(int)
    margins = np.maximum(0.0, yards - thresholds)

    eligible["is_success"] = successes
    eligible["success_margin"] = margins

    is_rush = (eligible["rush_attempt"] == 1) & (eligible["dropback"] == 0)
    is_pass = (eligible["dropback"] == 1) & (eligible["rush_attempt"] == 0)
    eligible["is_rush"] = is_rush
    eligible["is_pass"] = is_pass

    for (season, game_id), game_plays in eligible.groupby(
        ["season", "game_id"], sort=False
    ):
        game = games_by_id.get((int(season), int(game_id)))
        if game is None:
            continue
        avail = (pd.Timestamp(game.kickoff_utc) + timedelta(hours=6)).isoformat()

        for team in (game.home_team, game.away_team):
            for role in ("offense", "defense"):
                team_col = "offense_canon" if role == "offense" else "defense_canon"
                unit_plays = game_plays[game_plays[team_col] == team]

                # Rush plays
                rush_plays = unit_plays[unit_plays["is_rush"]]
                n_rush = len(rush_plays)
                succ_rush = rush_plays[rush_plays["is_success"] == 1]
                n_succ_rush = len(succ_rush)

                if "rush_success_rate" in target_ids:
                    if n_rush > 0:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "rush_success_rate",
                                float(n_succ_rush / n_rush),
                                float(n_rush),
                                avail,
                                "historically_reconstructed",
                            )
                        )
                    else:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "rush_success_rate",
                                None,
                                0.0,
                                avail,
                                "historically_reconstructed",
                                missing_reason="no_rush_attempts",
                            )
                        )

                if "rush_explosiveness" in target_ids:
                    if n_succ_rush > 0:
                        val = float(succ_rush["yards_gained"].sum() / n_succ_rush)
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "rush_explosiveness",
                                val,
                                float(n_succ_rush),
                                avail,
                                "historically_reconstructed",
                            )
                        )
                    else:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "rush_explosiveness",
                                None,
                                0.0,
                                avail,
                                "historically_reconstructed",
                                missing_reason="no_successful_plays",
                            )
                        )

                if "rush_explosiveness_margin" in target_ids:
                    if n_succ_rush > 0:
                        val = float(succ_rush["success_margin"].sum() / n_succ_rush)
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "rush_explosiveness_margin",
                                val,
                                float(n_succ_rush),
                                avail,
                                "historically_reconstructed",
                            )
                        )
                    else:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "rush_explosiveness_margin",
                                None,
                                0.0,
                                avail,
                                "historically_reconstructed",
                                missing_reason="no_successful_plays",
                            )
                        )

                # Pass plays
                pass_plays = unit_plays[unit_plays["is_pass"]]
                n_pass = len(pass_plays)
                succ_pass = pass_plays[pass_plays["is_success"] == 1]
                n_succ_pass = len(succ_pass)

                if "pass_success_rate" in target_ids:
                    if n_pass > 0:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "pass_success_rate",
                                float(n_succ_pass / n_pass),
                                float(n_pass),
                                avail,
                                "historically_reconstructed",
                            )
                        )
                    else:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "pass_success_rate",
                                None,
                                0.0,
                                avail,
                                "historically_reconstructed",
                                missing_reason="no_pass_attempts",
                            )
                        )

                if "pass_explosiveness" in target_ids:
                    if n_succ_pass > 0:
                        val = float(succ_pass["yards_gained"].sum() / n_succ_pass)
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "pass_explosiveness",
                                val,
                                float(n_succ_pass),
                                avail,
                                "historically_reconstructed",
                            )
                        )
                    else:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "pass_explosiveness",
                                None,
                                0.0,
                                avail,
                                "historically_reconstructed",
                                missing_reason="no_successful_plays",
                            )
                        )

                if "pass_explosiveness_margin" in target_ids:
                    if n_succ_pass > 0:
                        val = float(succ_pass["success_margin"].sum() / n_succ_pass)
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "pass_explosiveness_margin",
                                val,
                                float(n_succ_pass),
                                avail,
                                "historically_reconstructed",
                            )
                        )
                    else:
                        observations.append(
                            Observation(
                                int(season),
                                game.week,
                                int(game_id),
                                team,
                                role,
                                "pass_explosiveness_margin",
                                None,
                                0.0,
                                avail,
                                "historically_reconstructed",
                                missing_reason="no_successful_plays",
                            )
                        )

    return observations


RecipeBuilder = Callable[[Corpus, MeasurementRecipe], list[Observation]]

_RECIPE_BUILDERS: dict[str, RecipeBuilder] = {
    "v5_raw_ppp_game_v1": _build_ppp,
    "v6_4factor_game_v1": _build_4factor,
}


def register_recipe(recipe_id: str, builder: RecipeBuilder) -> None:
    if recipe_id in _RECIPE_BUILDERS:
        raise ValueError(f"recipe {recipe_id!r} is already registered")
    _RECIPE_BUILDERS[recipe_id] = builder


def build_individual(
    corpus: Corpus, recipe: MeasurementRecipe = MeasurementRecipe()
) -> list[Observation]:
    builder = _RECIPE_BUILDERS.get(recipe.recipe_id)
    if builder is None:
        raise ValueError(f"unregistered measurement recipe: {recipe.recipe_id!r}")
    return builder(corpus, recipe)


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
    measurement_id: str | None = None,
    *,
    signed_defense: bool = True,
) -> dict[Any, Rating]:
    """A previous season's complete measured performance supplies the carryover reference.

    When signed_defense is True, defensive observation values are negated before
    standardization so that higher standardized ratings consistently represent
    better performance for both offense and defense.
    """
    from .priors import compute_terminal_seeds

    return compute_terminal_seeds(
        individual,
        measurement_id=measurement_id,
        signed_defense=signed_defense,
    )


def observation_frame(observations: list[Observation]) -> pd.DataFrame:
    from dataclasses import asdict

    return pd.DataFrame.from_records([asdict(value) for value in observations])
