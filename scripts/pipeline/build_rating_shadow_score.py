#!/usr/bin/env python3
"""Finalize one frozen shadow slate with complete outcomes and paired V4."""

from __future__ import annotations

import argparse
import hashlib
import json
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
from cks_picks_cfb.ratings.prospective import (
    EVALUATOR_CODE_PATHS,
    committed_code_manifest,
    load_prospective_policy,
    validate_parent_manifest,
)
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
DEFAULT_POLICY = REPO_ROOT / "conf/ratings/prospective_evidence_v1.yaml"


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


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


def _cancellation_waivers(values: list[str], games: pd.DataFrame) -> dict[int, str]:
    waivers: dict[int, str] = {}
    for value in values:
        game_id_text, separator, reason = value.partition("=")
        if not separator or not reason.strip():
            raise ValueError("Cancellation waiver must be GAME_ID=reason")
        game_id = int(game_id_text)
        if game_id in waivers:
            raise ValueError(f"Duplicate cancellation waiver for game {game_id}")
        matching = games[pd.to_numeric(games["game_id"], errors="coerce").eq(game_id)]
        if len(matching) != 1:
            raise ValueError(
                f"Cancellation waiver game is not uniquely scheduled: {game_id}"
            )
        status = str(matching.iloc[0].get("status", "")).strip().lower()
        if status not in {"cancelled", "canceled", "postponed"}:
            raise ValueError(
                "Cancellation waiver requires an authoritative cancelled status"
            )
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
    parser.add_argument("--prospective-policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--outcomes-ref-uri", action="append", required=True)
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--register-catalog", action="store_true")
    parser.add_argument("--cancellation-waiver", action="append", default=[])
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Shadow scoring is permitted only in preview")
    shadow = load_shadow_config(args.config)
    policy = load_prospective_policy(args.prospective_policy)
    if policy.shadow_design_id != shadow.design_id:
        raise ValueError("Prospective policy and shadow config do not match")
    code_manifest = committed_code_manifest(
        repo_root=REPO_ROOT,
        code_sha=args.expected_code_sha,
        paths=EVALUATOR_CODE_PATHS,
        policy_sha256=policy.policy_sha256,
    )
    code_sha = str(code_manifest["code_sha"])
    preview, production = (
        get_storage(environment="preview"),
        ReadOnlyStorage(get_storage(environment="production")),
    )
    if args.register_catalog:
        _preflight_catalog()
    season, week = args.season, args.week
    if season != policy.season or week < policy.first_eligible_week:
        raise ValueError("Prospective policy does not permit this slate")
    score_started_at = datetime.now(timezone.utc)
    freeze_uri = canonical_manifest_uri(shadow, season=season, week=week, kind="freeze")
    if not preview.exists(freeze_uri):
        raise FileNotFoundError("Canonical shadow freeze manifest is required")
    freeze_bytes = preview.read_bytes(freeze_uri)
    freeze = json.loads(freeze_bytes.decode())
    if int(freeze.get("season", -1)) != season or int(freeze.get("week", -1)) != week:
        raise ValueError("Canonical freeze manifest does not match requested slate")
    if freeze.get("prospective_policy_sha256") != policy.policy_sha256:
        raise ValueError("Canonical freeze belongs to another prospective policy")
    assert_canonical_artifact_set(
        preview,
        prefix=shadow.canonical_week_prefix(season=season, week=week),
        kind="freeze",
    )
    prediction_ref = DatasetRef(**freeze["predictions_ref"])
    require_dataset(prediction_ref, SHADOW_FREEZE_DATASET)
    predictions = read_dataset(preview, prediction_ref)
    outcome_refs = tuple(_ref(preview, uri) for uri in args.outcomes_ref_uri)
    game_ref = _ref(preview, args.games_ref_uri)
    for ref in (*outcome_refs, game_ref):
        manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
        manifest = json.loads(preview.read_bytes(manifest_uri).decode())
        validate_parent_manifest(
            manifest,
            ref=ref_identity(ref),
            as_of=datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
            freeze_started_at=score_started_at,
        )
    outcomes = pd.concat(
        [read_dataset(preview, ref) for ref in outcome_refs], ignore_index=True
    )
    games = read_dataset(preview, game_ref)
    score_as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    if score_as_of > score_started_at:
        raise ValueError("Prospective score cutoff cannot be in the future")
    latest_kickoff = datetime.fromisoformat(
        str(freeze["latest_kickoff"]).replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    if (
        score_started_at - latest_kickoff
    ).total_seconds() < policy.score_stabilization_seconds:
        raise ValueError("Prospective score has not passed the stabilization interval")
    proof = dict(freeze["v4_source"])
    v4 = _read_v4(production, proof, season, week, dict(shadow.production_v4))
    input_identity = {
        "freeze_manifest_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
        "outcomes": [ref_identity(ref) for ref in outcome_refs],
        "games": ref_identity(game_ref),
        "v4": proof,
        "prospective_policy_sha256": policy.policy_sha256,
        "evaluator_code_manifest": code_manifest,
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
        "score_started_at": score_started_at.isoformat(),
        "games_ref": json.dumps(ref_identity(game_ref), sort_keys=True),
    }
    evidence, report = score_freeze(
        freeze_predictions=predictions,
        outcomes=outcomes,
        v4=v4,
        lineage=lineage,
        cancellation_waivers=_cancellation_waivers(args.cancellation_waiver, games),
    )
    report = {
        **report,
        **expected,
        "freeze_manifest_uri": freeze_uri,
        "v4_source": proof,
        "prospective_policy_sha256": policy.policy_sha256,
        "evaluator_code_manifest": code_manifest,
        "score_completed_at": datetime.now(timezone.utc).isoformat(),
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
            parent_refs=(prediction_ref, game_ref, *outcome_refs),
            code_sha=code_sha,
            config_sha=policy.policy_sha256,
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
