"""Sealed V5-03 candidate evaluation and deterministic selection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    DEFINITIONS,
    OUTER_SEASONS,
    PRIOR_FAMILIES,
    UPDATERS,
    candidate_id,
)


class PossessionTournamentError(ValueError):
    """Raised when a candidate cannot be fairly evaluated or selected."""


def _bootstrap(
    candidate: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    seed: int = 20260908,
    samples: int = 2000,
) -> tuple[float, float, float]:
    merged = candidate.merge(
        reference,
        on=["season", "week", "game_id", "target"],
        suffixes=("_candidate", "_reference"),
        validate="one_to_one",
    )
    if merged.empty:
        raise PossessionTournamentError("paired bootstrap requires common predictions")
    differences = merged["absolute_error_reference"].to_numpy(float) - merged[
        "absolute_error_candidate"
    ].to_numpy(float)
    rng = np.random.default_rng(seed)
    # Hierarchical season/week resampling preserves the shared-game comparison.
    # Construct each resampled group mean in vectorized batches instead of
    # repeatedly filtering DataFrames inside 2,000 Python-level replicas.
    seasons = sorted(merged["season"].unique())
    grouped = {
        int(season): [
            group["absolute_error_reference"].to_numpy(float)
            - group["absolute_error_candidate"].to_numpy(float)
            for _, group in season_rows.groupby("week", sort=True)
        ]
        for season, season_rows in merged.groupby("season", sort=True)
    }
    if set(grouped) != set(seasons) or any(
        not values for values in grouped.values()
    ):
        raise PossessionTournamentError("paired bootstrap has an empty season/week")

    season_choices = rng.integers(0, len(seasons), size=(samples, len(seasons)))
    sums = np.zeros(samples, dtype=float)
    counts = np.zeros(samples, dtype=np.int64)
    for season_index, season in enumerate(seasons):
        replica_indices, _ = np.where(season_choices == season_index)
        week_values = grouped[int(season)]
        selected_weeks = rng.integers(
            0,
            len(week_values),
            size=(len(replica_indices), len(week_values)),
        )
        for week_index, values in enumerate(week_values):
            occurrences, _ = np.where(selected_weeks == week_index)
            if not len(occurrences):
                continue
            replicas = replica_indices[occurrences]
            sampled = values[
                rng.integers(0, len(values), size=(len(replicas), len(values)))
            ].mean(axis=1)
            np.add.at(sums, replicas, sampled * len(values))
            np.add.at(counts, replicas, len(values))
    if (counts == 0).any():
        raise PossessionTournamentError("paired bootstrap generated an empty replica")
    means = sums / counts
    return (
        float(differences.mean()),
        float(np.quantile(means, 0.05)),
        float(np.quantile(means, 0.95)),
    )


def bridge_predictions(
    states: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    candidate: str,
    alpha: float = 10.0,
) -> pd.DataFrame:
    """Fit one earlier-only four-role Ridge bridge for margin and total."""
    required = {
        "candidate_id",
        "season",
        "game_id",
        "team",
        "offense_rating",
        "defense_rating",
    }
    if required - set(states) or {"season", "game_id", "home_team", "away_team"} - set(
        games
    ):
        raise PossessionTournamentError("bridge inputs lack state or schedule keys")
    current = states[states["candidate_id"].eq(candidate)]
    home = current.rename(
        columns={
            "team": "home_team",
            "offense_rating": "home_offense",
            "defense_rating": "home_defense",
        }
    )
    away = current.rename(
        columns={
            "team": "away_team",
            "offense_rating": "away_offense",
            "defense_rating": "away_defense",
        }
    )
    frame = (
        games.merge(
            home[["season", "game_id", "home_team", "home_offense", "home_defense"]],
            on=["season", "game_id", "home_team"],
            how="left",
        )
        .merge(
            away[["season", "game_id", "away_team", "away_offense", "away_defense"]],
            on=["season", "game_id", "away_team"],
            how="left",
        )
        .merge(outcomes, on=["season", "game_id"], how="inner")
    )
    features = ["home_offense", "home_defense", "away_offense", "away_defense"]
    if "home_host" not in frame:
        frame["home_host"] = 1.0
    if "venue_unknown" not in frame:
        frame["venue_unknown"] = False
    frame["home_host"] = frame["home_host"].fillna(0).astype(float)
    frame["venue_unknown"] = frame["venue_unknown"].fillna(True).astype(float)
    features += ["home_host", "venue_unknown"]
    frame = frame.dropna(subset=[*features, "home_points", "away_points"])
    rows: list[dict[str, Any]] = []
    for season in OUTER_SEASONS:
        test = frame[frame["season"].eq(season)]
        train = frame[frame["season"] < season]
        if test.empty or train.empty:
            continue
        center, scale = (
            train[features].mean(),
            train[features].std(ddof=0).clip(lower=0.05),
        )
        x_train, x_test = (
            (train[features] - center) / scale,
            (test[features] - center) / scale,
        )
        varying = [
            col for col in features if x_train[col].nunique(dropna=False) > 1
        ]
        if not varying:
            continue
        x_train_v = x_train[varying]
        x_test_v = x_test[varying]
        targets = {
            "margin": train["home_points"] - train["away_points"],
            "total": train["home_points"] + train["away_points"],
        }
        actuals = {
            "margin": test["home_points"] - test["away_points"],
            "total": test["home_points"] + test["away_points"],
        }
        for target, y in targets.items():
            model = Ridge(alpha=alpha).fit(x_train_v, y)
            prediction = model.predict(x_test_v)
            for row, value, actual in zip(
                test.itertuples(index=False),
                prediction,
                actuals[target].to_numpy(float),
                strict=True,
            ):
                rows.append(
                    {
                        "candidate_id": candidate,
                        "definition": candidate.split("__", 1)[0],
                        "season": int(season),
                        "week": int(getattr(row, "week", 0)),
                        "game_id": int(row.game_id),
                        "target": target,
                        "actual": float(actual),
                        "prediction": float(value),
                        "absolute_error": abs(float(value) - float(actual)),
                        "training_seasons": ",".join(
                            map(str, sorted(train["season"].unique()))
                        ),
                        "venue_unknown": bool(row.venue_unknown),
                        "completed_game_stage": int(
                            getattr(row, "completed_game_stage", 0)
                        ),
                    }
                )
    return pd.DataFrame(rows)


def select_candidates(
    predictions: pd.DataFrame,
    validity: Mapping[str, str | None] | None = None,
) -> pd.DataFrame:
    """Apply the contract's within-definition and PPP-preferred cross-definition gates.

    ``validity`` maps candidate IDs to an explicit failure reason (or ``None``).
    A failed candidate is reported with sentinel metrics and can never advance;
    an invalid reference blocks its definition entirely.
    """
    if predictions.empty and not validity:
        raise PossessionTournamentError("selection needs bridge predictions")
    expected = {
        candidate_id(d, p, u)
        for d in DEFINITIONS
        for p in PRIOR_FAMILIES
        for u in UPDATERS
    }
    failures = {key: value for key, value in (validity or {}).items() if value}
    represented = set(predictions["candidate_id"]) | set(failures)
    if represented != expected:
        raise PossessionTournamentError("selection requires all 60 candidates")
    records: list[dict[str, Any]] = []
    retained: dict[str, str] = {}
    for definition in DEFINITIONS:
        subset = predictions[predictions["definition"].eq(definition)]
        reference_id = candidate_id(definition, "rho_0_60", "exposure")
        if reference_id in failures or reference_id not in set(subset["candidate_id"]):
            raise PossessionTournamentError(
                f"invalid or missing reference blocks definition: {reference_id}"
            )
        reference = subset[subset["candidate_id"].eq(reference_id)]
        reference_mae = float(reference["absolute_error"].mean())
        reference_stages = set(reference["completed_game_stage"])
        reference_seasons = set(reference["season"])
        passing = [reference_id]
        for candidate in sorted(expected):
            if not candidate.startswith(f"{definition}__"):
                continue
            if candidate in failures:
                records.append(
                    {
                        "candidate_id": candidate,
                        "definition": definition,
                        "prior_family": candidate.split("__")[1],
                        "updater": candidate.split("__")[2],
                        "reference_candidate": reference_id,
                        "pooled_mae": -1.0,
                        "reference_mae": reference_mae,
                        "improvement_pct": -100.0,
                        "bootstrap_90_lower": -1.0,
                        "bootstrap_90_upper": -1.0,
                        "full_gate": False,
                        "early_gate": False,
                        "regression_gate": False,
                        "valid": False,
                        "selected": False,
                        "selection_reason": f"validity_failure: {failures[candidate]}",
                    }
                )
                continue
            values = subset[subset["candidate_id"].eq(candidate)]
            if len(values) != len(reference):
                raise PossessionTournamentError(
                    "candidate population differs from reference"
                )
            mae = float(values["absolute_error"].mean())
            improvement, lower, upper = _bootstrap(values, reference)
            percent = 100 * (reference_mae - mae) / reference_mae
            candidate_stages = set(values["completed_game_stage"])
            candidate_seasons = set(values["season"])
            if not candidate_stages <= reference_stages:
                stage_regression = False
            else:
                stage_ratio = (
                    values.groupby("completed_game_stage")["absolute_error"].mean()
                    / reference.groupby("completed_game_stage")["absolute_error"].mean()
                )
                stage_regression = bool((stage_ratio <= 1.05).all())
            if not candidate_seasons <= reference_seasons:
                season_regression = False
            else:
                season_ratio = (
                    values.groupby("season")["absolute_error"].mean()
                    / reference.groupby("season")["absolute_error"].mean()
                )
                season_regression = bool((season_ratio <= 1.05).all())
            regression = stage_regression and season_regression
            full = percent >= 0.5 and lower > 0
            early_values, early_reference = (
                values[values["completed_game_stage"].le(3)],
                reference[reference["completed_game_stage"].le(3)],
            )
            early = False
            if not early_values.empty:
                early_mean, early_lower, _ = _bootstrap(early_values, early_reference)
                early = (
                    100
                    * early_mean
                    / max(float(early_reference["absolute_error"].mean()), 1e-12)
                    >= 0.5
                    and early_lower > 0
                    and mae <= reference_mae * 1.01
                )
            valid = candidate == reference_id or ((full or early) and regression)
            if valid:
                passing.append(candidate)
            prior = candidate.split("__")[1]
            updater = candidate.split("__")[2]
            records.append(
                {
                    "candidate_id": candidate,
                    "definition": definition,
                    "prior_family": prior,
                    "updater": updater,
                    "reference_candidate": reference_id,
                    "pooled_mae": mae,
                    "reference_mae": reference_mae,
                    "improvement_pct": percent,
                    "bootstrap_90_lower": lower,
                    "bootstrap_90_upper": upper,
                    "full_gate": full,
                    "early_gate": early,
                    "regression_gate": regression,
                    "valid": valid,
                    "selected": False,
                    "selection_reason": "reference"
                    if candidate == reference_id
                    else "failed",
                }
            )
        complexity = {
            "neutral": 0,
            "rho_0_60": 0,
            "recruiting_ridge": 1,
            "returning_production_ridge": 1,
            "continuity_ridge": 1,
            "all_context_ridge": 3,
        }
        order = {
            "exposure": 0,
            "half_life_8": 1,
            "half_life_4": 2,
            "half_life_2": 3,
            "kalman": 4,
        }
        candidate_metrics = {
            record["candidate_id"]: record
            for record in records
            if record["definition"] == definition
        }
        best = min(candidate_metrics[item]["pooled_mae"] for item in passing)
        retained[definition] = min(
            (
                item
                for item in passing
                if candidate_metrics[item]["pooled_mae"] <= best * 1.005
            ),
            key=lambda item: (
                complexity[item.split("__")[1]],
                order[item.split("__")[2]],
                item,
            ),
        )
    selected = retained["ppp"]
    ppp_record = next(
        record for record in records if record["candidate_id"] == retained["ppp"]
    )
    epa_record = next(
        record
        for record in records
        if record["candidate_id"] == retained["epa_per_possession"]
    )
    if (
        epa_record["valid"]
        and epa_record["pooled_mae"] < ppp_record["pooled_mae"] * 0.995
        and epa_record["bootstrap_90_lower"] > 0
    ):
        selected = retained["epa_per_possession"]
    for record in records:
        record["selected"] = record["candidate_id"] == selected
        if record["selected"]:
            record["selection_reason"] = "cross_definition_winner"
    return pd.DataFrame(records)
