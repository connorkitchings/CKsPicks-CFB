"""Diagnostic-only retrospective context for the deployed V4 model.

This module intentionally does not use ``prediction_grades`` or any live
record table.  Historical market references are reconstructed after the fact,
so its output is display context only, never a betting or promotion record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

HISTORICAL_MODEL_CONTEXT_DATASET = "historical_model_context"
HISTORICAL_MODEL_CONTEXT_SCHEMA_VERSION = "historical_model_context_v1"
CALCULATION_VERSION = "v1"
TARGETS = ("spread", "total")
PERIOD_SEASON = "season"
PERIOD_WEEK = "week"


class HistoricalModelContextError(ValueError):
    """Raised when a retrospective diagnostic input is not its pinned lineage."""


@dataclass(frozen=True)
class HistoricalModelContextConfig:
    comparison_season: int
    model_id: str
    prediction_ref: Mapping[str, str]
    feature_ref: Mapping[str, str]
    market_ref: Mapping[str, str]
    market_policy_version: str
    timing_class: str
    usage: str

    @property
    def design_id(self) -> str:
        payload = {
            "comparison_season": self.comparison_season,
            "model_id": self.model_id,
            "prediction_ref": dict(self.prediction_ref),
            "feature_ref": dict(self.feature_ref),
            "market_ref": dict(self.market_ref),
            "market_policy_version": self.market_policy_version,
            "timing_class": self.timing_class,
            "usage": self.usage,
            "calculation_version": CALCULATION_VERSION,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def config_from_mapping(raw: Mapping[str, Any]) -> HistoricalModelContextConfig:
    try:
        config = HistoricalModelContextConfig(
            comparison_season=int(raw["comparison_season"]),
            model_id=str(raw["model_id"]),
            prediction_ref=dict(raw["prediction_ref"]),
            feature_ref=dict(raw["feature_ref"]),
            market_ref=dict(raw["market_ref"]),
            market_policy_version=str(raw["market_policy_version"]),
            timing_class=str(raw["timing_class"]),
            usage=str(raw["usage"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HistoricalModelContextError(
            "Incomplete historical context config"
        ) from exc
    if config.comparison_season != 2025:
        raise HistoricalModelContextError("Historical context is pinned to 2025")
    if not config.model_id:
        raise HistoricalModelContextError("Historical context requires a model ID")
    for name, ref in (
        ("prediction", config.prediction_ref),
        ("feature", config.feature_ref),
        ("market", config.market_ref),
    ):
        if set(ref) != {
            "dataset",
            "version_id",
            "schema_version",
            "content_sha",
            "uri",
        }:
            raise HistoricalModelContextError(f"{name} ref must be an exact DatasetRef")
        if len(ref["content_sha"]) != 64:
            raise HistoricalModelContextError(f"{name} ref requires a SHA-256")
    return config


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise HistoricalModelContextError(f"{label} is missing columns: {missing}")


def _assert_ref(
    actual: Mapping[str, Any], expected: Mapping[str, str], label: str
) -> None:
    observed = {key: str(actual.get(key, "")) for key in expected}
    if observed != dict(expected):
        raise HistoricalModelContextError(f"{label} ref identity mismatch")


def validate_parent_refs(
    *,
    prediction_ref: Mapping[str, Any],
    feature_ref: Mapping[str, Any],
    market_ref: Mapping[str, Any],
    config: HistoricalModelContextConfig,
) -> None:
    _assert_ref(prediction_ref, config.prediction_ref, "prediction")
    _assert_ref(feature_ref, config.feature_ref, "feature")
    _assert_ref(market_ref, config.market_ref, "market")


def build_comparisons(
    predictions: pd.DataFrame,
    features: pd.DataFrame,
    markets: pd.DataFrame,
    *,
    config: HistoricalModelContextConfig,
) -> pd.DataFrame:
    """Return one settled, diagnostic comparison row per 2025 game/target."""
    _require_columns(
        predictions,
        {"season", "game_id", "target", "actual", "v4_prediction", "training_max_year"},
        "predictions",
    )
    _require_columns(features, {"season", "game_id", "week"}, "features")
    _require_columns(
        markets,
        {
            "game_id",
            "spread_line",
            "total_line",
            "market_policy_version",
            "timing_class",
            "usage",
        },
        "markets",
    )
    values = predictions[
        predictions["season"].astype(int).eq(config.comparison_season)
    ].copy()
    if set(values["target"].astype(str)) != set(TARGETS):
        raise HistoricalModelContextError(
            "Predictions must contain exactly spread and total"
        )
    if values.duplicated(["game_id", "target"]).any():
        raise HistoricalModelContextError(
            "Predictions contain duplicate game/target keys"
        )
    if not values["training_max_year"].astype(int).eq(2024).all():
        raise HistoricalModelContextError(
            "2025 historical predictions must train through 2024"
        )
    if values["game_id"].nunique() != 761 or len(values) != 1522:
        raise HistoricalModelContextError(
            "Predictions must contain the pinned 761-game 2025 population"
        )
    weeks = features[features["season"].astype(int).eq(config.comparison_season)][
        ["game_id", "week"]
    ].drop_duplicates()
    if weeks.duplicated("game_id").any():
        raise HistoricalModelContextError("Features contain conflicting game weeks")
    selected_markets = markets[
        [
            "game_id",
            "spread_line",
            "total_line",
            "market_policy_version",
            "timing_class",
            "usage",
        ]
    ].copy()
    if selected_markets.duplicated("game_id").any():
        raise HistoricalModelContextError("Markets contain duplicate game rows")
    if (
        not selected_markets["market_policy_version"]
        .eq(config.market_policy_version)
        .all()
    ):
        raise HistoricalModelContextError(
            "Markets do not use the pinned selection policy"
        )
    if not selected_markets["timing_class"].eq(config.timing_class).all():
        raise HistoricalModelContextError("Markets do not retain reconstructed timing")
    if not selected_markets["usage"].eq(config.usage).all():
        raise HistoricalModelContextError("Markets are not diagnostic-only")
    values = values.merge(weeks, on="game_id", how="left", validate="many_to_one")
    values = values.merge(
        selected_markets, on="game_id", how="left", validate="many_to_one"
    )
    if values[["week", "spread_line", "total_line"]].isna().any().any():
        raise HistoricalModelContextError(
            "Every historical prediction requires a week and both reference lines"
        )
    values["week"] = values["week"].astype(int)
    if (values["week"] <= 0).any() or set(values["week"]) != set(range(1, 16)):
        raise HistoricalModelContextError(
            "2025 context requires exactly Weeks 1-15 and no Week 0"
        )

    spread = values[values["target"].eq("spread")].copy()
    spread["side"] = spread["v4_prediction"] + spread["spread_line"] >= 0
    spread["settlement_margin"] = spread["actual"] + spread["spread_line"]
    spread["result"] = spread.apply(
        lambda row: "push"
        if row["settlement_margin"] == 0
        else "win"
        if bool(row["settlement_margin"] > 0) == bool(row["side"])
        else "loss",
        axis=1,
    )
    spread["direction"] = spread["side"].map({True: "home", False: "away"})

    total = values[values["target"].eq("total")].copy()
    total["side"] = total["v4_prediction"] >= total["total_line"]
    total["settlement_margin"] = total["actual"] - total["total_line"]
    total["result"] = total.apply(
        lambda row: "push"
        if row["settlement_margin"] == 0
        else "win"
        if bool(row["settlement_margin"] > 0) == bool(row["side"])
        else "loss",
        axis=1,
    )
    total["direction"] = total["side"].map({True: "over", False: "under"})
    result = pd.concat([spread, total], ignore_index=True)
    result["model_id"] = config.model_id
    result["comparison_season"] = config.comparison_season
    result["calculation_version"] = CALCULATION_VERSION
    return result.sort_values(["game_id", "target"]).reset_index(drop=True)


def aggregate_periods(comparisons: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        comparisons,
        {
            "week",
            "target",
            "result",
            "model_id",
            "comparison_season",
            "calculation_version",
        },
        "comparisons",
    )
    rows: list[dict[str, Any]] = []
    periods: list[tuple[str, int | None, pd.DataFrame]] = [
        (PERIOD_SEASON, None, comparisons)
    ]
    periods.extend(
        (PERIOD_WEEK, week, frame)
        for week, frame in comparisons.groupby("week", sort=True)
    )
    for scope, week, frame in periods:
        row: dict[str, Any] = {
            "model_id": str(frame["model_id"].iloc[0]),
            "comparison_season": int(frame["comparison_season"].iloc[0]),
            "period_scope": scope,
            "comparison_week": week,
            "calculation_version": str(frame["calculation_version"].iloc[0]),
        }
        for target in TARGETS:
            results = frame.loc[frame["target"].eq(target), "result"]
            row[f"{target}_wins"] = int(results.eq("win").sum())
            row[f"{target}_losses"] = int(results.eq("loss").sum())
            row[f"{target}_pushes"] = int(results.eq("push").sum())
            row[f"{target}_compared_games"] = int(len(results))
        rows.append(row)
    return (
        pd.DataFrame.from_records(rows)
        .sort_values(["period_scope", "comparison_week"], na_position="first")
        .reset_index(drop=True)
    )


def build_audit(
    comparisons: pd.DataFrame,
    aggregates: pd.DataFrame,
    *,
    config: HistoricalModelContextConfig,
) -> dict[str, Any]:
    season = aggregates[aggregates["period_scope"].eq(PERIOD_SEASON)].iloc[0]
    week_two = aggregates[aggregates["comparison_week"].eq(2)].iloc[0]
    checks = {
        "comparison_rows": len(comparisons) == 1522,
        "unique_game_target_keys": not comparisons.duplicated(
            ["game_id", "target"]
        ).any(),
        "game_coverage": comparisons["game_id"].nunique() == 761,
        "no_week_zero": not comparisons["week"].eq(0).any(),
        "season_parity": (
            int(season["spread_wins"]),
            int(season["spread_losses"]),
            int(season["spread_pushes"]),
            int(season["total_wins"]),
            int(season["total_losses"]),
            int(season["total_pushes"]),
        )
        == (379, 366, 16, 398, 358, 5),
        "week_two_parity": (
            int(week_two["spread_wins"]),
            int(week_two["spread_losses"]),
            int(week_two["spread_pushes"]),
            int(week_two["total_wins"]),
            int(week_two["total_losses"]),
            int(week_two["total_pushes"]),
        )
        == (26, 22, 2, 28, 22, 0),
    }
    return {
        "schema_version": "historical_model_context_audit_v1",
        "design_id": config.design_id,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
