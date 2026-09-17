#!/usr/bin/env python3
"""Read-only V5-04A forecast-offset, bridge, and horizon preflight.

This runner is deliberately incapable of publishing.  V5-04B owns calibration,
immutable child writes, candidate manifests, and independent verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_DATASETS,
    FORECAST_MODEL_COLUMNS,
    FORECAST_PREDICTION_COLUMNS,
    FORECAST_REGISTRY_COLUMNS,
    FORECAST_SELECTION_COLUMNS,
    REQUIRED_RATING_CANDIDATE,
    WINDOW_COMPARISON_COLUMNS,
    forecast_identity,
    validate_config,
    verify_rating_parent,
)
from cks_picks_cfb.data.data_first_possession_rating_v1 import TEAM_STATE_COLUMNS
from cks_picks_cfb.data.lake import (
    canonical_frame_digest,
    partition_order_key,
    partitioned_records_sha,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.heads import evaluate_heads
from cks_picks_cfb.forecast.horizons import select_horizon
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _concat_frames,
    _manifest_parts,
    _partitioned_ref,
    _read_child,
    _stream_output,
    load_rating_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/forecast_v1.yaml"


class ForecastRunError(ValueError):
    """Raised before a V5-04A preflight could produce reviewable evidence."""


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise ForecastRunError(f"unreadable manifest: {uri}") from exc


def _stream_partitioned(
    storage: Any, *, value: Mapping[str, Any], dataset: str, schema: str
) -> pd.DataFrame:
    ref = _partitioned_ref(value, name=dataset)
    if ref.dataset != dataset or ref.schema_version != schema:
        raise ForecastRunError(f"retained rating output identity mismatch: {dataset}")
    _, parts = _manifest_parts(storage, ref)
    frames = [
        _read_child(storage, dataset=dataset, schema_version=schema, part=part)
        for part in parts
    ]
    return (
        _concat_frames(frames, columns=list(TEAM_STATE_COLUMNS))
        if frames
        else pd.DataFrame()
    )


def _feature_frame(
    *,
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
) -> pd.DataFrame:
    games = population[population["forecast_eligible"].astype(bool)].merge(
        outcomes[outcomes["completed"].astype(bool)],
        on=["season", "game_id"],
        how="inner",
        validate="one_to_one",
    )
    selected = team_states[
        team_states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE)
    ].copy()
    home = selected.rename(
        columns={
            "team": "home_team",
            "offense_rating": "home_offense",
            "defense_rating": "home_defense",
            "completed_games": "home_completed",
        }
    )
    away = selected.rename(
        columns={
            "team": "away_team",
            "offense_rating": "away_offense",
            "defense_rating": "away_defense",
            "completed_games": "away_completed",
        }
    )
    frame = games.merge(
        home[
            [
                "season",
                "game_id",
                "home_team",
                "home_offense",
                "home_defense",
                "home_completed",
            ]
        ],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away[
            [
                "season",
                "game_id",
                "away_team",
                "away_offense",
                "away_defense",
                "away_completed",
            ]
        ],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        offsets, on=["season", "week", "game_id"], how="inner", validate="one_to_one"
    )
    frame["home_host"] = 1.0
    frame["venue_unknown"] = True
    frame["actual_margin"] = frame["home_points"].astype(float) - frame[
        "away_points"
    ].astype(float)
    frame["actual_total"] = frame["home_points"].astype(float) + frame[
        "away_points"
    ].astype(float)
    frame["completed_game_stage"] = (
        frame[["home_completed", "away_completed"]]
        .min(axis=1)
        .clip(upper=4)
        .astype(int)
    )
    return frame


def _plan(
    name: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    partition_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Record deterministic compact or bounded partition membership without writes."""
    if not partition_keys:
        return {
            "name": name,
            "partition_keys": [],
            "parts": [],
            "row_count": len(frame),
            "records_sha": canonical_frame_digest(frame, columns=columns),
        }
    parts: list[dict[str, Any]] = []
    for values, group in frame.groupby(list(partition_keys), sort=True, dropna=False):
        values = values if isinstance(values, tuple) else (values,)
        partition = {
            key: value.item() if hasattr(value, "item") else value
            for key, value in zip(partition_keys, values, strict=True)
        }
        parts.append(
            {
                "partition": partition,
                "row_count": len(group),
                "records_sha": canonical_frame_digest(group, columns=columns),
            }
        )
    parts.sort(key=lambda item: partition_order_key(item["partition"]))
    return {
        "name": name,
        "partition_keys": list(partition_keys),
        "parts": parts,
        "row_count": len(frame),
        "records_sha": partitioned_records_sha(parts, partition_keys),
    }


def preflight(*, storage: Any, args: argparse.Namespace) -> dict[str, Any]:
    config = yaml.safe_load(Path(args.config).read_text())
    validate_config(config)
    rating, rating_raw = _read_json(storage, args.rating_manifest_uri)
    measurement, measurement_raw = _read_json(storage, args.measurement_manifest_uri)
    repair, repair_raw = _read_json(storage, args.repair_manifest_uri)
    parents = verify_rating_parent(
        rating,
        rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
        measurement=measurement,
        measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair=repair,
        repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )
    identity = forecast_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        parents={
            key: parents[key]
            for key in (
                "rating_raw_sha256",
                "measurement_raw_sha256",
                "repair_raw_sha256",
            )
        },
    )
    # Reuse 03's audited source loading.  It validates bounded parent parts and
    # chronology before any forecast feature is formed.
    rating_inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=lambda *_a, **_k: None,
    )
    scoring_events = _stream_output(
        storage,
        name="scoring_events",
        value=measurement["output_refs"]["scoring_events"],
        progress=lambda *_a, **_k: None,
    )
    team_states = _stream_partitioned(
        storage,
        value=rating["output_refs"]["team_states"],
        dataset="possession_team_state",
        schema="data_first_possession_team_state_v1",
    )
    offsets = build_offsets(
        rating_inputs.population,
        scoring_events,
        development_seasons=tuple(config["development_seasons"]),
        equivalent_games=int(config["offsets"]["equivalent_games"]),
    )
    features = _feature_frame(
        population=rating_inputs.population,
        outcomes=rating_inputs.outcomes,
        team_states=team_states,
        offsets=offsets.offsets,
    )
    bridge = config["bridge"]
    selection = config["selection"]
    computations = {
        horizon: evaluate_heads(
            features,
            horizon=horizon,
            development_seasons=tuple(config["development_seasons"]),
            outer_seasons=tuple(selection["outer_seasons"]),
            alpha_grid=tuple(bridge["alpha_grid"]),
            floor=float(bridge["scaling_floor"]),
            bootstrap_seed=int(selection["bootstrap_seed"]),
            bootstrap_samples=int(selection["bootstrap_replicates"]),
        )
        for horizon in config["horizons"]
    }
    retained = {
        horizon: computation.predictions.merge(
            pd.DataFrame(
                [
                    {"target": target, "head": head}
                    for target, head in computation.retained.items()
                ]
            ),
            on=["target", "head"],
            how="inner",
            validate="many_to_one",
        )
        for horizon, computation in computations.items()
    }
    selected_horizon, comparison = select_horizon(
        retained["expanding"],
        retained["latest_five"],
        seed=int(selection["bootstrap_seed"]),
        samples=int(selection["bootstrap_replicates"]),
    )
    predictions = retained[selected_horizon].copy()
    models = computations[selected_horizon].models.copy()
    registry = pd.DataFrame.from_records(
        [
            {
                "horizon": horizon,
                "target": target,
                "reference_alpha": 10.0,
                "alpha_grid": ",".join(map(str, bridge["alpha_grid"])),
            }
            for horizon in config["horizons"]
            for target in ("margin", "total")
        ]
    )
    horizon_sha = hashlib.sha256(
        comparison.to_json(
            orient="records", date_format="iso", double_precision=15
        ).encode()
    ).hexdigest()
    selection_frame = pd.DataFrame.from_records(
        [
            {
                "selected_horizon": selected_horizon,
                "target": target,
                "selected_head": computations[selected_horizon].retained[target],
                "selection_reason": "latest_five_gates_passed"
                if selected_horizon == "latest_five"
                else "retain_expanding",
                "horizon_sha256": horizon_sha,
            }
            for target in ("margin", "total")
        ]
    )
    outputs = {
        "forecast_registry": (registry, FORECAST_REGISTRY_COLUMNS, ()),
        "forecast_model": (
            models,
            FORECAST_MODEL_COLUMNS,
            ("horizon", "outer_season"),
        ),
        "forecast_prediction": (
            predictions,
            FORECAST_PREDICTION_COLUMNS,
            ("season", "week"),
        ),
        "window_comparison": (comparison, WINDOW_COMPARISON_COLUMNS, ()),
        "forecast_selection": (selection_frame, FORECAST_SELECTION_COLUMNS, ()),
    }
    for name, (frame, _columns, _keys) in outputs.items():
        dataset, schema = FORECAST_DATASETS[name]
        validate_frame(frame, schema_for(dataset, schema))
    plans = {
        name: _plan(name, frame, columns, keys)
        for name, (frame, columns, keys) in outputs.items()
    }
    return {
        "state": "dry_run",
        "identity": identity,
        "rating_parent": rating["identity"]["run_id"],
        "measurement_parent": measurement["identity"]["run_id"],
        "repair_parent": repair["identity"]["run_id"],
        "offsets_sha256": canonical_frame_digest(
            offsets.offsets, columns=tuple(offsets.offsets.columns)
        ),
        "head_metrics": {
            horizon: {
                target: {
                    "head": computation.retained[target],
                    "mae": float(
                        computation.predictions[
                            (computation.predictions["target"].eq(target))
                            & (
                                computation.predictions["head"].eq(
                                    computation.retained[target]
                                )
                            )
                        ].absolute_error.mean()
                    ),
                }
                for target in ("margin", "total")
            }
            for horizon, computation in computations.items()
        },
        "selected_horizon": selected_horizon,
        "horizon_sha256": horizon_sha,
        "preflight_plans": plans,
        "row_counts": {name: value["row_count"] for name, value in plans.items()},
        "output_records_sha256": {
            name: value["records_sha"] for name, value in plans.items()
        },
        "calibration": {"state": "deferred_to_v5_04b"},
        "production_activation_authorized": False,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--v4-benchmark-manifest-uri")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply:
        raise ForecastRunError("--apply is blocked by V5-04B")
    if _git_sha() != args.expected_code_sha:
        raise ForecastRunError("expected code SHA does not match committed HEAD")
    print(
        json.dumps(
            preflight(storage=get_storage(environment="preview"), args=args),
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
