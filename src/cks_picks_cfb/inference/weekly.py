"""Pure, reusable steps for the weekly prediction CLI."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from cks_picks_cfb.features.regimes import canonical_prediction_regime


@dataclass(frozen=True)
class PreparedInferenceInputs:
    """Point-in-time feature and market inputs selected for one weekly run."""

    features: pd.DataFrame
    market_snapshot: pd.DataFrame | None = None
    schedule_snapshot: pd.DataFrame | None = None
    dataset_refs: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class InferenceModelContext:
    """Loaded model/bundle metadata needed to produce reproducible predictions."""

    bundle: Any | None
    bundle_version: str | None
    model_bundle_sha256: str
    spread_model: Any | None = None
    total_model: Any | None = None
    spread_model_version: str = "unknown"
    total_model_version: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)


def load_inference_model_context(
    *,
    bundle: Any | None,
    bundle_version: str | None,
    spread_model: Any | None = None,
    total_model: Any | None = None,
    spread_model_version: str = "unknown",
    total_model_version: str = "unknown",
    metadata: Mapping[str, Any] | None = None,
) -> InferenceModelContext:
    """Normalize already-loaded bundle or compatibility models into one context."""
    if bundle is not None and bundle_version not in {"v2", "v3"}:
        raise ValueError("A routing bundle must declare version 'v2' or 'v3'")
    if bundle is None and bundle_version is not None:
        raise ValueError("A bundle version requires a routing bundle")
    bundle_sha = (
        str(bundle.manifest_sha256)
        if bundle is not None and hasattr(bundle, "manifest_sha256")
        else hashlib.sha256(
            f"{spread_model_version}:{total_model_version}".encode("utf-8")
        ).hexdigest()
    )
    return InferenceModelContext(
        bundle=bundle,
        bundle_version=bundle_version,
        model_bundle_sha256=bundle_sha,
        spread_model=spread_model,
        total_model=total_model,
        spread_model_version=spread_model_version,
        total_model_version=total_model_version,
        metadata=metadata or {},
    )


def prepare_inference_features(
    features: pd.DataFrame,
    *,
    year: int,
    week: int,
    market_snapshot: pd.DataFrame | None = None,
    schedule_snapshot: pd.DataFrame | None = None,
    dataset_refs: Sequence[Mapping[str, Any]] = (),
) -> PreparedInferenceInputs:
    """Filter one point-in-time Gold frame and merge its latest market snapshot."""
    result = features[
        (features["season"].astype(int) == int(year))
        & (features["week"].astype(int) == int(week))
    ].copy()
    if result.empty:
        raise ValueError(f"Gold dataset has no rows for {year} week {week}")
    if market_snapshot is not None and not market_snapshot.empty:
        market = market_snapshot.copy()
        captured_columns = [
            column
            for column in ("market_captured_at", "captured_at")
            if column in market
        ]
        if captured_columns:
            market = market.sort_values(captured_columns)
        market = market.drop_duplicates("game_id", keep="last").rename(
            columns={
                "spread_line": "home_team_spread_line",
                "spread": "home_team_spread_line",
                "total": "total_line",
            }
        )
        columns = [
            column
            for column in (
                "game_id",
                "home_team_spread_line",
                "total_line",
                "market_snapshot_id",
            )
            if column in market
        ]
        result = result.drop(
            columns=[column for column in columns if column != "game_id"],
            errors="ignore",
        ).merge(market[columns], on="game_id", how="left")
    if "id" not in result and "game_id" in result:
        result = result.rename(columns={"game_id": "id"})
    _validate_expected_coverage(result, schedule_snapshot, year=year, week=week)
    return PreparedInferenceInputs(
        features=result,
        market_snapshot=market_snapshot,
        schedule_snapshot=schedule_snapshot,
        dataset_refs=tuple(dataset_refs),
    )


def _validate_expected_coverage(
    features: pd.DataFrame,
    schedule_snapshot: pd.DataFrame | None,
    *,
    year: int,
    week: int,
) -> None:
    if schedule_snapshot is None:
        return
    schedule_week = schedule_snapshot[
        (schedule_snapshot["season"].astype(int) == int(year))
        & (schedule_snapshot["week"].astype(int) == int(week))
    ]
    expected = set(pd.to_numeric(schedule_week["game_id"], errors="raise").astype(int))
    actual = set(pd.to_numeric(features["id"], errors="raise").astype(int))
    if expected != actual:
        missing, unexpected = sorted(expected - actual), sorted(actual - expected)
        raise RuntimeError(
            "FBS-vs-FBS prediction coverage mismatch: "
            f"missing={missing[:10]} unexpected={unexpected[:10]}"
        )


def execute_regime_routing(
    model_context: InferenceModelContext,
    prepared_inputs: PreparedInferenceInputs,
    *,
    bundle_predictor: Callable[[Any, pd.DataFrame], pd.DataFrame] | None = None,
    legacy_predictor: Callable[[pd.DataFrame], tuple[Sequence[float], Sequence[float]]]
    | None = None,
) -> pd.DataFrame:
    """Produce a normalized prediction frame from a bundle or compatibility model."""
    features = prepared_inputs.features.copy()
    if model_context.bundle is not None:
        if bundle_predictor is None:
            raise ValueError("Bundle inference requires bundle_predictor")
        if model_context.bundle_version == "v3":
            features["prediction_regime"] = features["prediction_regime"].map(
                canonical_prediction_regime
            )
        routed = bundle_predictor(model_context.bundle, features)
        return pd.DataFrame(
            {
                "predicted_spread": routed["predicted_spread"].to_numpy(),
                "predicted_total": routed["predicted_total"].to_numpy(),
                "spread_model_version": routed["spread_model_version"].to_numpy(),
                "total_model_version": routed["total_model_version"].to_numpy(),
                "high_confidence_eligible": (
                    routed["spread_high_confidence_eligible"]
                    & routed["total_high_confidence_eligible"]
                ).to_numpy(),
            }
        )
    if legacy_predictor is None:
        raise ValueError("Compatibility inference requires legacy_predictor")
    spread, total = legacy_predictor(features)
    return pd.DataFrame(
        {
            "predicted_spread": spread,
            "predicted_total": total,
            "spread_model_version": model_context.spread_model_version,
            "total_model_version": model_context.total_model_version,
            "high_confidence_eligible": True,
        }
    )


def calculate_edges_and_leans(
    predictions: pd.DataFrame,
    features: pd.DataFrame,
    *,
    spread_threshold: float,
    spread_threshold_high: float,
    total_threshold: float,
    run_id: str,
) -> pd.DataFrame:
    """Apply the existing spread-sign, threshold, and lean display contract."""
    if len(predictions) != len(features):
        raise ValueError("Predictions and feature rows must have identical lengths")
    rows: list[dict[str, Any]] = []
    for index, feature in features.reset_index(drop=True).iterrows():
        prediction = predictions.iloc[index]
        spread = float(prediction["predicted_spread"])
        total = float(prediction["predicted_total"])
        book_spread, book_total = (
            feature.get("home_team_spread_line"),
            feature.get("total_line"),
        )
        spread_edge = 0.0 if pd.isna(book_spread) else abs(spread + float(book_spread))
        if pd.isna(book_spread) or spread_edge < spread_threshold:
            spread_bet, confidence = "No Bet", ""
        else:
            spread_bet = "Home" if spread + float(book_spread) > 0 else "Away"
            confidence = "High" if spread_edge >= spread_threshold_high else "Medium"
        if pd.isna(book_total):
            total_edge, total_bet = 0.0, "No Bet"
        else:
            total_delta = total - float(book_total)
            total_edge = abs(total_delta)
            total_bet = (
                "Over"
                if total_delta > total_threshold
                else "Under"
                if total_delta < -total_threshold
                else "No Bet"
            )
        home_count = pd.to_numeric(
            feature.get("home_current_season_games", 0), errors="coerce"
        )
        away_count = pd.to_numeric(
            feature.get("away_current_season_games", 0), errors="coerce"
        )
        rows.append(
            {
                "game_id": feature["id"],
                "Game": f"{feature['away_team']} @ {feature['home_team']}",
                "Spread Bet": spread_bet,
                "home_team_spread_line": book_spread,
                "Spread Prediction": spread,
                "edge_spread": spread_edge,
                "Spread Confidence": confidence,
                "total_line": book_total,
                "Total Prediction": total,
                "edge_total": total_edge,
                "Total Bet": total_bet,
                "high_confidence_eligible": bool(
                    prediction["high_confidence_eligible"]
                ),
                "home_completed_games": 0 if pd.isna(home_count) else int(home_count),
                "away_completed_games": 0 if pd.isna(away_count) else int(away_count),
                "prediction_regime": feature.get("prediction_regime", "established"),
                "spread_model_version": prediction["spread_model_version"],
                "total_model_version": prediction["total_model_version"],
                "market_snapshot_id": feature.get("market_snapshot_id"),
                "market_policy_version": feature.get("market_policy_version"),
                "spread_selection_rule": feature.get("spread_selection_rule"),
                "total_selection_rule": feature.get("total_selection_rule"),
                "spread_provider_count": feature.get("spread_provider_count", 0),
                "total_provider_count": feature.get("total_provider_count", 0),
                "source_quote_ids": feature.get("source_quote_ids", "[]"),
                "market_captured_at": feature.get("market_captured_at"),
                "run_id": run_id,
            }
        )
    result = pd.DataFrame(rows).merge(
        features[["id", "start_date", "home_team", "away_team"]],
        left_on="game_id",
        right_on="id",
        how="left",
    )
    result["Date"] = pd.to_datetime(result["start_date"]).dt.strftime("%Y-%m-%d")
    result["Time"] = pd.to_datetime(result["start_date"]).dt.strftime("%H:%M:%S")
    result["Home Team"], result["Away Team"] = result["home_team"], result["away_team"]
    result["predicted_spread_std_dev"] = np.nan
    result["predicted_total_std_dev"] = np.nan
    return result


def build_publication_manifest(
    results: pd.DataFrame,
    *,
    state: str,
    data_as_of: str,
    feature_snapshot_uri: str,
    feature_snapshot_sha256: str,
    code_sha: str,
    config_bytes: bytes,
    model_context: InferenceModelContext,
    prepared_inputs: PreparedInferenceInputs,
    source_config: str,
    system_name: str,
    model_id: str,
) -> dict[str, Any]:
    """Build the immutable run manifest without performing any storage I/O."""
    lined_games = int(
        results[["home_team_spread_line", "total_line"]].notna().all(axis=1).sum()
    )
    return {
        "state": state,
        "data_as_of": data_as_of,
        "feature_snapshot_uri": feature_snapshot_uri,
        "feature_snapshot_sha256": feature_snapshot_sha256,
        "expected_games": int(len(prepared_inputs.features)),
        "predicted_games": int(
            results[["Spread Prediction", "Total Prediction"]].notna().all(axis=1).sum()
        ),
        "lined_games": lined_games,
        "code_sha": code_sha,
        "config_sha": hashlib.sha256(config_bytes).hexdigest(),
        "model_bundle_sha256": model_context.model_bundle_sha256,
        "input_dataset_refs": list(prepared_inputs.dataset_refs),
        "source_config": source_config,
        "system_name": system_name,
        "model_id": model_id,
        "validation": {
            "all_predictions_present": bool(
                results[["Spread Prediction", "Total Prediction"]]
                .notna()
                .all(axis=None)
            ),
            "line_coverage_complete": lined_games == len(prepared_inputs.features),
        },
    }
