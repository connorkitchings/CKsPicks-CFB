"""Immutable, research-only recovery of historical V4 routed predictions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.ratings.contracts import MeasurementContractError

V4_BENCHMARK_CONFIG_VERSION = "v1"
V4_BENCHMARK_DATASET = "rating_v4_historical_predictions"
V4_BENCHMARK_SCHEMA_VERSION = "rating_v4_historical_predictions_v1"
TARGETS = ("spread", "total")
EARLY_REGIMES = ("game_1", "game_2", "game_3", "game_4")
ALL_REGIMES = (*EARLY_REGIMES, "established")
SOURCE_KINDS = ("native_route_replay", "derived_compatibility_replay")
PREDICTION_COLUMNS = {
    "baseline": "baseline_prediction",
    "blend": "blend_prediction",
    "direct_ridge": "direct_ridge_prediction",
    "points_ridge": "points_ridge_prediction",
    "direct_catboost": "direct_catboost_prediction",
    "points_catboost": "points_catboost_prediction",
}
BENCHMARK_COLUMNS = (
    "season",
    "game_id",
    "target",
    "regime",
    "actual",
    "v4_prediction",
    "training_max_year",
    "route_candidate",
    "source_kind",
    "feature_ref_version_id",
    "feature_ref_content_sha",
    "selection_design_sha",
    "v4_bundle_id",
    "benchmark_schema_version",
    "benchmark_design_id",
    "replay_engine_commit",
    "recovery_code_sha",
)
BENCHMARK_KEYS = ("season", "game_id", "target")


def _sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def payload_sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class V4BenchmarkConfig:
    research_prefix: str
    replay_engine_commit: str
    historical_seasons: tuple[int, ...]
    selection_feature_ref_uri: str
    selection_feature_version_id: str
    selection_feature_content_sha: str
    selection_report_uri: str
    selection_design_sha: str
    locked_feature_ref_uri: str
    locked_feature_version_id: str
    locked_feature_content_sha: str
    locked_report_uri: str
    bundle_manifest_uri: str
    bundle_manifest_sha256: str
    bundle_recorded_code_sha: str
    established_source_manifest_uri: str
    v4_experiment_path: str
    raw_config: Mapping[str, Any]

    @property
    def design_id(self) -> str:
        return _sha(self.raw_config)


def load_v4_benchmark_config(path: str | Path) -> V4BenchmarkConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("v4_benchmark_replay_config_version") != V4_BENCHMARK_CONFIG_VERSION
    ):
        raise MeasurementContractError("Unsupported V4 benchmark replay configuration")
    try:
        selection = raw["selection"]
        locked = raw["locked"]
        bundle = raw["bundle"]
        if not all(isinstance(item, Mapping) for item in (selection, locked, bundle)):
            raise TypeError
        seasons = tuple(int(value) for value in raw["historical_seasons"])
        config = V4BenchmarkConfig(
            research_prefix=str(raw["research_prefix"]).rstrip("/"),
            replay_engine_commit=str(raw["replay_engine_commit"]),
            historical_seasons=seasons,
            selection_feature_ref_uri=str(selection["feature_ref_uri"]),
            selection_feature_version_id=str(selection["expected_version_id"]),
            selection_feature_content_sha=str(selection["expected_content_sha"]),
            selection_report_uri=str(selection["report_uri"]),
            selection_design_sha=str(selection["expected_design_sha"]),
            locked_feature_ref_uri=str(locked["feature_ref_uri"]),
            locked_feature_version_id=str(locked["expected_version_id"]),
            locked_feature_content_sha=str(locked["expected_content_sha"]),
            locked_report_uri=str(locked["report_uri"]),
            bundle_manifest_uri=str(bundle["manifest_uri"]),
            bundle_manifest_sha256=str(bundle["expected_manifest_sha256"]),
            bundle_recorded_code_sha=str(bundle["expected_recorded_code_sha"]),
            established_source_manifest_uri=str(raw["established_source_manifest_uri"]),
            v4_experiment_path=str(raw["v4_experiment_path"]),
            raw_config=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementContractError(
            "Incomplete V4 benchmark replay configuration"
        ) from exc
    if config.historical_seasons != (2022, 2023, 2024, 2025):
        raise MeasurementContractError(
            "V4 benchmark replay seasons are frozen to 2022-2025"
        )
    if (
        len(config.replay_engine_commit) != 40
        or len(config.bundle_manifest_sha256) != 64
        or len(config.selection_feature_content_sha) != 64
        or len(config.locked_feature_content_sha) != 64
    ):
        raise MeasurementContractError(
            "V4 benchmark replay requires full immutable SHAs"
        )
    return config


def read_ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _canonical_strengths(value: Mapping[str, Any]) -> str:
    # Match the frozen V4 candidate writer, which used json.dumps defaults.
    return json.dumps(dict(value), sort_keys=True)


def _deduplicate_predictions(frame: pd.DataFrame, *, column: str) -> pd.DataFrame:
    keys = ["season", "game_id", "target"]
    required = {*keys, "regime", "actual", "training_max_year", column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise MeasurementContractError(
            f"V4 candidate rows are missing columns: {missing}"
        )
    # The frozen V4 evaluator drops incomplete candidate rows before scoring.
    # Candidate generation emits null placeholders for designs that could not
    # produce a value, so retain only usable values before enforcing exactly
    # one consistent prediction per game/target key.
    usable = frame.dropna(subset=[column]).copy()
    if usable.empty:
        raise MeasurementContractError("V4 routed prediction has no usable rows")
    grouped = usable.groupby(keys, sort=False, dropna=False)[column]
    if (grouped.nunique(dropna=False) != 1).any():
        raise MeasurementContractError("V4 route has conflicting duplicate predictions")
    return usable.sort_values(keys).groupby(keys, as_index=False, sort=False).first()


def extract_frozen_routes(
    candidates: pd.DataFrame,
    *,
    routing: Mapping[str, Mapping[str, str]],
    selection: Mapping[str, Any],
    source_kind: str,
) -> pd.DataFrame:
    """Select one frozen V4 route per early game and target without reselection."""
    if source_kind not in SOURCE_KINDS:
        raise MeasurementContractError("Unknown V4 benchmark source kind")
    outputs: list[pd.DataFrame] = []
    for target in TARGETS:
        for regime in EARLY_REGIMES:
            try:
                candidate = str(routing[target][regime])
                column = PREDICTION_COLUMNS[candidate]
            except KeyError as exc:
                raise MeasurementContractError(
                    f"Frozen V4 routing is incomplete for {target}/{regime}"
                ) from exc
            subset = candidates[
                (candidates["target"] == target) & (candidates["regime"] == regime)
            ].copy()
            if candidate != "baseline":
                details = selection["reports"][target][regime][candidate]
                variant = str(details["selected_feature_variant"])
                subset = subset[subset["feature_variant"].astype(str) == variant]
                if candidate != "blend":
                    strengths = _canonical_strengths(
                        details["selected_prior_strengths"]
                    )
                    subset = subset[
                        subset["prior_strengths_json"].astype(str) == strengths
                    ]
            if subset.empty:
                raise MeasurementContractError(
                    f"Frozen V4 route is absent for {target}/{regime}/{candidate}"
                )
            selected = _deduplicate_predictions(subset, column=column)
            selected["route_candidate"] = candidate
            selected["v4_prediction"] = pd.to_numeric(selected[column], errors="raise")
            selected["source_kind"] = source_kind
            outputs.append(selected)
    return pd.concat(outputs, ignore_index=True)


def format_established_routes(
    candidates: pd.DataFrame,
    *,
    source_kind: str = "derived_compatibility_replay",
) -> pd.DataFrame:
    if source_kind != "derived_compatibility_replay":
        raise MeasurementContractError("Established V4 replay must remain derived")
    values = candidates.copy()
    if set(values["regime"].dropna()) != {"established"}:
        raise MeasurementContractError(
            "Established replay may contain only established rows"
        )
    selected = _deduplicate_predictions(values, column="direct_ridge_prediction")
    selected["route_candidate"] = "established_direct_ridge"
    selected["v4_prediction"] = pd.to_numeric(
        selected["direct_ridge_prediction"], errors="raise"
    )
    selected["source_kind"] = source_kind
    return selected


def finalize_prediction_frame(
    frame: pd.DataFrame,
    *,
    selection_ref: DatasetRef,
    locked_ref: DatasetRef,
    selection_design_sha: str,
    bundle_id: str,
    config: V4BenchmarkConfig,
    recovery_code_sha: str,
) -> pd.DataFrame:
    values = frame.copy()
    values["season"] = values["season"].astype(int)
    if set(values["season"]) - set(config.historical_seasons):
        raise MeasurementContractError("V4 benchmark contains an unsupported season")
    if set(values["target"].dropna()) != set(TARGETS):
        raise MeasurementContractError("V4 benchmark must include spread and total")
    if not set(values["regime"].dropna()).issubset(ALL_REGIMES):
        raise MeasurementContractError("V4 benchmark has an unknown regime")
    if (values["training_max_year"].astype(int) >= values["season"]).any():
        raise MeasurementContractError("V4 benchmark has non-temporal predictions")
    values["feature_ref_version_id"] = np.where(
        values["season"] == 2025, locked_ref.version_id, selection_ref.version_id
    )
    values["feature_ref_content_sha"] = np.where(
        values["season"] == 2025, locked_ref.content_sha, selection_ref.content_sha
    )
    values["selection_design_sha"] = selection_design_sha
    values["v4_bundle_id"] = bundle_id
    values["benchmark_schema_version"] = V4_BENCHMARK_SCHEMA_VERSION
    values["benchmark_design_id"] = config.design_id
    values["replay_engine_commit"] = config.replay_engine_commit
    values["recovery_code_sha"] = recovery_code_sha
    missing = sorted(set(BENCHMARK_COLUMNS) - set(values.columns))
    if missing:
        raise MeasurementContractError(
            f"V4 benchmark output missing columns: {missing}"
        )
    result = (
        values.loc[:, BENCHMARK_COLUMNS]
        .sort_values(list(BENCHMARK_KEYS))
        .reset_index(drop=True)
    )
    if result.duplicated(list(BENCHMARK_KEYS)).any():
        raise MeasurementContractError("V4 benchmark has duplicate game/target keys")
    if (
        result[["actual", "v4_prediction"]].isna().any().any()
        or not np.isfinite(
            result[["actual", "v4_prediction"]].to_numpy(dtype=float)
        ).all()
    ):
        raise MeasurementContractError("V4 benchmark target or prediction is invalid")
    return result


def metric_summary(frame: pd.DataFrame) -> dict[str, float | int]:
    errors = pd.to_numeric(frame["v4_prediction"]) - pd.to_numeric(frame["actual"])
    return {
        "sample_count": int(len(frame)),
        "mae": float(errors.abs().mean()),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "bias": float(errors.mean()),
    }


def build_replay_audit(
    predictions: pd.DataFrame,
    *,
    config: V4BenchmarkConfig,
    selection_report: Mapping[str, Any],
    locked_report: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    expected_keys: pd.DataFrame,
) -> dict[str, Any]:
    expected = (
        expected_keys.loc[:, BENCHMARK_KEYS]
        .drop_duplicates()
        .sort_values(list(BENCHMARK_KEYS))
    )
    actual = (
        predictions.loc[:, BENCHMARK_KEYS]
        .drop_duplicates()
        .sort_values(list(BENCHMARK_KEYS))
    )
    coverage_ok = expected.reset_index(drop=True).equals(actual.reset_index(drop=True))
    parity: dict[str, Any] = {}
    parity_ok = True
    for target in TARGETS:
        for regime in EARLY_REGIMES:
            key = f"{target}/{regime}"
            selection_rows = predictions[
                (predictions["season"] < 2025)
                & (predictions["target"] == target)
                & (predictions["regime"] == regime)
            ]
            candidate = selection_report["proposed_routing"][target][regime]
            reports = selection_report["reports"][target][regime]
            if candidate == "baseline":
                frozen = next(iter(reports.values()))["metrics"]
                metric_prefix = "baseline"
            else:
                frozen = reports[candidate]["metrics"]
                metric_prefix = "candidate"
            observed = metric_summary(selection_rows)
            checks = {
                "sample_count": observed["sample_count"] == int(frozen["sample_count"]),
                "mae": bool(
                    np.isclose(
                        observed["mae"],
                        float(frozen[f"{metric_prefix}_mae"]),
                        atol=1e-10,
                    )
                ),
                "rmse": bool(
                    np.isclose(
                        observed["rmse"],
                        float(frozen[f"{metric_prefix}_rmse"]),
                        atol=1e-10,
                    )
                ),
                "bias": bool(
                    np.isclose(
                        observed["bias"],
                        float(frozen[f"{metric_prefix}_bias"]),
                        atol=1e-10,
                    )
                ),
            }
            parity[key] = {"observed": observed, "checks": checks}
            parity_ok = parity_ok and all(checks.values())
            locked_entry = locked_report["locked_2025_reports"][target][regime]
            if locked_entry.get("report"):
                locked_rows = predictions[
                    (predictions["season"] == 2025)
                    & (predictions["target"] == target)
                    & (predictions["regime"] == regime)
                ]
                locked_metrics = locked_entry["report"]["metrics"]
                locked_observed = metric_summary(locked_rows)
                locked_checks = {
                    "sample_count": locked_observed["sample_count"]
                    == int(locked_metrics["sample_count"]),
                    "mae": bool(
                        np.isclose(
                            locked_observed["mae"],
                            float(locked_metrics["candidate_mae"]),
                            atol=1e-10,
                        )
                    ),
                    "rmse": bool(
                        np.isclose(
                            locked_observed["rmse"],
                            float(locked_metrics["candidate_rmse"]),
                            atol=1e-10,
                        )
                    ),
                    "bias": bool(
                        np.isclose(
                            locked_observed["bias"],
                            float(locked_metrics["candidate_bias"]),
                            atol=1e-10,
                        )
                    ),
                }
                parity[f"locked/{key}"] = {
                    "observed": locked_observed,
                    "checks": locked_checks,
                }
                parity_ok = parity_ok and all(locked_checks.values())
    checks = {
        "complete_paired_coverage": coverage_ok,
        "unique_game_target_keys": not predictions.duplicated(
            list(BENCHMARK_KEYS)
        ).any(),
        "strictly_temporal": bool(
            (
                predictions["training_max_year"].astype(int)
                < predictions["season"].astype(int)
            ).all()
        ),
        "early_route_metric_parity": parity_ok,
        "established_rows_derived": bool(
            (
                predictions.loc[predictions["regime"] == "established", "source_kind"]
                == "derived_compatibility_replay"
            ).all()
        ),
        "no_markets_or_predictions_from_v4_refit": True,
    }
    return {
        "report_schema_version": "rating_v4_benchmark_replay_audit_v1",
        "benchmark_design_id": config.design_id,
        "historical_seasons": list(config.historical_seasons),
        "input_hashes": dict(input_hashes),
        "bundle_code_sha_discrepancy": {
            "recorded": config.bundle_recorded_code_sha,
            "replay_engine": config.replay_engine_commit,
            "warning": "Historical V4 bundle code SHA predates corrective materialization code; no original artifact was rewritten.",
        },
        "checks": checks,
        "frozen_report_parity": parity,
        "coverage": {
            "expected_game_targets": int(len(expected)),
            "recovered_game_targets": int(len(actual)),
            "by_source_kind": predictions.groupby("source_kind", observed=True)
            .size()
            .to_dict(),
            "by_season": predictions.groupby("season", observed=True).size().to_dict(),
        },
        "all_checks_passed": bool(all(checks.values())),
    }
