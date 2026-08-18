"""Canonical, reproducible point-in-time matchup feature snapshots."""

from __future__ import annotations

import json
from collections.abc import Mapping

import pandas as pd

from cks_picks_cfb.features.v2_recency import (
    aggregate_team_season_ewma,
    completed_game_regime,
    upcoming_game_regime,
)

IDENTITY_COLUMNS = {
    "id",
    "game_id",
    "season",
    "week",
    "start_date",
    "home_team",
    "away_team",
}
FORBIDDEN_FEATURE_TOKENS = ("spread_line", "total_line", "moneyline", "bookmaker")


def build_temporal_matchup_inputs(
    schedule: pd.DataFrame,
    team_game: pd.DataFrame,
    *,
    prior_2019: pd.DataFrame,
    outcomes: pd.DataFrame | None = None,
    inference_seasons: frozenset[int] = frozenset(),
    alpha: float = 0.5,
) -> pd.DataFrame:
    """Build deterministic pre-kickoff current/prior matchup feature blocks."""
    games = schedule.copy().rename(columns={"kickoff_utc": "start_date"})
    required_games = {
        "season",
        "week",
        "game_id",
        "start_date",
        "home_team",
        "away_team",
    }
    if missing := sorted(required_games - set(games.columns)):
        raise ValueError(f"Schedule is missing temporal matchup fields: {missing}")
    games["start_date"] = pd.to_datetime(games["start_date"], utc=True, errors="raise")
    if 2020 in set(games["season"].astype(int)):
        raise ValueError("2020 is excluded from temporal matchup inputs")
    if outcomes is not None:
        outcome_required = {
            "season",
            "game_id",
            "completed",
            "home_points",
            "away_points",
        }
        if missing := sorted(outcome_required - set(outcomes.columns)):
            raise ValueError(f"Outcomes are missing temporal fields: {missing}")
        outcome_values = outcomes[list(outcome_required)].copy()
        if outcome_values.duplicated(["season", "game_id"]).any():
            raise ValueError("Outcomes contain duplicate season/game_id keys")
        games = games.drop(
            columns=[
                column
                for column in outcome_required - {"season", "game_id"}
                if column in games
            ]
        ).merge(
            outcome_values,
            on=["season", "game_id"],
            how="left",
            validate="one_to_one",
        )
    if inference_seasons:
        historical = ~games["season"].astype(int).isin(inference_seasons)
        completed = games.get("completed", pd.Series(False, index=games.index))
        scores_present = games.get("home_points", pd.Series(index=games.index)).notna()
        scores_present &= games.get("away_points", pd.Series(index=games.index)).notna()
        games = games.loc[
            ~historical | (completed.eq(True).fillna(False) & scores_present)
        ].copy()
    sides = pd.concat(
        [
            games[
                ["season", "week", "game_id", "start_date", "home_team", "away_team"]
            ].rename(columns={"home_team": "team", "away_team": "opponent"}),
            games[
                ["season", "week", "game_id", "start_date", "home_team", "away_team"]
            ].rename(columns={"away_team": "team", "home_team": "opponent"}),
        ],
        ignore_index=True,
    )
    observations = team_game.copy().rename(columns={"kickoff_utc": "start_date"})
    metric_exclusions = {
        "season",
        "week",
        "game_id",
        "team",
        "opponent",
        "home_away",
        "start_date",
    }
    metric_columns = [
        column
        for column in observations.columns
        if column not in metric_exclusions
        and pd.api.types.is_numeric_dtype(observations[column])
    ]
    timeline = sides.merge(
        observations[["season", "game_id", "team", *metric_columns]],
        on=["season", "game_id", "team"],
        how="left",
        validate="one_to_one",
    )
    snapshots = aggregate_team_season_ewma(timeline, alpha=alpha)
    snapshots = sides.merge(
        snapshots,
        on=["season", "week", "game_id", "team"],
        how="left",
        validate="one_to_one",
    )

    prior_rows = []
    historical = observations[observations["season"].astype(int) != 2020]
    if metric_columns:
        prior_rows.append(
            historical.groupby(["season", "team"], as_index=False)[metric_columns]
            .mean(numeric_only=True)
            .rename(columns={"season": "prior_source_season"})
        )
    prior_2019 = prior_2019.copy()
    if not prior_2019.empty:
        if "season" in prior_2019:
            prior_2019 = prior_2019[prior_2019["season"].astype(int) == 2019]
        prior_2019["prior_source_season"] = 2019
        prior_rows.append(prior_2019)
    prior = pd.concat(prior_rows, ignore_index=True, sort=False)
    prior = prior.drop_duplicates(["prior_source_season", "team"], keep="last")
    snapshots["prior_source_season"] = snapshots["season"].astype(int).sub(1)
    snapshots.loc[snapshots["season"].astype(int) == 2021, "prior_source_season"] = 2019
    snapshots = snapshots.merge(
        prior,
        on=["prior_source_season", "team"],
        how="left",
        suffixes=("", "_prior"),
    )
    rows = []
    for game in games.sort_values(["season", "start_date", "game_id"]).to_dict(
        "records"
    ):
        row = dict(game)
        side_rows = snapshots[
            (snapshots["season"] == game["season"])
            & (snapshots["game_id"] == game["game_id"])
        ].set_index("team")
        for side, team, opponent in (
            ("home", game["home_team"], game["away_team"]),
            ("away", game["away_team"], game["home_team"]),
        ):
            if team not in side_rows.index:
                raise ValueError(
                    f"Missing temporal feature row for {team}/{game['game_id']}"
                )
            values = side_rows.loc[team]
            opponent_values = side_rows.loc[opponent]
            for metric in metric_columns:
                row[f"{side}_current_{metric}"] = values.get(metric)
                row[f"{side}_prior_{metric}"] = values.get(f"{metric}_prior")
                if metric.startswith("off_"):
                    counterpart = "def_" + metric.removeprefix("off_")
                    if counterpart in metric_columns:
                        row[f"{side}_current_adj_{metric}"] = values.get(
                            metric
                        ) - opponent_values.get(counterpart)
                elif metric.startswith("def_"):
                    counterpart = "off_" + metric.removeprefix("def_")
                    if counterpart in metric_columns:
                        row[f"{side}_current_adj_{metric}"] = values.get(
                            metric
                        ) - opponent_values.get(counterpart)
        rows.append(row)
    result = pd.DataFrame.from_records(rows)
    if {"home_points", "away_points"}.issubset(result.columns):
        result["spread_target"] = result["home_points"] - result["away_points"]
        result["total_target"] = result["home_points"] + result["away_points"]
    return result


def add_completed_game_routing(
    matchups: pd.DataFrame,
    schedule: pd.DataFrame,
    *,
    prior_source_overrides: Mapping[int, int] | None = None,
) -> pd.DataFrame:
    """Count completed games strictly before each kickoff and assign a regime."""
    required_matchups = {
        "season",
        "game_id",
        "start_date",
        "home_team",
        "away_team",
    }
    required_schedule = {
        "season",
        "game_id",
        "start_date",
        "home_team",
        "away_team",
        "completed",
    }
    if missing := sorted(required_matchups - set(matchups.columns)):
        raise ValueError(f"Matchups are missing routing columns: {missing}")
    if missing := sorted(required_schedule - set(schedule.columns)):
        raise ValueError(f"Schedule is missing routing columns: {missing}")
    result = matchups.copy()
    result["start_date"] = pd.to_datetime(
        result["start_date"], utc=True, errors="raise"
    )
    history = schedule.copy()
    history["start_date"] = pd.to_datetime(
        history["start_date"], utc=True, errors="raise"
    )
    history = history[history["completed"].fillna(False).astype(bool)]
    if "status" in history:
        history = history[
            ~history["status"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .isin({"cancelled", "canceled"})
        ]
    home_counts: list[int] = []
    away_counts: list[int] = []
    prior_sources: list[int] = []
    overrides = dict(prior_source_overrides or {2021: 2019})
    for row in result.itertuples(index=False):
        season = int(row.season)
        prior_source = overrides.get(season, season - 1)
        if season == 2020 or prior_source == 2020:
            raise ValueError("2020 data is excluded from point-in-time feature lineage")
        prior = history[
            (history["season"].astype(int) == season)
            & (history["start_date"] < row.start_date)
            & (history["game_id"] != row.game_id)
        ]
        home_counts.append(
            int(
                (
                    (prior["home_team"] == row.home_team)
                    | (prior["away_team"] == row.home_team)
                ).sum()
            )
        )
        away_counts.append(
            int(
                (
                    (prior["home_team"] == row.away_team)
                    | (prior["away_team"] == row.away_team)
                ).sum()
            )
        )
        prior_sources.append(prior_source)
    result["home_completed_games"] = home_counts
    result["away_completed_games"] = away_counts
    result["prior_source_season"] = prior_sources
    result["prior_season_gap"] = (
        result["season"].astype(int) - result["prior_source_season"]
    )
    minimum = result[["home_completed_games", "away_completed_games"]].min(axis=1)
    result["prediction_regime"] = minimum.map(upcoming_game_regime)
    if "feature_as_of" in result:
        feature_as_of = pd.to_datetime(
            result["feature_as_of"], utc=True, errors="raise"
        )
        if (feature_as_of > result["start_date"]).any():
            raise ValueError("Feature as_of timestamp follows kickoff")
    if {"home_points", "away_points"}.issubset(result.columns):
        result["spread_target"] = result["home_points"] - result["away_points"]
        result["total_target"] = result["home_points"] + result["away_points"]
    return result


def build_point_in_time_matchups(
    matchups: pd.DataFrame,
    *,
    season: int,
    as_of: str,
    provenance: Mapping[str, str],
    prior_source_overrides: Mapping[int, int] | None = None,
) -> pd.DataFrame:
    """Explode wide matchups into canonical team-keyed, pre-kickoff rows."""
    required = {"week", "home_team", "away_team"}
    if not required.issubset(matchups.columns) or not (
        {"id", "game_id"} & set(matchups.columns)
    ):
        raise ValueError("Matchups require game ID, week, home_team, and away_team")
    cutoff = (
        pd.Timestamp(as_of, tz="UTC")
        if pd.Timestamp(as_of).tzinfo is None
        else pd.Timestamp(as_of).tz_convert("UTC")
    )
    if "start_date" in matchups:
        starts = pd.to_datetime(matchups["start_date"], utc=True, errors="coerce")
        if starts.isna().any() or (starts < cutoff).any():
            raise ValueError(
                "Point-in-time cutoff must not follow any included kickoff"
            )

    game_col = "game_id" if "game_id" in matchups else "id"
    prior_sources = dict(prior_source_overrides or {2021: 2019})
    prior_source_season = prior_sources.get(season, season - 1)
    if season == 2020 or prior_source_season == 2020:
        raise ValueError("2020 data is excluded from point-in-time feature lineage")
    records: list[dict[str, object]] = []
    for _, matchup in matchups.iterrows():
        for side, opponent_side in (("home", "away"), ("away", "home")):
            prefix = f"{side}_"
            features = {
                column.removeprefix(prefix): matchup[column]
                for column in matchups.columns
                if column.startswith(prefix)
                and column not in {f"{side}_team"}
                and not any(
                    token in column.lower() for token in FORBIDDEN_FEATURE_TOKENS
                )
            }
            missing = sorted(name for name, value in features.items() if pd.isna(value))
            completed_games = int(
                pd.to_numeric(
                    matchup.get(f"{side}_current_season_games", 0),
                    errors="coerce",
                )
                if pd.notna(matchup.get(f"{side}_current_season_games", 0))
                else 0
            )
            records.append(
                {
                    "season": season,
                    "week": int(matchup["week"]),
                    "game_id": matchup[game_col],
                    "team": matchup[f"{side}_team"],
                    "opponent": matchup[f"{opponent_side}_team"],
                    "side": side,
                    "as_of": cutoff.isoformat(),
                    "completed_game_count": completed_games,
                    "team_regime": completed_game_regime(completed_games),
                    "prior_source_season": prior_source_season,
                    "prior_season_gap": season - prior_source_season,
                    "feature_provenance": ";".join(
                        f"{key}={value}" for key, value in sorted(provenance.items())
                    ),
                    "missing_feature_count": len(missing),
                    "missing_feature_names": ",".join(missing),
                    **features,
                }
            )
    result = pd.DataFrame.from_records(records)
    keys = ["season", "week", "game_id", "team"]
    if result.duplicated(keys).any():
        raise ValueError(f"Point-in-time matchup keys are not unique: {keys}")
    return result.sort_values(keys).reset_index(drop=True)


def build_team_side_gold(
    matchups: pd.DataFrame,
    schedule: pd.DataFrame,
    *,
    as_of: str,
    provenance: Mapping[str, str],
    prior_source_overrides: Mapping[int, int] | None = None,
) -> pd.DataFrame:
    """Build the canonical unblended team-side Gold feature contract."""
    routed = add_completed_game_routing(
        matchups,
        schedule,
        prior_source_overrides=prior_source_overrides,
    )
    cutoff = pd.to_datetime(as_of, utc=True, errors="raise")
    records: list[dict[str, object]] = []
    context_columns = [
        column
        for column in ("neutral_site", "conference_game", "same_conference")
        if column in routed
    ]
    for game in routed.to_dict("records"):
        for side, opponent_side in (("home", "away"), ("away", "home")):
            feature_values: dict[str, object] = {}
            prefix = f"{side}_"
            for column, value in game.items():
                if not column.startswith(prefix) or column == f"{side}_team":
                    continue
                name = column.removeprefix(prefix)
                if any(token in name.casefold() for token in FORBIDDEN_FEATURE_TOKENS):
                    continue
                if name.startswith("prior_"):
                    feature_values[name] = value
                elif name.startswith("current_"):
                    feature_values[name] = value
                elif name in {
                    "completed_games",
                    "points",
                    "conference",
                    "classification",
                }:
                    continue
                else:
                    feature_values[f"current_{name}"] = value
            completed = int(game[f"{side}_completed_games"])
            opponent_completed = int(game[f"{opponent_side}_completed_games"])
            row: dict[str, object] = {
                "season": int(game["season"]),
                "week": int(game.get("week", 0)),
                "game_id": int(game["game_id"]),
                "kickoff_utc": pd.Timestamp(game["start_date"]).isoformat(),
                "team": game[f"{side}_team"],
                "opponent": game[f"{opponent_side}_team"],
                "side": side,
                "completed_game_count": completed,
                "opponent_completed_game_count": opponent_completed,
                "team_regime": completed_game_regime(completed),
                "prediction_regime": game["prediction_regime"],
                "prior_source_season": int(game["prior_source_season"]),
                "prior_season_gap": int(game["prior_season_gap"]),
                "feature_as_of": min(
                    cutoff,
                    pd.Timestamp(game["start_date"]) - pd.Timedelta(microseconds=1),
                ).isoformat(),
                "feature_provenance": json.dumps(dict(sorted(provenance.items()))),
                **{column: game[column] for column in context_columns},
                **feature_values,
            }
            for target in ("spread_target", "total_target"):
                if target in game:
                    row[target] = game[target]
            prior_columns = [
                name for name in feature_values if name.startswith("prior_")
            ]
            current_columns = [
                name for name in feature_values if name.startswith("current_")
            ]
            row["prior_features_missing"] = not prior_columns or all(
                pd.isna(feature_values[name]) for name in prior_columns
            )
            row["current_features_missing"] = not current_columns or all(
                pd.isna(feature_values[name]) for name in current_columns
            )
            row["missing_feature_count"] = sum(
                pd.isna(value) for value in feature_values.values()
            )
            records.append(row)
    result = pd.DataFrame.from_records(records)
    keys = ["season", "game_id", "team"]
    if result.duplicated(keys).any():
        raise ValueError(f"Gold team-side keys are not unique: {keys}")
    return result.sort_values(["season", "kickoff_utc", "game_id", "side"]).reset_index(
        drop=True
    )


def team_side_to_wide(team_side: pd.DataFrame) -> pd.DataFrame:
    """Materialize the deterministic one-row-per-game ML view."""
    required = {"season", "game_id", "team", "opponent", "side", "kickoff_utc"}
    if missing := sorted(required - set(team_side.columns)):
        raise ValueError(f"Team-side Gold data is missing columns: {missing}")
    rows: list[dict[str, object]] = []
    identity = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "team",
        "opponent",
        "side",
        "prediction_regime",
        "feature_as_of",
        "feature_provenance",
        "spread_target",
        "total_target",
    }
    for (_, game_id), group in team_side.groupby(["season", "game_id"], sort=True):
        if len(group) != 2 or set(group["side"]) != {"home", "away"}:
            raise ValueError(
                f"Game {game_id} does not contain one home and one away row"
            )
        home = group[group["side"] == "home"].iloc[0]
        away = group[group["side"] == "away"].iloc[0]
        row: dict[str, object] = {
            "season": int(home["season"]),
            "week": int(home["week"]),
            "game_id": int(game_id),
            "start_date": home["kickoff_utc"],
            "home_team": home["team"],
            "away_team": away["team"],
            "home_completed_games": int(home["completed_game_count"]),
            "away_completed_games": int(away["completed_game_count"]),
            "prediction_regime": home["prediction_regime"],
            "prior_source_season": int(home["prior_source_season"]),
            "prior_season_gap": int(home["prior_season_gap"]),
            "feature_as_of": home["feature_as_of"],
            "feature_provenance": home["feature_provenance"],
        }
        for target in ("spread_target", "total_target"):
            if target in home:
                row[target] = home[target]
        for side, source in (("home", home), ("away", away)):
            for column, value in source.items():
                if column in identity or column in {
                    "completed_game_count",
                    "opponent_completed_game_count",
                    "team_regime",
                    "prior_source_season",
                    "prior_season_gap",
                }:
                    continue
                if column.startswith("current_"):
                    output = f"{side}_{column.removeprefix('current_')}"
                elif column.startswith("prior_"):
                    output = f"{side}_{column}"
                else:
                    output = f"{side}_{column}"
                row[output] = value
        rows.append(row)
    result = pd.DataFrame.from_records(rows)
    if result.duplicated(["season", "game_id"]).any():
        raise ValueError("Wide Gold game keys are not unique")
    return result.sort_values(["season", "start_date", "game_id"]).reset_index(
        drop=True
    )


def attach_baseline_predictions(
    matchups: pd.DataFrame,
    baselines: pd.DataFrame,
    *,
    required_seasons: set[int] | None = None,
) -> pd.DataFrame:
    """Attach explicit OOF/inference baseline components to the wide Gold view."""
    required = {
        "season",
        "game_id",
        "baseline_spread_prediction",
        "baseline_total_prediction",
    }
    if missing := sorted(required - set(baselines.columns)):
        raise ValueError(f"Baseline predictions are missing columns: {missing}")
    if baselines.duplicated(["season", "game_id"]).any():
        raise ValueError("Baseline prediction keys are not unique")
    # Preserve the two temporal components as well as the selected baseline.
    # The canonical blend is an evaluation-only candidate and must be rebuilt
    # from immutable OOF components, never reverse-engineered from a final
    # baseline prediction.
    component_columns = [
        column
        for column in baselines.columns
        if column in {"season", "game_id", "training_max_year"}
        or column.endswith("_prediction")
    ]
    result = matchups.merge(
        baselines[component_columns], on=["season", "game_id"], how="left"
    )
    missing_rows = (
        result[["baseline_spread_prediction", "baseline_total_prediction"]]
        .isna()
        .any(axis=1)
    )
    # A labeled-season game without a final result (canceled or unreported)
    # cannot carry a baseline or a target; it is unlabeled exactly like a
    # future scheduled game and must not fail the join.
    resultless = pd.Series(False, index=result.index)
    for target_column in ("spread_target", "total_target"):
        if target_column in result.columns:
            resultless |= result[target_column].isna()
    missing_rows &= ~resultless
    if required_seasons is not None:
        missing_rows &= result["season"].astype(int).isin(required_seasons)
    if missing_rows.any():
        ids = result.loc[missing_rows, "game_id"].tolist()
        raise ValueError(f"Missing baseline predictions for games: {ids[:10]}")
    return result
