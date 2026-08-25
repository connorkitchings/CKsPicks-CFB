"""Tests for the isolated V4 historical benchmark recovery contract."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch

import pandas as pd
import pytest

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.v4_benchmark import (
    EARLY_REGIMES,
    build_replay_audit,
    extract_frozen_routes,
    finalize_prediction_frame,
    format_established_routes,
    load_v4_benchmark_config,
    metric_summary,
)
from scripts.pipeline import build_rating_v4_benchmark as cli


@pytest.fixture()
def config():
    return load_v4_benchmark_config("conf/ratings/v4_benchmark_replay_v1.yaml")


@pytest.fixture()
def refs():
    return (
        DatasetRef(
            "point_in_time_matchups_v5",
            "selection",
            "v5",
            "a" * 64,
            "selection.parquet",
        ),
        DatasetRef(
            "point_in_time_matchups_v5", "locked", "v5", "b" * 64, "locked.parquet"
        ),
    )


def _reports(frame: pd.DataFrame) -> tuple[dict, dict]:
    reports = {target: {} for target in ("spread", "total")}
    routing = {target: {} for target in ("spread", "total")}
    for target in routing:
        for regime in EARLY_REGIMES:
            rows = frame[(frame.target == target) & (frame.regime == regime)]
            values = metric_summary(
                rows.rename(columns={"direct_ridge_prediction": "v4_prediction"})
            )
            metrics = {
                "sample_count": values["sample_count"],
                "candidate_mae": values["mae"],
                "candidate_rmse": values["rmse"],
                "candidate_bias": values["bias"],
                "baseline_mae": values["mae"],
                "baseline_rmse": values["rmse"],
                "baseline_bias": values["bias"],
            }
            reports[target][regime] = {
                "direct_ridge": {
                    "selected_feature_variant": "prior_core",
                    "selected_prior_strengths": {},
                    "metrics": metrics,
                }
            }
            routing[target][regime] = "direct_ridge"
    selection = {
        "selection_design_sha": "design",
        "proposed_routing": routing,
        "reports": reports,
    }
    locked = {
        "routing": routing,
        "locked_2025_reports": {
            target: {
                regime: {"candidate": "direct_ridge", "locked_test_pass": True}
                for regime in EARLY_REGIMES
            }
            for target in ("spread", "total")
        },
    }
    return selection, locked


def _candidate_rows(seasons=(2022, 2023, 2024)) -> pd.DataFrame:
    rows = []
    game_id = 1
    for season in seasons:
        for target in ("spread", "total"):
            for ordinal, regime in enumerate(EARLY_REGIMES):
                actual = float(season - 2000 + ordinal)
                rows.append(
                    {
                        "season": season,
                        "game_id": game_id,
                        "target": target,
                        "regime": regime,
                        "actual": actual,
                        "training_max_year": season - 1,
                        "feature_variant": "prior_core",
                        "prior_strengths_json": "{}",
                        "baseline_prediction": actual,
                        "blend_prediction": actual,
                        "direct_ridge_prediction": actual,
                    }
                )
                game_id += 1
    return pd.DataFrame(rows)


def test_extract_frozen_routes_filters_the_frozen_design():
    candidates = _candidate_rows()
    selection, _ = _reports(candidates)
    # A non-selected design for the same game must never affect the route value.
    extra = candidates.iloc[[0]].copy()
    extra["feature_variant"] = "wrong"
    extra["direct_ridge_prediction"] = 999.0
    result = extract_frozen_routes(
        pd.concat([candidates, extra], ignore_index=True),
        routing=selection["proposed_routing"],
        selection=selection,
        source_kind="native_route_replay",
    )
    assert len(result) == len(candidates)
    assert result["v4_prediction"].max() < 999.0
    assert set(result["route_candidate"]) == {"direct_ridge"}


def test_extract_frozen_routes_rejects_conflicting_duplicate_predictions():
    candidates = _candidate_rows()
    selection, _ = _reports(candidates)
    duplicate = candidates.iloc[[0]].copy()
    duplicate["direct_ridge_prediction"] = 42.0
    with pytest.raises(MeasurementContractError, match="conflicting duplicate"):
        extract_frozen_routes(
            pd.concat([candidates, duplicate], ignore_index=True),
            routing=selection["proposed_routing"],
            selection=selection,
            source_kind="native_route_replay",
        )


def test_established_replay_must_be_labeled_derived():
    candidates = _candidate_rows((2022,)).copy()
    candidates["regime"] = "established"
    result = format_established_routes(candidates)
    assert set(result["source_kind"]) == {"derived_compatibility_replay"}
    with pytest.raises(MeasurementContractError, match="must remain derived"):
        format_established_routes(candidates, source_kind="native_route_replay")


def test_finalize_rejects_same_season_training(config, refs):
    candidates = _candidate_rows((2022,))
    selection, _ = _reports(candidates)
    routed = extract_frozen_routes(
        candidates,
        routing=selection["proposed_routing"],
        selection=selection,
        source_kind="native_route_replay",
    )
    routed.loc[routed.index[0], "training_max_year"] = 2022
    with pytest.raises(MeasurementContractError, match="non-temporal"):
        finalize_prediction_frame(
            routed,
            selection_ref=refs[0],
            locked_ref=refs[1],
            selection_design_sha="design",
            bundle_id="bundle",
            config=config,
            recovery_code_sha="code",
        )


def test_audit_accepts_exact_frozen_early_route_parity(config, refs):
    selection_candidates = _candidate_rows((2022, 2023, 2024))
    locked_candidates = _candidate_rows((2025,))
    selection, locked = _reports(selection_candidates)
    established_candidates = _candidate_rows((2022, 2023, 2024, 2025)).copy()
    established_candidates["game_id"] += 100_000
    established_candidates["regime"] = "established"
    predicted = finalize_prediction_frame(
        pd.concat(
            [
                extract_frozen_routes(
                    selection_candidates,
                    routing=selection["proposed_routing"],
                    selection=selection,
                    source_kind="native_route_replay",
                ),
                extract_frozen_routes(
                    locked_candidates,
                    routing=locked["routing"],
                    selection=selection,
                    source_kind="native_route_replay",
                ),
                format_established_routes(established_candidates),
            ],
            ignore_index=True,
        ),
        selection_ref=refs[0],
        locked_ref=refs[1],
        selection_design_sha="design",
        bundle_id="bundle",
        config=config,
        recovery_code_sha="code",
    )
    audit = build_replay_audit(
        predicted,
        config=config,
        selection_report=selection,
        locked_report=locked,
        input_hashes={"bundle": "x"},
        expected_keys=predicted[["season", "game_id", "target"]],
    )
    assert audit["all_checks_passed"] is True
    assert audit["checks"]["early_route_metric_parity"] is True


def test_cli_rejects_production_before_any_storage_operation():
    with pytest.raises(ValueError, match="only in preview"):
        cli.main(
            [
                "--environment",
                "production",
                "--as-of",
                "2026-08-25T00:00:00Z",
                "--run-id",
                "test",
                "--predictions-ref-uri",
                "unused",
                "--report-uri",
                "unused",
                "--manifest-uri",
                "unused",
            ]
        )


def test_cli_rejects_outputs_outside_the_research_prefix():
    with pytest.raises(ValueError, match="run-stamped research prefix"):
        cli.main(
            [
                "--environment",
                "preview",
                "--as-of",
                "2026-08-25T00:00:00Z",
                "--run-id",
                "test",
                "--predictions-ref-uri",
                "artifacts/production/v4/ref.json",
                "--report-uri",
                "artifacts/production/v4/report.json",
                "--manifest-uri",
                "artifacts/production/v4/manifest.json",
            ]
        )


def test_cli_publishes_successful_refs_only_after_a_passing_idempotent_audit(
    tmp_path, capsys, config, refs
):
    storage = LocalStorage(tmp_path)
    selection_candidates = _candidate_rows((2022, 2023, 2024))
    locked_candidates = _candidate_rows((2025,))
    established_candidates = _candidate_rows((2022, 2023, 2024, 2025)).copy()
    established_candidates["game_id"] += 100_000
    established_candidates["regime"] = "established"
    selection, locked = _reports(selection_candidates)
    locked["selection_report"] = selection
    expected = finalize_prediction_frame(
        pd.concat(
            [
                extract_frozen_routes(
                    selection_candidates,
                    routing=selection["proposed_routing"],
                    selection=selection,
                    source_kind="native_route_replay",
                ),
                extract_frozen_routes(
                    locked_candidates,
                    routing=locked["routing"],
                    selection=selection,
                    source_kind="native_route_replay",
                ),
                format_established_routes(established_candidates),
            ],
            ignore_index=True,
        ),
        selection_ref=refs[0],
        locked_ref=refs[1],
        selection_design_sha=config.selection_design_sha,
        bundle_id="bundle",
        config=config,
        recovery_code_sha="test-code-sha",
    )
    prefix = f"{config.research_prefix}/{config.design_id}/runs/test-run"
    argv = [
        "--environment",
        "preview",
        "--as-of",
        "2026-08-17T16:00:00Z",
        "--run-id",
        "test-run",
        "--predictions-ref-uri",
        f"{prefix}/predictions/ref.json",
        "--report-uri",
        f"{prefix}/audit/report.json",
        "--manifest-uri",
        f"{prefix}/manifest.json",
    ]
    validated = (refs[0], refs[1], selection, locked, {"bundle_id": "bundle"}, {})
    with (
        patch.object(cli, "get_storage", return_value=storage),
        patch.object(cli, "_require_committed_code", return_value="test-code-sha"),
        patch.object(cli, "_validate_inputs", return_value=validated),
        patch.object(
            cli,
            "_expected_keys",
            return_value=expected[["season", "game_id", "target"]],
        ),
        patch.object(
            cli,
            "_engine_candidates",
            return_value=(
                selection_candidates,
                locked_candidates,
                established_candidates[established_candidates["season"] < 2025],
                established_candidates[established_candidates["season"] == 2025],
            ),
        ),
    ):
        cli.main(argv)
        first = json.loads(capsys.readouterr().out)
        ref_payload = storage.read_bytes(f"{prefix}/predictions/ref.json")
        report_payload = storage.read_bytes(f"{prefix}/audit/report.json")
        manifest_payload = storage.read_bytes(f"{prefix}/manifest.json")
        cli.main(argv)
        second = json.loads(capsys.readouterr().out)

    assert first == second
    assert first["predictions_ref"] == json.loads(ref_payload)
    assert storage.read_bytes(f"{prefix}/predictions/ref.json") == ref_payload
    assert storage.read_bytes(f"{prefix}/audit/report.json") == report_payload
    assert storage.read_bytes(f"{prefix}/manifest.json") == manifest_payload
    report = json.loads(report_payload)
    assert report["all_checks_passed"] is True
    assert report["lineage"]["prediction_ref"] == asdict(
        DatasetRef(**json.loads(ref_payload))
    )
    assert report["lineage"]["prediction_manifest_uri"].endswith("/manifest.json")
