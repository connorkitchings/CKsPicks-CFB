"""Independent reconstruction of the outcome-free V5 live bridge output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_COLUMNS,
    LiveForecastContractError,
    validate_prediction_frame,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.lake import canonical_frame_digest

VERIFY_FEATURES = (
    "home_offense",
    "home_defense",
    "away_offense",
    "away_defense",
    "home_host",
    "venue_unknown",
)
VERIFY_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)


class LiveForecastVerificationError(ValueError):
    """Raised when an independently reconstructed live forecast differs."""


def _matrix(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    center = train.loc[:, VERIFY_FEATURES].mean()
    scale = train.loc[:, VERIFY_FEATURES].std(ddof=0).clip(lower=0.05)
    left = (train.loc[:, VERIFY_FEATURES] - center) / scale
    right = (test.loc[:, VERIFY_FEATURES] - center) / scale
    varying = [
        column for column in VERIFY_FEATURES if left[column].nunique(dropna=False) > 1
    ]
    if not varying:
        raise LiveForecastVerificationError("verifier training design is constant")
    return left.loc[:, varying].to_numpy(float), right.loc[:, varying].to_numpy(float)


def reconstruct_predictions(
    historical_features: pd.DataFrame,
    live_features: pd.DataFrame,
    *,
    recipes: Mapping[str, Mapping[str, Any]],
    variances: Mapping[str, float],
    run_id: str,
    model_ref: str,
    state_refs: Mapping[int, str],
    source_ref: str,
) -> pd.DataFrame:
    """Re-fit only the fixed through-2025 recipes and rebuild each live row."""
    if set(historical_features["season"].astype(int)) - set(VERIFY_SEASONS):
        raise LiveForecastVerificationError("verifier historical seasons differ")
    if historical_features["season"].isin((2020, 2026)).any():
        raise LiveForecastVerificationError(
            "verifier training includes a forbidden season"
        )
    if live_features.empty or not live_features["season"].eq(2026).all():
        raise LiveForecastVerificationError(
            "verifier application population is not 2026"
        )
    if set(recipes) != {"margin", "total"} or set(variances) != {"margin", "total"}:
        raise LiveForecastVerificationError(
            "verifier lacks a target recipe or variance"
        )
    rows: list[pd.DataFrame] = []
    training = historical_features[historical_features["season"].isin(VERIFY_SEASONS)]
    for target in ("margin", "total"):
        recipe = recipes[target]
        alpha = float(recipe.get("final_alpha", recipe.get("alpha", float("nan"))))
        variance = float(variances[target])
        if (
            recipe.get("head") not in ("reference", "challenger")
            or not np.isfinite(alpha)
            or alpha <= 0
        ):
            raise LiveForecastVerificationError("verifier model recipe is invalid")
        if not np.isfinite(variance) or variance <= 0:
            raise LiveForecastVerificationError(
                "verifier calibration variance is invalid"
            )
        actual = f"actual_{target}"
        offset = f"offset_{target}"
        clean_train = training.replace([np.inf, -np.inf], np.nan).dropna(
            subset=[actual, offset, *VERIFY_FEATURES]
        )
        clean_live = live_features.replace([np.inf, -np.inf], np.nan).dropna(
            subset=[offset, *VERIFY_FEATURES]
        )
        if len(clean_live) != len(live_features):
            raise LiveForecastVerificationError(
                "verifier live feature frame is incomplete"
            )
        x_train, x_live = _matrix(clean_train, clean_live)
        model = Ridge(alpha=alpha)
        model.fit(
            x_train,
            clean_train[actual].to_numpy(float) - clean_train[offset].to_numpy(float),
        )
        means = model.predict(x_live) + clean_live[offset].to_numpy(float)
        sigma = float(np.sqrt(variance))
        frame = clean_live.loc[:, ["season", "week", "game_id"]].copy()
        frame["run_id"] = run_id
        frame["target"] = target
        frame["mean"] = means
        frame["variance"] = variance
        frame["interval_lower_95"] = means - 1.959963984540054 * sigma
        frame["interval_upper_95"] = means + 1.959963984540054 * sigma
        frame["offset"] = clean_live[offset].to_numpy(float)
        frame["completed_game_stage"] = (
            pd.to_numeric(
                clean_live.get(
                    "completed_game_stage", pd.Series(0, index=clean_live.index)
                ),
                errors="raise",
            )
            .clip(upper=4)
            .astype(int)
            .to_numpy()
        )
        frame["timing_class"] = "live"
        frame["model_ref"] = f"{model_ref}#{target}:{recipe['head']}:{alpha:g}"
        frame["state_ref"] = (
            clean_live["game_id"]
            .map(lambda value: state_refs.get(int(value), ""))
            .to_numpy()
        )
        frame["source_ref"] = source_ref
        rows.append(frame)
    actual = pd.concat(rows, ignore_index=True).loc[:, list(LIVE_FORECAST_COLUMNS)]
    actual = actual.sort_values(
        ["season", "week", "game_id", "target"], kind="mergesort"
    ).reset_index(drop=True)
    try:
        validate_prediction_frame(actual, run_id=run_id)
    except LiveForecastContractError as exc:
        raise LiveForecastVerificationError(str(exc)) from exc
    return actual


def verify_manifest_envelope(
    manifest: Mapping[str, Any], *, raw_sha256: str
) -> dict[str, Any]:
    try:
        verify_signed_payload(manifest, label="live forecast manifest")
    except ValueError as exc:
        raise LiveForecastVerificationError(str(exc)) from exc
    identity = manifest.get("identity") or {}
    parents = manifest.get("parents") or {}
    if (
        manifest.get("schema_version") != "data_first_live_forecast_manifest_v1"
        or manifest.get("state") != "frozen"
        or identity.get("environment") != "preview"
        or identity.get("season") != 2026
        or manifest.get("production_activation_authorized") is not False
        or not raw_sha256
        or not all(
            parents.get(key)
            for key in (
                "measurement_uri",
                "measurement_raw_sha256",
                "rating_replay_uri",
                "rating_replay_raw_sha256",
                "bridge_uri",
                "bridge_raw_sha256",
                "schedule_ref_uri",
                "schedule_raw_sha256",
            )
        )
    ):
        raise LiveForecastVerificationError(
            "live forecast manifest envelope is incomplete"
        )
    identity_parents = identity.get("parents") or {}
    if any(identity_parents.get(key) != parents.get(key) for key in parents):
        raise LiveForecastVerificationError("manifest and identity parents differ")
    return {
        "run_id": str(identity.get("run_id") or ""),
        "prediction_count": int(manifest.get("row_count", 0)),
        "population_sha256": str(manifest.get("population_sha256") or ""),
    }


def verify_predictions(
    *,
    manifest: Mapping[str, Any],
    stored: pd.DataFrame,
    reconstructed: pd.DataFrame,
) -> dict[str, Any]:
    """Confirm complete canonical records and row count against the signed manifest."""
    try:
        validate_prediction_frame(
            stored, run_id=str((manifest.get("identity") or {}).get("run_id"))
        )
    except LiveForecastContractError as exc:
        raise LiveForecastVerificationError(str(exc)) from exc
    if len(stored) != len(reconstructed) or len(stored) != int(
        manifest.get("row_count", -1)
    ):
        raise LiveForecastVerificationError(
            "live forecast prediction row count differs"
        )
    stored_sha = canonical_frame_digest(stored, columns=LIVE_FORECAST_COLUMNS)
    reconstructed_sha = canonical_frame_digest(
        reconstructed, columns=LIVE_FORECAST_COLUMNS
    )
    if stored_sha != reconstructed_sha or stored_sha != manifest.get(
        "prediction_records_sha256"
    ):
        raise LiveForecastVerificationError(
            "live forecast predictions differ from reconstruction"
        )
    return {
        "verified": True,
        "row_count": int(len(stored)),
        "records_sha256": stored_sha,
    }
