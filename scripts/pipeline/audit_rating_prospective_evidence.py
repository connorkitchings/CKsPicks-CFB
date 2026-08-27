#!/usr/bin/env python3
"""Audit canonical Phase 5 evidence without selecting or tuning a candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.prospective import (
    EVALUATOR_CODE_PATHS,
    committed_code_manifest,
    descriptive_metrics,
    load_prospective_policy,
)
from cks_picks_cfb.ratings.shadow import (
    assert_canonical_artifact_set,
    canonical_manifest_uri,
    immutable_write,
    load_shadow_config,
    ref_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/shadow_operations_v1.yaml"
DEFAULT_POLICY = REPO_ROOT / "conf/ratings/prospective_evidence_v1.yaml"


def _load_json(storage, uri: str) -> tuple[dict, str]:
    payload = storage.read_bytes(uri)
    return json.loads(payload.decode()), hashlib.sha256(payload).hexdigest()


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--prospective-policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--through-week", type=int, required=True)
    parser.add_argument("--verification-games-ref-uri", required=True)
    parser.add_argument(
        "--verification-outcomes-ref-uri", action="append", required=True
    )
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Prospective evidence audit is Preview-only")
    shadow = load_shadow_config(args.config)
    policy = load_prospective_policy(args.prospective_policy)
    code_manifest = committed_code_manifest(
        repo_root=REPO_ROOT,
        code_sha=args.expected_code_sha,
        paths=EVALUATOR_CODE_PATHS,
        policy_sha256=policy.policy_sha256,
    )
    if policy.shadow_design_id != shadow.design_id:
        raise ValueError("Prospective policy and shadow config do not match")
    if args.through_week < policy.first_eligible_week:
        raise ValueError("Audit through-week precedes the protected window")
    storage = get_storage(environment="preview")
    verification_games = read_dataset(
        storage,
        DatasetRef(
            **json.loads(storage.read_bytes(args.verification_games_ref_uri).decode())
        ),
    )
    verification_outcomes = pd.concat(
        [
            read_dataset(
                storage, DatasetRef(**json.loads(storage.read_bytes(uri).decode()))
            )
            for uri in args.verification_outcomes_ref_uri
        ],
        ignore_index=True,
    )
    eligible: list[dict] = []
    all_rows = []
    excluded_weeks: list[dict] = []
    for week in range(policy.first_eligible_week, args.through_week + 1):
        prefix = shadow.canonical_week_prefix(season=policy.season, week=week)
        freeze_uri = canonical_manifest_uri(
            shadow, season=policy.season, week=week, kind="freeze"
        )
        score_uri = canonical_manifest_uri(
            shadow, season=policy.season, week=week, kind="score"
        )
        if not storage.exists(freeze_uri) or not storage.exists(score_uri):
            continue
        assert_canonical_artifact_set(storage, prefix=prefix, kind="freeze")
        assert_canonical_artifact_set(storage, prefix=prefix, kind="score")
        freeze, freeze_sha = _load_json(storage, freeze_uri)
        score, score_sha = _load_json(storage, score_uri)
        if (
            freeze.get("shadow_design_id") != shadow.design_id
            or freeze.get("prospective_policy_sha256") != policy.policy_sha256
            or score.get("prospective_policy_sha256") != policy.policy_sha256
            or not freeze.get("eligibility", {}).get("policy_eligible")
            or int(freeze.get("scheduled_games", 0)) < policy.normal_coverage_min_games
            or float(freeze.get("measured_lead_seconds", 0)) < policy.hard_lead_seconds
        ):
            continue
        evidence_ref = DatasetRef(**score["evidence_ref"])
        evidence = read_dataset(storage, evidence_ref)
        frozen_game_ids = set(evidence["game_id"].astype(int))
        current_games = verification_games[
            verification_games["game_id"].astype(int).isin(frozen_game_ids)
        ]
        if len(current_games) != len(frozen_game_ids):
            excluded_weeks.append(
                {"week": week, "reason": "authoritative_schedule_missing"}
            )
            continue
        completed = verification_outcomes[
            verification_outcomes["completed"]
            .astype(str)
            .str.lower()
            .isin(("true", "1", "1.0"))
        ].drop_duplicates(["season", "game_id"])
        current = (
            evidence[["season", "game_id", "actual"]]
            .drop_duplicates()
            .merge(
                completed[["season", "game_id", "home_points", "away_points"]],
                on=["season", "game_id"],
                how="left",
            )
        )
        current_actual = current.home_points.astype(float) - current.away_points.astype(
            float
        )
        target_actual = current.assign(current_actual=current_actual).merge(
            evidence[["season", "game_id", "target", "actual"]],
            on=["season", "game_id"],
            how="left",
        )
        target_actual["expected_actual"] = target_actual.apply(
            lambda row: row["current_actual"]
            if row["target"] == "margin"
            else row["home_points"] + row["away_points"],
            axis=1,
        )
        if (
            target_actual["expected_actual"].isna().any()
            or not (
                target_actual["expected_actual"].astype(float)
                == target_actual["actual"].astype(float)
            ).all()
        ):
            excluded_weeks.append(
                {"week": week, "reason": "authoritative_outcome_correction_or_missing"}
            )
            continue
        all_rows.append(evidence)
        eligible.append(
            {
                "week": week,
                "freeze_manifest_uri": freeze_uri,
                "freeze_manifest_sha256": freeze_sha,
                "score_report_uri": score_uri,
                "score_report_sha256": score_sha,
                "evidence_ref": ref_identity(evidence_ref),
            }
        )
    evidence_frame = (
        pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    )
    summary = {
        "schema_version": "rating_prospective_evidence_summary_v1",
        "season": policy.season,
        "through_week": args.through_week,
        "shadow_design_id": shadow.design_id,
        "prospective_policy_sha256": policy.policy_sha256,
        "evaluator_code_manifest": code_manifest,
        "eligible_slate_count": len(eligible),
        "eligible_slates": eligible,
        "excluded_weeks": excluded_weeks,
        "metrics": descriptive_metrics(evidence_frame),
        "promotion_decision": None,
    }
    prefix = policy.canonical_prefix(shadow.research_prefix, args.through_week)
    summary_uri = f"{prefix}/summary.json"
    immutable_write(
        storage,
        summary_uri,
        json.dumps(summary, indent=2, sort_keys=True, default=str).encode(),
    )
    completion_uri = None
    if len(eligible) >= policy.required_eligible_slates:
        completion = {
            "schema_version": "rating_prospective_evidence_completion_v1",
            "season": policy.season,
            "shadow_design_id": shadow.design_id,
            "prospective_policy_sha256": policy.policy_sha256,
            "first_six_eligible_slates": eligible[: policy.required_eligible_slates],
            "summary_uri": summary_uri,
        }
        completion_uri = f"{prefix}/phase5-completion.json"
        immutable_write(
            storage,
            completion_uri,
            json.dumps(completion, indent=2, sort_keys=True).encode(),
        )
    print(
        json.dumps(
            {"summary_uri": summary_uri, "completion_uri": completion_uri, **summary},
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
