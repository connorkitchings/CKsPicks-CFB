"""Convert independently verified V5 live forecasts to weekly serving rows."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LiveForecastContractError,
    validate_prediction_frame,
)
from cks_picks_cfb.inference.weekly import (
    calculate_edges_and_leans,
    prepare_inference_features,
)


class V5ServingError(ValueError):
    """A V5 forecast cannot safely enter the weekly serving format."""


def build_v5_serving_rows(
    forecasts: pd.DataFrame,
    schedule: pd.DataFrame,
    forecast_schedule: pd.DataFrame,
    markets: pd.DataFrame | None,
    *,
    forecast_run_id: str,
    forecast_manifest_sha256: str,
    year: int,
    week: int,
    as_of: str,
    run_id: str,
    spread_threshold: float,
    spread_threshold_high: float,
    total_threshold: float,
) -> pd.DataFrame:
    """Require one pregame margin/total pair for every scheduled serving game.

    ``schedule`` is the same explicit FBS-vs-FBS snapshot used by the weekly
    pipeline. Market lines affect only post-model display decisions.
    """
    if year != 2026 or not forecast_manifest_sha256 or not forecast_run_id:
        raise V5ServingError("V5 serving requires a bound 2026 forecast identity")
    try:
        validate_prediction_frame(forecasts, run_id=forecast_run_id)
    except LiveForecastContractError as exc:
        raise V5ServingError(str(exc)) from exc
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise V5ServingError("V5 serving cutoff must be timezone-aware")
    cutoff = cutoff.tz_convert("UTC")
    required = {"season", "week", "game_id", "home_team", "away_team", "start_date"}
    if missing := sorted(required - set(schedule)):
        raise V5ServingError(f"serving schedule lacks columns: {missing}")
    slate = schedule.loc[schedule["season"].eq(year) & schedule["week"].eq(week)].copy()
    if (
        slate.empty
        or slate["game_id"].isna().any()
        or slate.duplicated("game_id").any()
    ):
        raise V5ServingError("serving schedule is empty or duplicates a game")
    kickoff = pd.to_datetime(slate["start_date"], utc=True, errors="raise")
    if kickoff.le(cutoff).any():
        raise V5ServingError("V5 serving schedule includes a game at or before cutoff")
    source_required = {
        "season",
        "week",
        "game_id",
        "home_team",
        "away_team",
        "kickoff_utc",
    }
    if missing := sorted(source_required - set(forecast_schedule)):
        raise V5ServingError(f"forecast parent schedule lacks columns: {missing}")
    source_slate = forecast_schedule.loc[
        forecast_schedule["season"].eq(year) & forecast_schedule["week"].eq(week)
    ].set_index("game_id")
    for game in slate.itertuples(index=False):
        if game.game_id not in source_slate.index:
            raise V5ServingError("serving game is absent from forecast parent schedule")
        source = source_slate.loc[game.game_id]
        if isinstance(source, pd.DataFrame):
            raise V5ServingError("forecast parent schedule duplicates a serving game")
        source_kickoff = pd.to_datetime(source["kickoff_utc"], utc=True)
        serving_kickoff = pd.to_datetime(game.start_date, utc=True)
        if (
            str(source["home_team"]) != str(game.home_team)
            or str(source["away_team"]) != str(game.away_team)
            or source_kickoff != serving_kickoff
        ):
            raise V5ServingError("serving schedule differs from forecast parent")
    if markets is not None and not markets.empty:
        markets = markets.loc[markets["game_id"].isin(slate["game_id"])].copy()
        captured_columns = [
            column
            for column in ("market_captured_at", "captured_at")
            if column in markets
        ]
        if not markets.empty and not captured_columns:
            raise V5ServingError("market snapshot lacks a capture timestamp")
        for column in captured_columns:
            captures = pd.to_datetime(markets[column], utc=True, errors="coerce")
            if captures.isna().any() or captures.gt(cutoff).any():
                raise V5ServingError("market snapshot lacks a valid pre-cutoff capture")
    selected = forecasts.loc[
        forecasts["season"].eq(year) & forecasts["week"].eq(week)
    ].copy()
    expected = set(pd.to_numeric(slate["game_id"], errors="raise").astype(int))
    actual = set(pd.to_numeric(selected["game_id"], errors="raise").astype(int))
    if expected != actual or len(selected) != 2 * len(expected):
        raise V5ServingError(
            f"V5 serving coverage mismatch: missing={sorted(expected - actual)} "
            f"unexpected={sorted(actual - expected)}"
        )
    pairs = selected.pivot(
        index="game_id", columns="target", values=["mean", "variance"]
    )
    if pairs.isna().any().any() or set(pairs["mean"]) != {"margin", "total"}:
        raise V5ServingError("V5 serving requires complete margin and total pairs")
    prepared = prepare_inference_features(
        slate.assign(id=slate["game_id"]),
        year=year,
        week=week,
        market_snapshot=markets,
        schedule_snapshot=slate,
    )
    features = prepared.features.reset_index(drop=True)
    pairs = pairs.loc[pd.to_numeric(features["id"], errors="raise").astype(int)]
    model_version = f"v5:{forecast_run_id}:{forecast_manifest_sha256[:12]}"
    predictions = pd.DataFrame(
        {
            "predicted_spread": pairs[("mean", "margin")].to_numpy(float),
            "predicted_total": pairs[("mean", "total")].to_numpy(float),
            "spread_model_version": model_version,
            "total_model_version": model_version,
            "high_confidence_eligible": False,
        }
    )
    if (
        not np.isfinite(predictions[["predicted_spread", "predicted_total"]])
        .all()
        .all()
    ):
        raise V5ServingError("V5 serving predictions must be finite")
    rows = calculate_edges_and_leans(
        predictions,
        features,
        spread_threshold=spread_threshold,
        spread_threshold_high=spread_threshold_high,
        total_threshold=total_threshold,
        run_id=run_id,
    )
    rows["predicted_spread_std_dev"] = np.sqrt(
        pairs[("variance", "margin")].to_numpy(float)
    )
    rows["predicted_total_std_dev"] = np.sqrt(
        pairs[("variance", "total")].to_numpy(float)
    )
    rows["forecast_manifest_sha256"] = forecast_manifest_sha256
    rows["forecast_run_id"] = forecast_run_id
    return rows


def v5_serving_manifest_fields(
    *, manifest_uri: str, manifest_raw: bytes, verification: Mapping[str, Any]
) -> dict[str, Any]:
    if verification.get("verified") is not True:
        raise V5ServingError("V5 source forecast lacks independent verification")
    digest = hashlib.sha256(manifest_raw).hexdigest()
    return {
        "v5_live_forecast_manifest_uri": manifest_uri,
        "v5_live_forecast_manifest_sha256": digest,
        "v5_verification_records_sha256": verification.get("records_sha256"),
    }
