"""Common earlier-only forecast bridge and paired historical evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from cks_picks_cfb.forecast.heads import FEATURES, _fit_one, gaussian_crps

from .contracts import DEVELOPMENT_SEASONS, HEADLINE_SEASONS, RatingState
from .corpus import Corpus

KEYS = ["season", "week", "game_id", "target"]


def _expected_keys(corpus: Corpus) -> set[tuple[int, int, int, str]]:
    frame = corpus.v5_predictions
    return set(frame.loc[:, KEYS].itertuples(index=False, name=None))


def validate_prediction_population(predictions: pd.DataFrame, corpus: Corpus) -> None:
    if predictions.duplicated(KEYS).any() or set(
        predictions.loc[:, KEYS].itertuples(index=False, name=None)
    ) != _expected_keys(corpus):
        raise ValueError(
            "candidate predictions do not cover the accepted eligible schedule"
        )
    expected = corpus.v5_predictions.loc[:, KEYS + ["actual"]]
    paired = predictions.merge(
        expected, on=KEYS, suffixes=("", "_v5"), validate="one_to_one"
    )
    if len(paired) != len(expected) or not np.allclose(
        paired["actual"], paired["actual_v5"]
    ):
        raise ValueError("candidate outcomes differ from frozen V5 benchmark")


FOUR_FACTOR_CORE_IDS: tuple[str, ...] = (
    "rush_success_rate",
    "rush_explosiveness",
    "pass_success_rate",
    "pass_explosiveness",
)

FIVE_FACTOR_CORE_IDS: tuple[str, ...] = (
    *FOUR_FACTOR_CORE_IDS,
    "finish_points_per_opp",
)

DIRECT18_FEATURES: tuple[str, ...] = (
    "home_offense__rush_success_rate",
    "home_offense__rush_explosiveness",
    "home_offense__pass_success_rate",
    "home_offense__pass_explosiveness",
    "home_defense__rush_success_rate",
    "home_defense__rush_explosiveness",
    "home_defense__pass_success_rate",
    "home_defense__pass_explosiveness",
    "away_offense__rush_success_rate",
    "away_offense__rush_explosiveness",
    "away_offense__pass_success_rate",
    "away_offense__pass_explosiveness",
    "away_defense__rush_success_rate",
    "away_defense__rush_explosiveness",
    "away_defense__pass_success_rate",
    "away_defense__pass_explosiveness",
    "home_host",
    "venue_unknown",
)

DIRECT22_FEATURES: tuple[str, ...] = (
    "home_offense__rush_success_rate",
    "home_offense__rush_explosiveness",
    "home_offense__pass_success_rate",
    "home_offense__pass_explosiveness",
    "home_offense__finish_points_per_opp",
    "home_defense__rush_success_rate",
    "home_defense__rush_explosiveness",
    "home_defense__pass_success_rate",
    "home_defense__pass_explosiveness",
    "home_defense__finish_points_per_opp",
    "away_offense__rush_success_rate",
    "away_offense__rush_explosiveness",
    "away_offense__pass_success_rate",
    "away_offense__pass_explosiveness",
    "away_offense__finish_points_per_opp",
    "away_defense__rush_success_rate",
    "away_defense__rush_explosiveness",
    "away_defense__pass_success_rate",
    "away_defense__pass_explosiveness",
    "away_defense__finish_points_per_opp",
    "home_host",
    "venue_unknown",
)

DIFFERENTIAL_SPREAD_FEATURES: tuple[str, ...] = (
    "diff__rush_success_rate",
    "diff__rush_explosiveness",
    "diff__pass_success_rate",
    "diff__pass_explosiveness",
    "home_host",
    "venue_unknown",
)

DIFFERENTIAL_SPREAD_FEATURES_5F: tuple[str, ...] = (
    "diff__rush_success_rate",
    "diff__rush_explosiveness",
    "diff__pass_success_rate",
    "diff__pass_explosiveness",
    "diff__finish_points_per_opp",
    "home_host",
    "venue_unknown",
)

DIFFERENTIAL_TOTAL_FEATURES: tuple[str, ...] = (
    "sum__rush_success_rate",
    "sum__rush_explosiveness",
    "sum__pass_success_rate",
    "sum__pass_explosiveness",
    "home_host",
    "venue_unknown",
)

DIFFERENTIAL_TOTAL_FEATURES_5F: tuple[str, ...] = (
    "sum__rush_success_rate",
    "sum__rush_explosiveness",
    "sum__pass_success_rate",
    "sum__pass_explosiveness",
    "sum__finish_points_per_opp",
    "home_host",
    "venue_unknown",
)


def frame_with_candidate_states(
    corpus: Corpus, states: list[RatingState]
) -> pd.DataFrame:
    """Swap only rating columns; offsets, outcomes, venue, and stages stay fixed."""
    rows = pd.DataFrame.from_records(
        [
            {
                "season": state.season,
                "game_id": state.game_id,
                "team": state.team,
                "role": state.role,
                "mean": state.rating.mean,
            }
            for state in states
        ]
    )
    if rows.empty or rows.duplicated(["season", "game_id", "team", "role"]).any():
        raise ValueError("candidate rating states are empty or duplicated")
    frame = corpus.v5_features.copy()
    if frame.duplicated(["season", "game_id"]).any():
        raise ValueError("V5 common feature frame has duplicate games")
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            selected = rows[rows["role"].eq(role)].rename(
                columns={"team": f"{side}_team", "mean": f"{side}_{role}"}
            )
            frame = frame.drop(columns=[f"{side}_{role}"]).merge(
                selected[["season", "game_id", f"{side}_team", f"{side}_{role}"]],
                on=["season", "game_id", f"{side}_team"],
                how="left",
                validate="one_to_one",
            )
    if frame.loc[:, FEATURES].isna().any().any():
        raise ValueError("candidate lacks one or more full-population pregame states")
    return frame


def frame_with_multifactor_states(
    corpus: Corpus,
    states: list[RatingState],
    *,
    core_mids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Assemble multi-factor matchup features including direct columns and differentials/sums."""
    records = []
    for s in states:
        mid = s.explanation.get("measurement_id")
        if not mid:
            raise ValueError(
                f"RatingState for team {s.team!r} role {s.role!r} has no measurement_id in explanation"
            )
        records.append(
            {
                "season": s.season,
                "game_id": s.game_id,
                "team": s.team,
                "role": s.role,
                "measurement_id": str(mid),
                "mean": s.rating.mean,
            }
        )
    rows = pd.DataFrame.from_records(records)
    if rows.empty:
        raise ValueError("candidate rating states are empty")
    if rows.duplicated(["season", "game_id", "team", "role", "measurement_id"]).any():
        raise ValueError("candidate rating states have duplicate entries")

    if core_mids is None:
        has_finish = "finish_points_per_opp" in set(rows["measurement_id"])
        core_mids = FIVE_FACTOR_CORE_IDS if has_finish else FOUR_FACTOR_CORE_IDS

    frame = corpus.v5_features.copy()
    if frame.duplicated(["season", "game_id"]).any():
        raise ValueError("V5 common feature frame has duplicate games")

    # Merge each of the factors for home and away offense and defense
    for mid in core_mids:
        mid_rows = rows[rows["measurement_id"].eq(mid)]
        if mid_rows.empty:
            raise ValueError(f"no rating states found for core factor: {mid!r}")
        for side in ("home", "away"):
            for role in ("offense", "defense"):
                col_name = f"{side}_{role}__{mid}"
                selected = mid_rows[mid_rows["role"].eq(role)].rename(
                    columns={"team": f"{side}_team", "mean": col_name}
                )
                if role == "defense":
                    # Frame space is quality space for all columns; filter space remains observation space.
                    # Negate allowed-rate values so higher is strictly better.
                    selected[col_name] = -selected[col_name]
                frame = frame.merge(
                    selected[["season", "game_id", f"{side}_team", col_name]],
                    on=["season", "game_id", f"{side}_team"],
                    how="left",
                    validate="one_to_one",
                )

    # Compute differentials and sums for Bridge B
    for mid in core_mids:
        h_off = frame[f"home_offense__{mid}"]
        a_def = frame[f"away_defense__{mid}"]
        a_off = frame[f"away_offense__{mid}"]
        h_def = frame[f"home_defense__{mid}"]

        frame[f"diff__{mid}"] = (h_off - a_def) - (a_off - h_def)
        frame[f"sum__{mid}"] = (h_off - a_def) + (a_off - h_def)

    # Validate no missing values
    check_cols = (
        [
            f"{side}_{role}__{mid}"
            for mid in core_mids
            for side in ("home", "away")
            for role in ("offense", "defense")
        ]
        + [f"diff__{mid}" for mid in core_mids]
        + [f"sum__{mid}" for mid in core_mids]
        + ["home_host", "venue_unknown"]
    )
    if frame.loc[:, check_cols].isna().any().any():
        raise ValueError("candidate lacks one or more full-population pregame states")

    return frame


def _calibration_variance(
    frame: pd.DataFrame,
    *,
    season: int,
    target: str,
    features: tuple[str, ...] = FEATURES,
) -> tuple[float, int]:
    errors: list[float] = []
    for validation in (s for s in DEVELOPMENT_SEASONS if 2017 <= s < season):
        train = frame[frame.season.lt(validation)]
        test = frame[frame.season.eq(validation)]
        if train.empty or test.empty:
            continue
        values, _ = _fit_one(
            train, test, target=target, alpha=10.0, floor=1e-6, features=features
        )
        actual = test[f"actual_{target}"].to_numpy(float)
        offset = test[f"offset_{target}"].to_numpy(float)
        errors.extend((actual - offset - values).tolist())
    if not errors:
        raise ValueError("earlier-only calibration has no residual evidence")
    return max(float(np.mean(np.square(errors))), 1e-6), len(errors)


def common_bridge_predictions(
    corpus: Corpus,
    frame: pd.DataFrame,
    *,
    candidate_id: str,
    seasons: tuple[int, ...] = HEADLINE_SEASONS,
    bridge: str = "v5_common",
) -> pd.DataFrame:
    """Alpha-10 Ridge on seasons before each validation season; no model selection."""
    if not candidate_id or frame.duplicated(["season", "game_id"]).any():
        raise ValueError("invalid candidate feature frame")
    if set(
        frame.loc[:, ["season", "game_id"]].itertuples(index=False, name=None)
    ) != set(
        corpus.v5_features.loc[:, ["season", "game_id"]].itertuples(
            index=False, name=None
        )
    ):
        raise ValueError(
            "common bridge requires the complete historical feature population"
        )

    if bridge == "v5_common":
        req_features = list(FEATURES)
    elif bridge in ("alpha10_direct18", "alpha10_direct22"):
        req_features = (
            list(DIRECT22_FEATURES)
            if "home_offense__finish_points_per_opp" in frame.columns
            else list(DIRECT18_FEATURES)
        )
    elif bridge == "alpha10_differentials":
        if "diff__finish_points_per_opp" in frame.columns:
            req_features = list(
                set(DIFFERENTIAL_SPREAD_FEATURES_5F)
                | set(DIFFERENTIAL_TOTAL_FEATURES_5F)
            )
        else:
            req_features = list(
                set(DIFFERENTIAL_SPREAD_FEATURES) | set(DIFFERENTIAL_TOTAL_FEATURES)
            )
    else:
        raise ValueError(f"unregistered bridge type: {bridge!r}")

    if (
        frame.loc[
            :,
            [
                *req_features,
                "actual_margin",
                "actual_total",
                "offset_margin",
                "offset_total",
            ],
        ]
        .isna()
        .any()
        .any()
    ):
        raise ValueError("common bridge has missing inputs")
    records: list[dict[str, object]] = []
    if seasons not in (HEADLINE_SEASONS, (2018, 2019, 2021)):
        raise ValueError("unregistered evaluation season group")
    for season in seasons:
        train = frame[frame.season.lt(season)].copy()
        test = frame[frame.season.eq(season)].copy()
        if train.empty or test.empty or train.season.ge(season).any():
            raise ValueError("invalid rolling-origin split")
        for target in ("margin", "total"):
            if bridge == "v5_common":
                active_features = FEATURES
            elif bridge in ("alpha10_direct18", "alpha10_direct22"):
                active_features = (
                    DIRECT22_FEATURES
                    if "home_offense__finish_points_per_opp" in frame.columns
                    else DIRECT18_FEATURES
                )
            elif bridge == "alpha10_differentials":
                if "diff__finish_points_per_opp" in frame.columns:
                    active_features = (
                        DIFFERENTIAL_SPREAD_FEATURES_5F
                        if target == "margin"
                        else DIFFERENTIAL_TOTAL_FEATURES_5F
                    )
                else:
                    active_features = (
                        DIFFERENTIAL_SPREAD_FEATURES
                        if target == "margin"
                        else DIFFERENTIAL_TOTAL_FEATURES
                    )

            variance, calibration_count = _calibration_variance(
                frame, season=season, target=target, features=active_features
            )
            fitted, _ = _fit_one(
                train,
                test,
                target=target,
                alpha=10.0,
                floor=1e-6,
                features=active_features,
            )
            prediction = fitted + test[f"offset_{target}"].to_numpy(float)
            actual = test[f"actual_{target}"].to_numpy(float)
            crps = gaussian_crps(actual, prediction, variance)
            z90 = float(norm.ppf(0.95))
            for row, value, truth, score in zip(
                test.itertuples(index=False), prediction, actual, crps, strict=True
            ):
                records.append(
                    {
                        "candidate_id": candidate_id,
                        "season": int(row.season),
                        "week": int(row.week),
                        "game_id": int(row.game_id),
                        "target": target,
                        "actual": float(truth),
                        "prediction": float(value),
                        "absolute_error": float(abs(truth - value)),
                        "gaussian_crps": float(score),
                        "variance": variance,
                        "interval_90_lower": float(value - z90 * np.sqrt(variance)),
                        "interval_90_upper": float(value + z90 * np.sqrt(variance)),
                        "training_seasons": ",".join(
                            map(str, sorted(train.season.unique()))
                        ),
                        "calibration_count": calibration_count,
                        "completed_game_stage": int(row.completed_game_stage),
                    }
                )
    predictions = (
        pd.DataFrame.from_records(records).sort_values(KEYS).reset_index(drop=True)
    )
    if seasons == HEADLINE_SEASONS:
        validate_prediction_population(predictions, corpus)
    else:
        expected = frame[frame.season.isin(seasons)]
        if len(predictions) != 2 * len(expected) or predictions.duplicated(KEYS).any():
            raise ValueError("early diagnostic population is incomplete")
    return predictions


def frozen_v5_predictions(corpus: Corpus) -> pd.DataFrame:
    frame = corpus.v5_predictions.copy()
    frame["absolute_error"] = (frame.actual - frame.prediction).abs()
    validate_prediction_population(frame, corpus)
    return frame


def metrics(frame: pd.DataFrame) -> dict[str, object]:
    error = frame.actual.to_numpy(float) - frame.prediction.to_numpy(float)
    result: dict[str, object] = {
        "rows": len(frame),
        "games": len(frame[["season", "game_id"]].drop_duplicates()),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "bias": float(np.mean(error)),
        "crps": float(frame.gaussian_crps.mean()) if "gaussian_crps" in frame else None,
    }
    if {"interval_90_lower", "interval_90_upper"} <= set(frame):
        lower, upper = (
            frame.interval_90_lower.to_numpy(float),
            frame.interval_90_upper.to_numpy(float),
        )
        result["interval_90_coverage"] = float(
            np.mean(
                (frame.actual.to_numpy(float) >= lower)
                & (frame.actual.to_numpy(float) <= upper)
            )
        )
        result["interval_90_width"] = float(np.mean(upper - lower))
    return result


def scorecard(predictions: pd.DataFrame) -> dict[str, object]:
    return {
        "pooled": {
            target: metrics(part)
            for target, part in predictions.groupby("target", sort=True)
        },
        "by_season": {
            str(season): {
                target: metrics(part)
                for target, part in rows.groupby("target", sort=True)
            }
            for season, rows in predictions.groupby("season", sort=True)
        },
        "by_stage": {
            str(stage): {
                target: metrics(part)
                for target, part in rows.groupby("target", sort=True)
            }
            for stage, rows in predictions.groupby("completed_game_stage", sort=True)
        },
    }


def paired_comparison(
    candidate: pd.DataFrame,
    reference: pd.DataFrame,
    corpus: Corpus,
    *,
    seed: int = 20260928,
    samples: int = 2000,
) -> dict[str, object]:
    validate_prediction_population(candidate, corpus)
    validate_prediction_population(reference, corpus)
    merged = candidate.merge(
        reference, on=KEYS, suffixes=("_candidate", "_reference"), validate="one_to_one"
    )
    report: dict[str, object] = {
        "candidate": scorecard(candidate),
        "reference": scorecard(reference),
        "paired": {},
    }
    rng = np.random.default_rng(seed)
    for target, rows in merged.groupby("target", sort=True):
        rows = rows.reset_index(drop=True)
        difference = rows.absolute_error_reference.to_numpy(
            float
        ) - rows.absolute_error_candidate.to_numpy(float)
        blocks = [
            group.index.to_numpy()
            for _, group in rows.groupby(["season", "week"], sort=True)
        ]
        sampled = []
        for _ in range(samples):
            chosen = rng.integers(0, len(blocks), len(blocks))
            indices = np.concatenate([blocks[index] for index in chosen])
            sampled.append(float(difference[indices].mean()))
        report["paired"][target] = {
            "mae_gain": float(difference.mean()),
            "lower_90": float(np.quantile(sampled, 0.05)),
            "upper_90": float(np.quantile(sampled, 0.95)),
            "seed": seed,
            "replicates": samples,
        }
    return report
