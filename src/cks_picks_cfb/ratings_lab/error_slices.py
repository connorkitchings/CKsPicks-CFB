"""Pure slicing of V5 prediction errors for the 2021-2025 development view.

Read-only diagnostics. Nothing here fits, selects or tunes a model. Slices are
defined only from the model's own pregame outputs, game timing, completed-game
stage and the evidence-coverage flags; never from market lines or from
betting results (against-the-spread or over/under outcomes).

Error convention: ``error = actual - prediction``. A positive bias therefore
means outcomes ran above the prediction (the model under-predicted).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

MIN_CELL_GAMES = 100
DEVELOPMENT_VIEW_SEASONS = (2021, 2022, 2023, 2024, 2025)
TERCILE_LABELS = ("low", "mid", "high")
GAP_LABELS = ("small gap", "medium gap", "large gap")
WEEK_BUCKETS = ("1", "2", "3", "4", "5-8", "9-12", "13-16")
REQUIRED = ("season", "game_id", "target", "actual", "prediction")


def require_development_view(frame: pd.DataFrame) -> pd.DataFrame:
    """Reject any season outside 2021-2025 (2020 is excluded, 2026 is held out)."""
    outside = sorted(set(frame["season"].astype(int)) - set(DEVELOPMENT_VIEW_SEASONS))
    if outside:
        raise ValueError(
            f"seasons {outside} are outside the development view "
            f"{DEVELOPMENT_VIEW_SEASONS[0]}-{DEVELOPMENT_VIEW_SEASONS[-1]}"
        )
    return frame


def tercile_edges(values: Sequence[float] | pd.Series) -> tuple[float, float]:
    """Lower and upper tercile cut points computed from the data."""
    low, high = np.quantile(np.asarray(values, dtype=float), [1 / 3, 2 / 3])
    return float(low), float(high)


def assign_terciles(
    values: pd.Series, edges: tuple[float, float], labels: Sequence[str]
) -> pd.Series:
    """Label values at or below the lower edge first, then up to the upper edge."""
    bins = np.where(values <= edges[0], 0, np.where(values <= edges[1], 1, 2))
    return pd.Series(np.asarray(labels, dtype=object)[bins], index=values.index)


def week_bucket(week: int) -> str:
    if week < 1:
        raise ValueError("week buckets start at week 1; week 0 is not in the corpus")
    if week <= 4:
        return str(week)
    if week <= 8:
        return "5-8"
    if week <= 12:
        return "9-12"
    return "13-16"


def partial_quarantine_games(observations: pd.DataFrame) -> set[tuple[int, int]]:
    """Games where some, but not all, team-role PPP observations were quarantined.

    Quarantined means missing for ``unresolved_scoring_attribution``; a role with
    no eligible possessions is a different condition and does not count.
    """
    ppp = observations[observations["measurement_id"].eq("ppp")]
    quarantined = ppp["missing_reason"].eq("unresolved_scoring_attribution")
    grouped = quarantined.groupby(
        [ppp["season"].astype(int), ppp["game_id"].astype(int)]
    )
    partial = grouped.any() & ~grouped.all()
    return {key for key, flag in partial.items() if flag}


def quarantine_exposed_games(
    observations: pd.DataFrame, features: pd.DataFrame
) -> pd.Series:
    """True where either team played an earlier-week partially quarantined game.

    Descriptive exposure flag only. It does not re-estimate ratings, so it is
    not a sensitivity test of the quarantine policy.
    """
    partial = partial_quarantine_games(observations)
    keys = list(
        zip(observations["season"].astype(int), observations["game_id"].astype(int))
    )
    in_partial = np.fromiter(
        (key in partial for key in keys), dtype=bool, count=len(keys)
    )
    rows = observations.loc[in_partial, ["season", "team", "week"]]
    earliest = rows.groupby(["season", "team"])["week"].min()
    result = pd.Series(False, index=features.index)
    for side in ("home", "away"):
        index = pd.MultiIndex.from_arrays(
            [features["season"], features[f"{side}_team"]]
        )
        first = earliest.reindex(index).to_numpy(dtype=float)
        result |= pd.Series(
            first < features["week"].to_numpy(float), index=features.index
        )
    return result


def game_attributes(
    common: pd.DataFrame, features: pd.DataFrame, exposure: pd.Series
) -> tuple[pd.DataFrame, dict[str, tuple[float, float]]]:
    """One row per game with slice labels, plus the tercile edges used.

    ``common`` holds the rolling-origin margin and total predictions. Gap size
    is the absolute predicted margin; the totals regime is the predicted total.
    Both are the model's own outputs, never market lines.
    """
    require_development_view(common)
    margin = common[common["target"].eq("margin")].set_index(["season", "game_id"])
    total = common[common["target"].eq("total")].set_index(["season", "game_id"])
    attrs = pd.DataFrame(
        {
            "week": margin["week"],
            "stage": margin["completed_game_stage"],
            "abs_predicted_margin": margin["prediction"].abs(),
            "predicted_total": total["prediction"],
        }
    ).reset_index()
    flags = features[["season", "game_id"]].assign(
        quarantine_exposed=exposure.to_numpy()
    )
    attrs = attrs.merge(flags, on=["season", "game_id"], validate="one_to_one")
    gap_edges = tercile_edges(attrs["abs_predicted_margin"])
    total_edges = tercile_edges(attrs["predicted_total"])
    attrs["week_bucket"] = attrs["week"].map(week_bucket)
    attrs["gap_bin"] = assign_terciles(
        attrs["abs_predicted_margin"], gap_edges, GAP_LABELS
    )
    attrs["totals_regime"] = assign_terciles(
        attrs["predicted_total"], total_edges, TERCILE_LABELS
    )
    attrs["stage_label"] = "stage " + attrs["stage"].astype(int).astype(str)
    return attrs, {"gap": gap_edges, "total": total_edges}


def attach_slices(predictions: pd.DataFrame, attributes: pd.DataFrame) -> pd.DataFrame:
    """Join slice labels onto predictions; games without attributes are dropped."""
    missing = [name for name in REQUIRED if name not in predictions]
    if missing:
        raise ValueError(f"predictions lack columns: {missing}")
    require_development_view(predictions)
    return predictions.merge(
        attributes.drop(columns=["week"]),
        on=["season", "game_id"],
        how="inner",
        validate="many_to_one",
    )


def slice_table(
    frame: pd.DataFrame, by: str, order: Sequence[str] | None = None
) -> pd.DataFrame:
    """MAE, RMSE, bias and 90% coverage per slice for a single target.

    Slices with no games are omitted. Cells under ``MIN_CELL_GAMES`` are flagged.
    """
    if frame["target"].nunique() > 1:
        raise ValueError("slice_table needs one target at a time")
    if frame.duplicated(["season", "game_id"]).any():
        raise ValueError("duplicate game rows in a single-target frame")
    labels = list(order) if order is not None else sorted(frame[by].unique())
    unknown = set(frame[by].unique()) - set(labels)
    if unknown:
        raise ValueError(f"slice values missing from ordering: {sorted(unknown)}")
    has_interval = {"interval_90_lower", "interval_90_upper"} <= set(frame)
    rows = []
    for label in labels:
        part = frame[frame[by].eq(label)]
        if part.empty:
            continue
        error = part["actual"].to_numpy(float) - part["prediction"].to_numpy(float)
        coverage = (
            float(
                np.mean(
                    (part["actual"] >= part["interval_90_lower"])
                    & (part["actual"] <= part["interval_90_upper"])
                )
            )
            if has_interval
            else float("nan")
        )
        rows.append(
            {
                "slice": label,
                "games": len(part),
                "mae": float(np.mean(np.abs(error))),
                "rmse": float(np.sqrt(np.mean(np.square(error)))),
                "bias": float(np.mean(error)),
                "coverage": coverage,
                "small": len(part) < MIN_CELL_GAMES,
            }
        )
    return pd.DataFrame(
        rows, columns=["slice", "games", "mae", "rmse", "bias", "coverage", "small"]
    )


def early_season_cost(frame: pd.DataFrame, early_weeks: int = 4) -> pd.DataFrame:
    """Per-week MAE for weeks 1 to ``early_weeks`` against the later-season level."""
    if frame["target"].nunique() > 1:
        raise ValueError("early_season_cost needs one target at a time")
    later = frame[frame["week"] > early_weeks]
    if later.empty:
        raise ValueError("no later-season games to compare against")
    later_mae = float(np.mean(np.abs(later["actual"] - later["prediction"])))
    rows = []
    for week in range(1, early_weeks + 1):
        part = frame[frame["week"].eq(week)]
        if part.empty:
            continue
        mae = float(np.mean(np.abs(part["actual"] - part["prediction"])))
        rows.append(
            {
                "week": week,
                "games": len(part),
                "mae": mae,
                "later_mae": later_mae,
                "excess": mae - later_mae,
                "small": len(part) < MIN_CELL_GAMES,
            }
        )
    return pd.DataFrame(
        rows, columns=["week", "games", "mae", "later_mae", "excess", "small"]
    )
