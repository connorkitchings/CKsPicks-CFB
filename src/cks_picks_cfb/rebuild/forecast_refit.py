"""Stage: admitted-ledger offsets, the historical feature frame and the alpha-10 refit.

Offsets come from the verified admitted ledger (never the stale baseline offsets), the
feature frame uses the corrected team states, and the bridge is the served recipe: a fixed
alpha-10 Ridge with earlier-only interval calibration. Nothing here sees a 2020 or 2026
row; ``fit_bundle_from_frame`` rejects them.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterator, Mapping
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.rebuild import common, comparison, eligibility, measurements
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput

PREFIX = "rebuild/6a/{run_id}/forecast/"
FRAME_FILES = ("offsets", "offset_team_games", "feature_frame")


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


def frame_digest(frame: pd.DataFrame) -> str:
    hashed = pd.util.hash_pandas_object(frame.reset_index(drop=True), index=False)
    return hashlib.sha256(hashed.to_numpy().tobytes()).hexdigest()


def bundle_sha(bundle: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _staged(context: StageContext, stage: str, key: str) -> bytes:
    return context.read_artifact(stage, key)


def _population(context: StageContext) -> pd.DataFrame:
    """The measurement-ready population, in the form the forecast code always receives."""
    from cks_picks_cfb.data.data_first_possession_v1 import build_population

    prefix = eligibility.PREFIX.format(run_id=context.plan.run_id)
    raw = pd.read_parquet(
        io.BytesIO(_staged(context, "eligibility", prefix + eligibility.POPULATION))
    )
    return build_population(raw, scope="historical")


def _team_states(context: StageContext) -> pd.DataFrame:
    prefix = measurements.PREFIX.format(run_id=context.plan.run_id)
    return pd.read_parquet(
        io.BytesIO(
            _staged(context, "measurements_ratings", prefix + "team_states.parquet")
        )
    )


def _admitted_events(context: StageContext) -> pd.DataFrame:
    prefix = comparison.PREFIX.format(run_id=context.plan.run_id)
    return pd.read_parquet(
        io.BytesIO(
            _staged(
                context,
                "step5_comparison",
                prefix + comparison.FILES["admitted_events"],
            )
        )
    )


def _forecast_config(context: StageContext) -> tuple[dict[str, Any], str]:
    import yaml

    raw = context.read_input("forecast_config")
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.forecast.heads import FEATURES
    from cks_picks_cfb.forecast.historical_features import _feature_frame
    from cks_picks_cfb.forecast.intended_update_bundle import (
        assert_pre2026_frame,
        fit_bundle_from_frame,
    )
    from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
    from cks_picks_cfb.forecast.offsets import build_offsets

    storage = common.preview_storage(context)
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    population = _population(context)
    outcomes = measurements._outcomes(context, storage, pin_file)
    events = _admitted_events(context)
    computation = build_offsets(
        population,
        events,
        development_seasons=tuple(DEVELOPMENT_SEASONS),
        equivalent_games=4,
    )
    eligible = int(population["forecast_eligible"].sum())
    if len(computation.offsets) != eligible:
        raise GateError(f"offsets cover {len(computation.offsets)} of {eligible} games")
    features = _feature_frame(
        population=population,
        outcomes=outcomes,
        team_states=_team_states(context),
        offsets=computation.offsets,
    )
    if len(features) != eligible:
        raise GateError(f"feature frame has {len(features)} rows, expected {eligible}")
    assert_pre2026_frame(features)
    if features[list(FEATURES)].isna().any().any():
        raise GateError("feature frame has missing feature values")
    bundle, counts = fit_bundle_from_frame(features)
    config, config_sha = _forecast_config(context)
    diagnostic = _diagnostic_calibration(features, config)
    summary = {
        "rows": {
            "offsets": int(len(computation.offsets)),
            "offset_team_games": int(len(computation.team_games)),
            "feature_frame": int(len(features)),
        },
        "digests": {
            "offsets": frame_digest(computation.offsets),
            "feature_frame": frame_digest(features),
            "bundle": bundle_sha(bundle),
        },
        "leakage": {
            "seasons": sorted(int(s) for s in features["season"].unique()),
            "max_kickoff_utc": str(
                pd.to_datetime(features["kickoff_utc"], utc=True).max()
            ),
            "forbidden_seasons_present": False,
        },
        "recipe": {"head": "reference", "alpha": 10.0, "calibration": "earlier_only"},
        "calibration_counts": dict(counts),
        "diagnostic_calibration_11c": diagnostic,
        "forecast_config_sha256": config_sha,
        "eligible_games": eligible,
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        yield f"{prefix}offsets.parquet", _parquet(computation.offsets)
        yield f"{prefix}offset_team_games.parquet", _parquet(computation.team_games)
        yield f"{prefix}feature_frame.parquet", _parquet(features)
        yield (
            f"{prefix}bundle.json",
            json.dumps(bundle, sort_keys=True, default=str).encode(),
        )
        yield (
            f"{prefix}summary.json",
            json.dumps(summary, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics=summary["rows"])


def _diagnostic_calibration(
    features: pd.DataFrame, config: Mapping[str, Any]
) -> dict[str, Any]:
    """The 11C calibration variance alongside the served one; reported, never gating."""
    from cks_picks_cfb.forecast.calibration import calibrate_uncertainty
    from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS

    result = calibrate_uncertainty(
        features,
        horizon="expanding",
        development_seasons=tuple(DEVELOPMENT_SEASONS),
        outer_seasons=tuple(config["selection"]["outer_seasons"]),
        alpha_grid=tuple(config["bridge"]["alpha_grid"]),
        floor=float(config["bridge"]["scaling_floor"]),
    )
    return {
        "records": len(result.records),
        "variances": {str(k): v for k, v in dict(result.variances).items()},
    }


def bundle_prediction_problems(
    bundle: Mapping[str, Any], features: pd.DataFrame, fit_one
) -> list[str]:
    """Check the exported bundle against an independent Ridge fit on the same frame."""
    problems: list[str] = []
    train = features
    for target, entry in bundle["targets"].items():
        names = entry["feature_names"]
        center = np.asarray([entry["center"][name] for name in names], dtype=float)
        scale = np.asarray([entry["scale"][name] for name in names], dtype=float)
        coefficients = np.asarray(entry["coefficients"], dtype=float)
        matrix = (train[names].to_numpy(float) - center) / scale
        predicted = float(entry["intercept"]) + (matrix * coefficients).sum(axis=1)
        fitted, _ = fit_one(train, train, target=target, alpha=10.0, floor=0.05)
        if not np.allclose(predicted, np.asarray(fitted, dtype=float), atol=1e-8):
            problems.append(
                f"{target}: bundle predictions differ from an independent fit"
            )
        if entry["training_rows"] != len(train):
            problems.append(f"{target}: training_rows differs from the frame")
        if not entry["calibration_variance"] >= 1e-6:
            problems.append(f"{target}: calibration variance below the floor")
        if not np.isfinite(coefficients).all():
            problems.append(f"{target}: non-finite coefficients")
    return problems


def verify(context: StageContext) -> list[str]:
    from cks_picks_cfb.forecast import forecast_verification as mirror
    from cks_picks_cfb.forecast.heads import FEATURES
    from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS

    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    read = lambda name: _staged(context, stage, prefix + name)  # noqa: E731
    summary = json.loads(read("summary.json"))
    bundle = json.loads(read("bundle.json"))
    offsets = pd.read_parquet(io.BytesIO(read("offsets.parquet")))
    features = pd.read_parquet(io.BytesIO(read("feature_frame.parquet")))
    problems: list[str] = []
    if sorted(int(s) for s in features["season"].unique()) != sorted(
        DEVELOPMENT_SEASONS
    ):
        problems.append("feature frame seasons are not exactly the development seasons")
    if len(features) != summary["eligible_games"] or len(offsets) != len(features):
        problems.append(
            "offset or feature rows differ from the forecast-eligible games"
        )
    if summary["digests"]["bundle"] != bundle_sha(bundle):
        problems.append("bundle digest differs from the summary")
    if bundle.get("feature_order") != list(FEATURES):
        problems.append("bundle feature order changed")
    if bundle.get("development_seasons") != list(DEVELOPMENT_SEASONS):
        problems.append("bundle development seasons changed")

    # Independent recomputation of the offsets from the verified admitted ledger.
    population = _population(context)
    expected = mirror._build_offsets(
        population,
        _admitted_events(context),
        development_seasons=tuple(DEVELOPMENT_SEASONS),
        equivalent_games=4,
    )
    keys = ["season", "week", "game_id"]
    if not comparison.canonical_equal(
        offsets[[*keys, "offset_margin", "offset_total"]],
        expected[[*keys, "offset_margin", "offset_total"]],
    )["equal"]:
        problems.append("offsets differ from the independent recomputation")
    problems += bundle_prediction_problems(bundle, features, mirror._fit_one)
    return problems
