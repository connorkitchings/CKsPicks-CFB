#!/usr/bin/env python3
"""Finalize one frozen shadow slate with complete outcomes and paired V4."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
    require_dataset,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage
from cks_picks_cfb.ratings.shadow import (
    SHADOW_EVIDENCE_DATASET,
    SHADOW_EVIDENCE_SCHEMA_VERSION,
    SHADOW_FREEZE_DATASET,
    assert_canonical_artifact_set,
    canonical_manifest_uri,
    existing_or_collision,
    immutable_write,
    load_shadow_config,
    normalize_v4_prediction_run,
    ref_identity,
    score_freeze,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/shadow_operations_v1.yaml"
RELEVANT = (
    "src/cks_picks_cfb/ratings/shadow.py",
    "scripts/pipeline/build_rating_shadow_score.py",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _require_commit(expected: str | None, config_path: str) -> str:
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    code_sha = expected or current
    paths = (*RELEVANT, config_path)
    if not code_sha or any(
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode
        for path in paths
    ):
        raise ValueError(
            "Shadow score artifacts require committed implementation paths"
        )
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *paths], cwd=REPO_ROOT, check=False
    ).returncode:
        raise ValueError("Shadow score paths differ from the recorded commit")
    return code_sha


def _read_v4(
    production,
    proof: dict[str, object],
    season: int,
    week: int,
    expected_v4: dict[str, str],
) -> pd.DataFrame:
    manifest_bytes = production.read_bytes(str(proof["manifest_uri"]))
    csv_bytes = production.read_bytes(str(proof["artifact_uri"]))
    if (
        hashlib.sha256(manifest_bytes).hexdigest() != proof["manifest_sha256"]
        or hashlib.sha256(csv_bytes).hexdigest() != proof["prediction_sha256"]
    ):
        raise ValueError("Pinned production V4 artifact changed after freeze")
    return normalize_v4_prediction_run(
        manifest=json.loads(manifest_bytes.decode()),
        csv_bytes=csv_bytes,
        season=season,
        week=week,
        expected_v4=expected_v4,
    )


def _cancellation_waivers(values: list[str]) -> dict[int, str]:
    waivers: dict[int, str] = {}
    for value in values:
        game_id_text, separator, reason = value.partition("=")
        if not separator or not reason.strip():
            raise ValueError("Cancellation waiver must be GAME_ID=reason")
        game_id = int(game_id_text)
        if game_id in waivers:
            raise ValueError(f"Duplicate cancellation waiver for game {game_id}")
        waivers[game_id] = reason.strip()
    return waivers


def _preflight_catalog() -> None:
    import psycopg

    with psycopg.connect(resolve_runtime_target("preview").database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--outcomes-ref-uri", action="append", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--register-catalog", action="store_true")
    parser.add_argument("--cancellation-waiver", action="append", default=[])
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Shadow scoring is permitted only in preview")
    shadow = load_shadow_config(args.config)
    config_path = str(Path(args.config).resolve().relative_to(REPO_ROOT))
    code_sha = _require_commit(args.expected_code_sha, config_path)
    preview, production = (
        get_storage(environment="preview"),
        ReadOnlyStorage(get_storage(environment="production")),
    )
    if args.register_catalog:
        _preflight_catalog()
    season, week = args.season, args.week
    freeze_uri = canonical_manifest_uri(shadow, season=season, week=week, kind="freeze")
    if not preview.exists(freeze_uri):
        raise FileNotFoundError("Canonical shadow freeze manifest is required")
    freeze_bytes = preview.read_bytes(freeze_uri)
    freeze = json.loads(freeze_bytes.decode())
    if int(freeze.get("season", -1)) != season or int(freeze.get("week", -1)) != week:
        raise ValueError("Canonical freeze manifest does not match requested slate")
    prediction_ref = DatasetRef(**freeze["predictions_ref"])
    require_dataset(prediction_ref, SHADOW_FREEZE_DATASET)
    predictions = read_dataset(preview, prediction_ref)
    outcome_refs = tuple(_ref(preview, uri) for uri in args.outcomes_ref_uri)
    outcomes = pd.concat(
        [read_dataset(preview, ref) for ref in outcome_refs], ignore_index=True
    )
    score_as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    proof = dict(freeze["v4_source"])
    v4 = _read_v4(production, proof, season, week, dict(shadow.production_v4))
    input_identity = {
        "freeze_manifest_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
        "outcomes": [ref_identity(ref) for ref in outcome_refs],
        "v4": proof,
    }
    expected = {
        "shadow_design_id": shadow.design_id,
        "season": season,
        "week": week,
        "as_of": score_as_of.isoformat(),
        "input_identity": input_identity,
    }
    report_uri = canonical_manifest_uri(shadow, season=season, week=week, kind="score")
    prefix = shadow.canonical_week_prefix(season=season, week=week)
    assert_canonical_artifact_set(preview, prefix=prefix, kind="score")
    if existing := existing_or_collision(preview, report_uri, expected):
        print(
            json.dumps(
                {"status": "existing", "report": existing}, indent=2, sort_keys=True
            )
        )
        return
    lineage = {
        "freeze_manifest_sha256": input_identity["freeze_manifest_sha256"],
        "outcome_refs": json.dumps(input_identity["outcomes"], sort_keys=True),
        "v4_run_id": proof["run_id"],
        "v4_manifest_sha256": proof["manifest_sha256"],
        "v4_prediction_sha256": proof["prediction_sha256"],
        "v4_source_uri": proof["artifact_uri"],
        "scored_at": score_as_of.isoformat(),
    }
    evidence, report = score_freeze(
        freeze_predictions=predictions,
        outcomes=outcomes,
        v4=v4,
        lineage=lineage,
        cancellation_waivers=_cancellation_waivers(args.cancellation_waiver),
    )
    report = {
        **report,
        **expected,
        "freeze_manifest_uri": freeze_uri,
        "v4_source": proof,
    }
    if not report["complete"]:
        diagnostic_uri = f"{shadow.canonical_week_prefix(season=season, week=week)}/diagnostics/score-{hashlib.sha256(json.dumps(expected, sort_keys=True, default=str).encode()).hexdigest()}.json"
        immutable_write(
            preview,
            diagnostic_uri,
            json.dumps(report, indent=2, sort_keys=True, default=str).encode(),
        )
        raise ValueError(
            f"Shadow score is incomplete; diagnostic written to {diagnostic_uri}"
        )
    evidence_ref, evidence_manifest = build_dataset_version(
        preview,
        build=BuildRequest(
            dataset=SHADOW_EVIDENCE_DATASET,
            parent_refs=(prediction_ref, *outcome_refs),
            code_sha=code_sha,
            config_sha=shadow.design_id,
            as_of=score_as_of,
            schema_version=SHADOW_EVIDENCE_SCHEMA_VERSION,
            tier="gold",
        ),
        records=evidence.to_dict("records"),
        partitions={"slate": [f"{season}_w{week:02d}"]},
        validation={"complete_outcomes": True, "complete_v4_pairing": True},
    )
    report["code_sha"] = code_sha
    report["evidence_ref"] = ref_identity(evidence_ref)
    immutable_write(
        preview,
        report_uri,
        json.dumps(report, indent=2, sort_keys=True, default=str).encode(),
    )
    immutable_write(
        preview,
        f"{prefix}/evidence-ref.json",
        json.dumps(ref_identity(evidence_ref), sort_keys=True).encode(),
    )
    if args.register_catalog:
        from cks_picks_cfb.data.catalog import register_dataset_version

        register_dataset_version(
            resolve_runtime_target("preview").database_url,
            evidence_ref,
            evidence_manifest,
        )
    print(
        json.dumps(
            {
                "status": "scored",
                "report_uri": report_uri,
                "evidence_ref": ref_identity(evidence_ref),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
