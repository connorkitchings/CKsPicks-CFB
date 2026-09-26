"""Pure, reusable steps for the weekly prediction CLI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from cks_picks_cfb.features.regimes import canonical_prediction_regime
from cks_picks_cfb.models.market_grading import (
    SELECTION_POLICY_VERSION,
    select_best_quote,
)


@dataclass(frozen=True)
class PreparedInferenceInputs:
    """Point-in-time feature and market inputs selected for one weekly run."""

    features: pd.DataFrame
    market_snapshot: pd.DataFrame | None = None
    schedule_snapshot: pd.DataFrame | None = None
    dataset_refs: tuple[Mapping[str, Any], ...] = ()
    market_quotes: pd.DataFrame | None = None


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
    market_quotes: pd.DataFrame | None = None,
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
                "market_captured_at",
                "market_policy_version",
                "spread_selection_rule",
                "total_selection_rule",
                "spread_provider_count",
                "total_provider_count",
                "source_quote_ids",
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
        market_quotes=market_quotes,
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
    market_quotes: pd.DataFrame | None = None,
    allow_default_price: bool = True,
) -> pd.DataFrame:
    """Apply the existing spread-sign, threshold, and lean display contract.

    When ``market_quotes`` is provided, selects the best pre-kickoff quote
    for each target using :func:`select_best_quote`.
    """
    if len(predictions) != len(features):
        raise ValueError("Predictions and feature rows must have identical lengths")

    quotes_by_game: dict[int, list[dict[str, Any]]] = {}
    if market_quotes is not None and not market_quotes.empty:
        for _, q_row in market_quotes.iterrows():
            gid_val = q_row.get("game_id")
            if pd.isna(gid_val):
                continue
            gid = int(gid_val)
            cap = q_row.get("captured_at")
            h_price = q_row.get("home_spread_price")
            a_price = q_row.get("away_spread_price")
            o_price = q_row.get("over_price")
            u_price = q_row.get("under_price")
            quotes_by_game.setdefault(gid, []).append(
                {
                    "quote_id": str(q_row["quote_id"]),
                    "game_id": gid,
                    "captured_at": cap,
                    "spread": (
                        float(q_row["spread"])
                        if q_row.get("spread") is not None
                        and not pd.isna(q_row["spread"])
                        else None
                    ),
                    "total": (
                        float(q_row["total"])
                        if q_row.get("total") is not None
                        and not pd.isna(q_row["total"])
                        else None
                    ),
                    "home_spread_price": (
                        float(h_price)
                        if h_price is not None and not pd.isna(h_price)
                        else None
                    ),
                    "away_spread_price": (
                        float(a_price)
                        if a_price is not None and not pd.isna(a_price)
                        else None
                    ),
                    "over_price": (
                        float(o_price)
                        if o_price is not None and not pd.isna(o_price)
                        else None
                    ),
                    "under_price": (
                        float(u_price)
                        if u_price is not None and not pd.isna(u_price)
                        else None
                    ),
                    "provider": q_row.get("provider"),
                }
            )

    rows: list[dict[str, Any]] = []
    for index, feature in features.reset_index(drop=True).iterrows():
        prediction = predictions.iloc[index]
        spread = float(prediction["predicted_spread"])
        total = float(prediction["predicted_total"])
        game_id = int(feature["id"])
        canonical_spread = feature.get("home_team_spread_line")
        canonical_total = feature.get("total_line")
        snap_id = feature.get("market_snapshot_id")
        start_date_val = feature.get("start_date")
        if start_date_val is not None and not pd.isna(start_date_val):
            start_date_dt = pd.to_datetime(start_date_val, utc=True).to_pydatetime()
        else:
            start_date_dt = datetime.now(timezone.utc)

        raw_sq_ids = feature.get("source_quote_ids", "[]")
        if isinstance(raw_sq_ids, str):
            try:
                source_q_ids = json.loads(raw_sq_ids)
            except Exception:
                source_q_ids = []
        elif isinstance(raw_sq_ids, list):
            source_q_ids = raw_sq_ids
        else:
            source_q_ids = []

        spread_quote_id = None
        spread_quote_price = None
        spread_policy_ver = None
        total_quote_id = None
        total_quote_price = None
        total_policy_ver = None

        if market_quotes is not None and snap_id:
            cands = quotes_by_game.get(game_id, [])
            if source_q_ids:
                linked_ids = set(str(qid) for qid in source_q_ids)
                cands = [c for c in cands if c["quote_id"] in linked_ids]

            spread_cands = [
                {
                    "quote_id": c["quote_id"],
                    "game_id": c["game_id"],
                    "snapshot_id": snap_id,
                    "target": "spread",
                    "point": c["spread"],
                    "captured_at": c["captured_at"],
                    "home_spread_price": c["home_spread_price"],
                    "away_spread_price": c["away_spread_price"],
                }
                for c in cands
                if c["spread"] is not None
            ]
            selected_spread = select_best_quote(
                target="spread",
                prediction=spread,
                canonical_snapshot_id=snap_id,
                canonical_line=(
                    None if pd.isna(canonical_spread) else float(canonical_spread)
                ),
                game_id=game_id,
                kickoff_utc=start_date_dt,
                quote_candidates=spread_cands,
                require_price=not allow_default_price,
            )

            total_cands = [
                {
                    "quote_id": c["quote_id"],
                    "game_id": c["game_id"],
                    "snapshot_id": snap_id,
                    "target": "total",
                    "point": c["total"],
                    "captured_at": c["captured_at"],
                    "over_price": c["over_price"],
                    "under_price": c["under_price"],
                }
                for c in cands
                if c["total"] is not None
            ]
            selected_total = select_best_quote(
                target="total",
                prediction=total,
                canonical_snapshot_id=snap_id,
                canonical_line=(
                    None if pd.isna(canonical_total) else float(canonical_total)
                ),
                game_id=game_id,
                kickoff_utc=start_date_dt,
                quote_candidates=total_cands,
                require_price=not allow_default_price,
            )

            if selected_spread is not None:
                book_spread = selected_spread.point
                spread_edge = selected_spread.edge
                if spread_edge < spread_threshold:
                    spread_bet, confidence = "No Bet", ""
                else:
                    spread_bet = "Home" if selected_spread.side == "home" else "Away"
                    confidence = (
                        "High" if spread_edge >= spread_threshold_high else "Medium"
                    )
                spread_quote_id = selected_spread.quote_id
                spread_quote_price = selected_spread.price
                spread_policy_ver = selected_spread.policy_version
            else:
                book_spread, spread_edge, spread_bet, confidence = (
                    None,
                    0.0,
                    "No Bet",
                    "",
                )

            if selected_total is not None:
                book_total = selected_total.point
                total_edge = selected_total.edge
                if total_edge < total_threshold:
                    total_bet = "No Bet"
                else:
                    total_bet = "Over" if selected_total.side == "over" else "Under"
                total_quote_id = selected_total.quote_id
                total_quote_price = selected_total.price
                total_policy_ver = selected_total.policy_version
            else:
                book_total, total_edge, total_bet = None, 0.0, "No Bet"
        else:
            book_spread, book_total = (
                canonical_spread,
                canonical_total,
            )
            spread_edge = (
                0.0 if pd.isna(book_spread) else abs(spread + float(book_spread))
            )
            if pd.isna(book_spread) or spread_edge < spread_threshold:
                spread_bet, confidence = "No Bet", ""
            else:
                spread_bet = "Home" if spread + float(book_spread) > 0 else "Away"
                confidence = (
                    "High" if spread_edge >= spread_threshold_high else "Medium"
                )
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
                "spread_market_quote_id": spread_quote_id,
                "total_market_quote_id": total_quote_id,
                "spread_market_quote_price": spread_quote_price,
                "total_market_quote_price": total_quote_price,
                "market_selection_policy": spread_policy_ver or total_policy_ver,
                "canonical_spread_line": canonical_spread,
                "canonical_total_line": canonical_total,
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
            "best_quote_selection_policy": (
                SELECTION_POLICY_VERSION
                if "spread_market_quote_id" in results
                and results["spread_market_quote_id"].notna().any()
                else None
            ),
            "selected_quotes_count": int(
                results[["spread_market_quote_id", "total_market_quote_id"]]
                .notna()
                .sum()
                .sum()
            )
            if {"spread_market_quote_id", "total_market_quote_id"}
            <= set(results.columns)
            else 0,
        },
    }
