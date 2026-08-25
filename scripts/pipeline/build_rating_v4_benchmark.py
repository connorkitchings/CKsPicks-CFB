#!/usr/bin/env python3
"""Recover a research-only, temporally valid historical V4 benchmark."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.v4_benchmark import (
    V4_BENCHMARK_DATASET,
    V4_BENCHMARK_SCHEMA_VERSION,
    build_replay_audit,
    extract_frozen_routes,
    finalize_prediction_frame,
    format_established_routes,
    load_v4_benchmark_config,
    payload_sha,
    read_ref,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/v4_benchmark_replay_v1.yaml"
RELEVANT_PATHS = (
    "src/cks_picks_cfb/ratings/v4_benchmark.py",
    "scripts/pipeline/build_rating_v4_benchmark.py",
    "conf/ratings/v4_benchmark_replay_v1.yaml",
)


def _require_committed_code(expected: str | None) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    code_sha = expected or result.stdout.strip()
    if not code_sha:
        raise ValueError("V4 benchmark artifacts require a committed recovery-code SHA")
    for path in RELEVANT_PATHS:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise ValueError(f"V4 benchmark artifact path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *RELEVANT_PATHS],
        cwd=REPO_ROOT,
        check=False,
    ).returncode:
        raise ValueError("V4 benchmark artifact paths differ from the recorded commit")
    return code_sha


def _write_immutable(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact exists: {uri}")
        return
    storage.write_bytes(payload, uri)


def _worktree(config, directory: Path) -> Path:
    path = directory / "v4-engine"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(path), config.replay_engine_commit],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return path


def _run(command: list[str], *, cwd: Path, engine_root: Path) -> None:
    env = os.environ.copy()
    inherited = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(engine_root / "src") + (
        os.pathsep + inherited if inherited else ""
    )
    subprocess.run(
        command, cwd=cwd, env=env, check=True, capture_output=True, text=True
    )


def _established_script(path: Path) -> None:
    path.write_text(
        """import json
import sys
import pandas as pd
from omegaconf import OmegaConf
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.v2_recency import canonical_prediction_regime
from cks_picks_cfb.models.game_ordinal_training import generate_game_ordinal_candidate_predictions
from cks_picks_cfb.models.training_policy import policy_from_mapping

ref_uri, stage, features_json, experiment, output = sys.argv[1:]
storage = get_storage(environment='preview')
ref = DatasetRef(**json.loads(storage.read_bytes(ref_uri).decode()))
raw = read_dataset(storage, ref).assign(
    prediction_regime=lambda values: values['prediction_regime'].map(canonical_prediction_regime)
)
raw = raw[raw['prediction_regime'].eq('established')].copy()
raw['prediction_regime'] = 'game_1'
spec = OmegaConf.load(experiment)
policy = policy_from_mapping(OmegaConf.to_container(OmegaConf.load(spec.training_policy), resolve=True))
result = generate_game_ordinal_candidate_predictions(
    raw,
    policy=policy,
    features=json.loads(features_json),
    baseline_columns=OmegaConf.to_container(spec.baseline_columns, resolve=True),
    stage=stage,
    candidate_kinds=('direct_ridge',),
    prior_strengths={},
    feature_variant='established_compatibility',
)
result['regime'] = 'established'
result.to_csv(output, index=False)
""",
        encoding="utf-8",
    )


def _engine_candidates(
    config, bundle: dict[str, Any], *, temp_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run original V4 generation code from the corrective committed source tree."""
    engine_root = _worktree(config, temp_root)
    try:
        experiment = engine_root / config.v4_experiment_path
        if not experiment.is_file():
            raise ValueError(
                "Frozen V4 experiment path is absent from the replay engine"
            )
        selection_csv = temp_root / "selection.csv"
        locked_csv = temp_root / "locked.csv"
        script = engine_root / "scripts/pipeline/generate_game_ordinal_candidates.py"
        _run(
            [
                sys.executable,
                str(script),
                "--stage",
                "selection",
                "--feature-ref-uri",
                config.selection_feature_ref_uri,
                "--output-csv",
                str(selection_csv),
                "--environment",
                "preview",
                "--experiment",
                str(experiment),
            ],
            cwd=engine_root,
            engine_root=engine_root,
        )
        _run(
            [
                sys.executable,
                str(script),
                "--stage",
                "locked",
                "--feature-ref-uri",
                config.locked_feature_ref_uri,
                "--selection-report-uri",
                config.selection_report_uri,
                "--output-csv",
                str(locked_csv),
                "--environment",
                "preview",
                "--experiment",
                str(experiment),
            ],
            cwd=engine_root,
            engine_root=engine_root,
        )
        established = temp_root / "established.py"
        _established_script(established)
        established_selection_csv = temp_root / "established-selection.csv"
        established_locked_csv = temp_root / "established-locked.csv"
        features = next(
            route["direct"]["features"]
            for route in bundle["routes"]
            if route["target"] == "spread" and route["regime"] == "established"
        )
        for ref_uri, stage, output in (
            (config.selection_feature_ref_uri, "selection", established_selection_csv),
            (config.locked_feature_ref_uri, "locked", established_locked_csv),
        ):
            _run(
                [
                    sys.executable,
                    str(established),
                    ref_uri,
                    stage,
                    json.dumps(features),
                    str(experiment),
                    str(output),
                ],
                cwd=engine_root,
                engine_root=engine_root,
            )
        return tuple(
            pd.read_csv(path)
            for path in (
                selection_csv,
                locked_csv,
                established_selection_csv,
                established_locked_csv,
            )
        )
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(engine_root)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        )


def _expected_keys(
    storage, refs: tuple[DatasetRef, DatasetRef], config
) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for ref, seasons in ((refs[0], {2022, 2023, 2024}), (refs[1], {2025})):
        frame = read_dataset(storage, ref)
        frame = frame[frame["season"].astype(int).isin(seasons)].copy()
        for target, column in (("spread", "spread_target"), ("total", "total_target")):
            rows = frame[frame[column].notna()][["season", "game_id"]].copy()
            rows["target"] = target
            outputs.append(rows)
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["season", "game_id", "target"]
    )


def _validate_inputs(
    config, storage
) -> tuple[
    DatasetRef,
    DatasetRef,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
]:
    selection_ref = read_ref(storage, config.selection_feature_ref_uri)
    locked_ref = read_ref(storage, config.locked_feature_ref_uri)
    if (
        selection_ref.dataset != "point_in_time_matchups_v5"
        or locked_ref.dataset != "point_in_time_matchups_v5"
    ):
        raise ValueError("V4 benchmark requires strict V5 model-ready feature refs")
    if (
        selection_ref.version_id != config.selection_feature_version_id
        or selection_ref.content_sha != config.selection_feature_content_sha
        or locked_ref.version_id != config.locked_feature_version_id
        or locked_ref.content_sha != config.locked_feature_content_sha
    ):
        raise ValueError("V4 benchmark feature-ref identity mismatch")
    payloads = {
        "selection_report": storage.read_bytes(config.selection_report_uri),
        "locked_report": storage.read_bytes(config.locked_report_uri),
        "bundle_manifest": storage.read_bytes(config.bundle_manifest_uri),
        "established_source_manifest": storage.read_bytes(
            config.established_source_manifest_uri
        ),
    }
    if payload_sha(payloads["bundle_manifest"]) != config.bundle_manifest_sha256:
        raise ValueError("V4 bundle manifest checksum mismatch")
    selection = json.loads(payloads["selection_report"])
    locked = json.loads(payloads["locked_report"])
    bundle = json.loads(payloads["bundle_manifest"])
    if selection.get("selection_design_sha") != config.selection_design_sha:
        raise ValueError("Frozen V4 selection design SHA mismatch")
    if (
        selection.get("feature_track") != "strict"
        or selection.get("feature_ref_uri") != config.selection_feature_ref_uri
        or locked.get("feature_track") != "strict"
    ):
        raise ValueError("V4 benchmark requires the frozen strict report lineage")
    if (
        locked.get("selection_report_sha") != config.selection_design_sha
        or locked.get("stage") != "finalized"
    ):
        raise ValueError("Frozen V4 locked routing report mismatch")
    if (
        bundle.get("bundle_id") != "week0-2026-v4-strict-20260818-r2"
        or bundle.get("code_sha") != config.bundle_recorded_code_sha
        or bundle.get("promotion_reports", {}).get("game_ordinal_predictive_routing")
        != config.locked_report_uri
    ):
        raise ValueError("Unexpected V4 bundle identity")
    source = json.loads(payloads["established_source_manifest"])
    established_features: list[list[str]] = []
    for target in ("spread", "total"):
        v4_features = next(
            route["direct"]["features"]
            for route in bundle["routes"]
            if route["target"] == target and route["regime"] == "established"
        )
        source_route = next(
            route
            for route in source["routes"]
            if route["target"] == target and route["regime"] == "established"
        )
        source_features = (source_route.get("direct") or source_route).get("features")
        if list(v4_features) != list(source_features):
            raise ValueError(
                "V4 established-route feature order differs from its V2 source"
            )
        established_features.append(list(v4_features))
    if established_features[0] != established_features[1]:
        raise ValueError("V4 established spread and total feature orders differ")
    return (
        selection_ref,
        locked_ref,
        selection,
        locked,
        bundle,
        {key: payload_sha(value) for key, value in payloads.items()},
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--predictions-ref-uri", required=True)
    parser.add_argument("--report-uri", required=True)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("V4 benchmark recovery is permitted only in preview")
    config = load_v4_benchmark_config(args.config)
    prefix = f"{config.research_prefix}/{config.design_id}/runs/{args.run_id}/"
    if not args.run_id or any(
        not uri.startswith(prefix)
        for uri in (args.predictions_ref_uri, args.report_uri, args.manifest_uri)
    ):
        raise ValueError(
            "V4 benchmark outputs must live under the run-stamped research prefix"
        )
    code_sha = _require_committed_code(args.expected_code_sha)
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    storage = get_storage(environment="preview")
    selection_ref, locked_ref, selection, locked, bundle, hashes = _validate_inputs(
        config, storage
    )
    with tempfile.TemporaryDirectory(prefix="rating-v4-benchmark-") as raw_temp:
        (
            selection_candidates,
            locked_candidates,
            established_selection,
            established_locked,
        ) = _engine_candidates(config, bundle, temp_root=Path(raw_temp))
    early_selection = extract_frozen_routes(
        selection_candidates,
        routing=selection["proposed_routing"],
        selection=selection,
        source_kind="native_route_replay",
    )
    early_locked = extract_frozen_routes(
        locked_candidates,
        routing=locked["routing"],
        selection=locked["selection_report"],
        source_kind="native_route_replay",
    )
    established = format_established_routes(
        pd.concat([established_selection, established_locked], ignore_index=True)
    )
    predictions = finalize_prediction_frame(
        pd.concat([early_selection, early_locked, established], ignore_index=True),
        selection_ref=selection_ref,
        locked_ref=locked_ref,
        selection_design_sha=config.selection_design_sha,
        bundle_id=bundle["bundle_id"],
        config=config,
        recovery_code_sha=code_sha,
    )
    audit = build_replay_audit(
        predictions,
        config=config,
        selection_report=selection,
        locked_report=locked,
        input_hashes=hashes,
        expected_keys=_expected_keys(storage, (selection_ref, locked_ref), config),
    )
    report_payload = json.dumps(audit, indent=2, sort_keys=True).encode()
    if not audit["all_checks_passed"]:
        _write_immutable(storage, args.report_uri, report_payload)
        raise ValueError(
            "V4 benchmark audit failed; successful refs were not published"
        )
    prediction_ref, _prediction_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=V4_BENCHMARK_DATASET,
            parent_refs=(selection_ref, locked_ref),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=V4_BENCHMARK_SCHEMA_VERSION,
            tier="gold",
        ),
        records=predictions.to_dict("records"),
        partitions={"seasons": list(config.historical_seasons)},
        validation={"nonempty": not predictions.empty, "all_audit_checks_passed": True},
    )
    audit["lineage"] = {
        "prediction_ref": asdict(prediction_ref),
        "prediction_manifest_uri": (
            prediction_ref.uri.rsplit("/", 1)[0] + "/manifest.json"
        ),
    }
    report_payload = json.dumps(audit, indent=2, sort_keys=True).encode()
    _write_immutable(storage, args.report_uri, report_payload)
    _write_immutable(
        storage,
        args.predictions_ref_uri,
        json.dumps(asdict(prediction_ref), sort_keys=True).encode(),
    )
    manifest = {
        "schema_version": "rating_v4_benchmark_replay_manifest_v1",
        "benchmark_design_id": config.design_id,
        "run_id": args.run_id,
        "code_sha": code_sha,
        "replay_engine_commit": config.replay_engine_commit,
        "prediction_ref": asdict(prediction_ref),
        "report_uri": args.report_uri,
        "report_sha256": payload_sha(report_payload),
        "input_hashes": hashes,
    }
    _write_immutable(
        storage,
        args.manifest_uri,
        json.dumps(manifest, indent=2, sort_keys=True).encode(),
    )
    print(
        json.dumps(
            {
                "status": "built",
                "predictions_ref": asdict(prediction_ref),
                "report_sha256": payload_sha(report_payload),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
