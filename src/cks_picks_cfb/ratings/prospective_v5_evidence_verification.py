"""Independent Contract 06 evidence reconstruction and artifact verification."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.ratings.prospective_v5_evidence_sources import (
    collect_verified_sources,
)

MANIFEST_SCHEMA = "data_first_v5_prospective_evidence_manifest_v1"
OUTPUT_NAMES = {
    "attempt_ledger": "attempt-ledger.json",
    "football_report": "football-report.json",
    "quote_diagnostic": "quote-diagnostic.json",
    "recommendation": "recommendation.json",
}
REQUIRED_SLATES = 6
FREEZE_HARD_LEAD_SECONDS = 3600
SCORE_STABILIZATION_SECONDS = 24 * 3600


class EvidenceVerificationError(ValueError):
    """Raised when immutable Contract 06 outputs do not reconstruct."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _equivalent(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right)
        )
    if (
        isinstance(left, (float, int))
        and not isinstance(left, bool)
        and isinstance(right, (float, int))
        and not isinstance(right, bool)
    ):
        return bool(
            np.isclose(
                float(left), float(right), rtol=1e-12, atol=1e-10, equal_nan=True
            )
        )
    return left == right


def _independent_dispositions(
    attempts: pd.DataFrame,
    evaluations: pd.DataFrame,
    *,
    candidate: str,
) -> pd.DataFrame:
    if evaluations.empty:
        evaluations = pd.DataFrame(
            columns=[
                "candidate",
                "season",
                "week",
                "run_id",
                "outcome_version",
                "score_completed_at",
                "last_game_completed_at",
                "outcome_ref",
                "evaluation_ref",
                "evaluation_manifest_sha256",
                "evaluation_verified",
                "supersedes_score_manifest_uri",
            ]
        )
    merged = attempts.merge(
        evaluations,
        on=["candidate", "season", "week", "run_id"],
        how="left",
        suffixes=("", "_evaluation"),
        validate="one_to_many",
    )
    rows: list[dict[str, Any]] = []
    already_counted: set[tuple[str, int, int]] = set()
    for value in merged.to_dict("records"):
        reasons: list[str] = []
        slate = (str(value["candidate"]), int(value["season"]), int(value["week"]))
        if str(value["candidate"]) != candidate:
            reasons.append("candidate_identity_mismatch")
        if int(value["week"]) < 5:
            reasons.append("week_before_prospective_window")
        if bool(value["diagnostic_only"]):
            reasons.append("diagnostic_only")
        if (
            not bool(value["readiness_verified"])
            or value["readiness_overall"] != "ready"
        ):
            reasons.append("readiness_not_verified_ready")
        try:
            kickoff = pd.Timestamp(value["first_kickoff"])
            frozen = pd.Timestamp(value["freeze_completed_at"])
            if (
                pd.isna(kickoff)
                or pd.isna(frozen)
                or kickoff.tzinfo is None
                or frozen.tzinfo is None
            ):
                raise ValueError
            if (
                kickoff.tz_convert("UTC") - frozen.tz_convert("UTC")
            ).total_seconds() < FREEZE_HARD_LEAD_SECONDS:
                reasons.append("freeze_missed_t_minus_1h")
        except (TypeError, ValueError):
            reasons.append("freeze_missing_or_unverified")
        if not bool(value["normal_coverage"]):
            reasons.append("schedule_coverage_incomplete")
        paired = int(value["paired_games"])
        declared = int(value["declared_games"])
        if paired < 40:
            reasons.append("paired_games_below_40")
        if paired > declared:
            reasons.append("paired_population_exceeds_declared")
        if not value.get("freeze_manifest_sha256") or not value.get("freeze_ref"):
            reasons.append("freeze_manifest_unverified")
        if (
            pd.isna(value.get("evaluation_ref"))
            or not str(value.get("evaluation_ref", "")).strip()
        ):
            reasons.append("evaluation_missing")
        else:
            if not bool(value.get("evaluation_verified")):
                reasons.append("evaluation_not_independently_verified")
            if not value.get("evaluation_manifest_sha256") or not value.get(
                "outcome_ref"
            ):
                reasons.append("outcome_lineage_missing")
            completed_value = value.get("last_game_completed_at")
            if pd.isna(completed_value):
                reasons.append("final_completion_time_missing")
            else:
                try:
                    completed = pd.Timestamp(completed_value)
                    scored = pd.Timestamp(value["score_completed_at"])
                    if completed.tzinfo is None or scored.tzinfo is None:
                        raise ValueError
                    elapsed = (
                        scored.tz_convert("UTC") - completed.tz_convert("UTC")
                    ).total_seconds()
                    if elapsed < SCORE_STABILIZATION_SECONDS:
                        reasons.append("outcomes_not_stable_for_24h")
                except (KeyError, TypeError, ValueError):
                    reasons.append("score_completion_time_missing")
        if slate in already_counted:
            reasons.append("slate_already_disposed")
        qualified = not reasons
        if qualified:
            already_counted.add(slate)
        rows.append(
            {
                "candidate": str(value["candidate"]),
                "season": int(value["season"]),
                "week": int(value["week"]),
                "run_id": str(value["run_id"]),
                "outcome_version": value.get("outcome_version"),
                "qualifying": qualified,
                "reason": ";".join(reasons),
                "paired_games": paired,
                "freeze_ref": value.get("freeze_ref"),
                "evaluation_ref": value.get("evaluation_ref"),
                "freeze_manifest_sha256": value.get("freeze_manifest_sha256"),
                "evaluation_manifest_sha256": value.get("evaluation_manifest_sha256"),
                "supersedes_score_manifest_uri": value.get(
                    "supersedes_score_manifest_uri"
                ),
            }
        )
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(["season", "week", "run_id"], kind="mergesort")
        .reset_index(drop=True)
    )


def _independent_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"row_count": 0, "targets": {}}
    targets: dict[str, Any] = {}
    for target, subset in frame.groupby("target", sort=True):
        actual = subset["actual"].to_numpy(float)
        pred = subset["v5_mean"].to_numpy(float)
        variance = subset["v5_variance"].to_numpy(float)
        paired = subset["paired_population"].astype(bool).to_numpy()
        benchmark = subset["v4_mean"].to_numpy(float)[paired]
        if (
            not np.isfinite(actual).all()
            or not np.isfinite(pred).all()
            or not np.isfinite(variance).all()
            or (variance <= 0).any()
        ):
            raise EvidenceVerificationError("football rows contain invalid V5 values")
        if not np.isfinite(benchmark).all():
            raise EvidenceVerificationError(
                "paired football rows contain invalid V4 values"
            )
        error = pred - actual
        paired_error = benchmark - actual[paired]
        delta = np.abs(error[paired]) - np.abs(paired_error)
        interval = _paired_block_interval(subset.loc[paired], delta)
        sigma = np.sqrt(variance)
        z = (actual - pred) / sigma
        phi = np.exp(-0.5 * z * z) / np.sqrt(2 * np.pi)
        cdf = 0.5 * (1 + np.vectorize(__import__("math").erf)(z / np.sqrt(2)))
        crps = sigma * (z * (2 * cdf - 1) + 2 * phi - 1 / np.sqrt(np.pi))
        by_stage: dict[str, Any] = {}
        for stage, group in subset.groupby("completed_game_stage", sort=True):
            mask = group["paired_population"].astype(bool).to_numpy()
            stage_v4 = group["v4_mean"].to_numpy(float)[mask]
            stage_actual = group["actual"].to_numpy(float)
            by_stage[str(int(stage))] = {
                "count": int(len(group)),
                "v5_mae": float(
                    np.mean(np.abs(group["v5_mean"].to_numpy(float) - stage_actual))
                ),
                "paired_count": int(mask.sum()),
                "v4_mae_paired": float(np.mean(np.abs(stage_v4 - stage_actual[mask])))
                if mask.any()
                else None,
            }
        targets[str(target)] = {
            "count": int(len(subset)),
            "v5_mae": float(np.mean(np.abs(error))),
            "v5_rmse": float(np.sqrt(np.mean(error**2))),
            "v5_bias": float(np.mean(error)),
            "v4_count": int(paired.sum()),
            "v4_mae_paired": float(np.mean(np.abs(paired_error)))
            if paired.any()
            else None,
            "v4_rmse_paired": float(np.sqrt(np.mean(paired_error**2)))
            if paired.any()
            else None,
            "v4_bias_paired": float(np.mean(paired_error)) if paired.any() else None,
            "paired_mae_delta_v5_minus_v4": float(np.mean(delta))
            if paired.any()
            else None,
            "paired_mae_delta_ci95": interval,
            "v5_crps": float(np.mean(crps)),
            "v5_coverage_95": float(
                np.mean(np.abs(error) <= 1.959963984540054 * sigma)
            ),
            "v5_mean_interval_width_95": float(np.mean(2 * 1.959963984540054 * sigma)),
            "broader_games": int(
                subset.loc[
                    subset["broader_population"].astype(bool), "game_id"
                ].nunique()
            ),
            "paired_games": int(
                subset.loc[
                    subset["paired_population"].astype(bool), "game_id"
                ].nunique()
            ),
            "by_stage": by_stage,
        }
    return {"row_count": int(len(frame)), "targets": targets}


def _paired_block_interval(frame: pd.DataFrame, delta: np.ndarray) -> dict[str, Any]:
    if frame.empty:
        return {"estimate": None, "lower_95": None, "upper_95": None, "blocks": 0}
    keys = list(zip(frame["season"].astype(int), frame["week"].astype(int)))
    blocks = sorted(set(keys))
    estimate = float(np.mean(delta))
    if len(blocks) < 2:
        return {
            "estimate": estimate,
            "lower_95": None,
            "upper_95": None,
            "blocks": len(blocks),
            "reason": "fewer than two independent slate blocks",
        }
    values = {
        key: delta[np.array([item == key for item in keys], dtype=bool)]
        for key in blocks
    }
    generator = np.random.default_rng(20260922)
    draws = []
    for _ in range(2000):
        chosen = generator.choice(len(blocks), size=len(blocks), replace=True)
        draws.append(
            float(np.mean(np.concatenate([values[blocks[index]] for index in chosen])))
        )
    low, high = np.quantile(np.asarray(draws), [0.025, 0.975])
    return {
        "estimate": estimate,
        "lower_95": float(low),
        "upper_95": float(high),
        "blocks": len(blocks),
        "method": "paired slate-cluster bootstrap",
        "seed": 20260922,
        "samples": 2000,
    }


def _quote_summary(
    frame: pd.DataFrame, quotes: pd.DataFrame, cutoff: str
) -> dict[str, Any]:
    cap = pd.Timestamp(cutoff)
    if cap.tzinfo is None:
        raise EvidenceVerificationError("quote report cutoff must be timezone-aware")
    declared = (
        set(map(tuple, frame[["game_id", "target"]].drop_duplicates().to_numpy()))
        if {"game_id", "target"} <= set(frame)
        else set()
    )
    if quotes.empty:
        return {
            "quote_rows": 0,
            "covered_games": 0,
            "missing_games": len(declared),
            "declared_game_targets": len(declared),
            "cutoff": cap.tz_convert("UTC").isoformat(),
        }
    needed = {
        "game_id",
        "target",
        "provider",
        "quote_id",
        "captured_at",
        "effective_at",
        "line",
    }
    if not needed <= set(quotes):
        raise EvidenceVerificationError(
            "authentic quote source lacks provenance columns"
        )
    captured = pd.to_datetime(quotes["captured_at"], utc=True, errors="coerce")
    effective = pd.to_datetime(quotes["effective_at"], utc=True, errors="coerce")
    if cap.tzinfo is None or captured.isna().any() or effective.isna().any():
        raise EvidenceVerificationError("authentic quote source has invalid timestamps")
    if (captured > cap.tz_convert("UTC")).any() or (
        effective > cap.tz_convert("UTC")
    ).any():
        raise EvidenceVerificationError(
            "authentic quote timestamp exceeds report cutoff"
        )
    if quotes.duplicated(["game_id", "target", "provider", "quote_id"]).any():
        raise EvidenceVerificationError("authentic quote identity is duplicated")
    values = pd.to_numeric(quotes["line"], errors="coerce").to_numpy(float)
    if not np.isfinite(values).all():
        raise EvidenceVerificationError("authentic quote line is invalid")
    quote_keys = set(
        map(tuple, quotes[["game_id", "target"]].drop_duplicates().to_numpy())
    )
    return {
        "quote_rows": int(len(quotes)),
        "covered_games": len(declared & quote_keys),
        "missing_games": len(declared - quote_keys),
        "declared_game_targets": len(declared),
        "cutoff": cap.tz_convert("UTC").isoformat(),
        "providers": sorted(quotes["provider"].astype(str).unique().tolist()),
    }


def verify_evidence_artifact(
    storage: Any,
    *,
    manifest_uri: str,
    expected_code_sha: str,
) -> dict[str, Any]:
    """Re-read parents and independently reconstruct every immutable report."""
    raw_manifest = storage.read_bytes(manifest_uri)
    try:
        manifest = json.loads(raw_manifest)
        verify_signed_payload(manifest, label="Contract 06 evidence manifest")
    except (json.JSONDecodeError, ValueError) as exc:
        raise EvidenceVerificationError(f"evidence manifest rejected: {exc}") from exc
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("state") != "frozen"
        or manifest.get("production_activation_authorized") is not False
    ):
        raise EvidenceVerificationError(
            "evidence manifest is not a sealed Preview report"
        )
    identity = manifest.get("identity") or {}
    if (
        identity.get("environment") != "preview"
        or identity.get("code_sha") != expected_code_sha
    ):
        raise EvidenceVerificationError(
            "evidence identity environment or code SHA mismatch"
        )
    unsigned_identity = dict(identity)
    declared_identity_sha = unsigned_identity.pop("identity_sha256", None)
    if (
        hashlib.sha256(_canonical(unsigned_identity)).hexdigest()
        != declared_identity_sha
    ):
        raise EvidenceVerificationError("evidence identity digest mismatch")
    input_ref = manifest.get("input_descriptor") or {}
    input_uri = str(input_ref.get("uri", ""))
    input_raw = storage.read_bytes(input_uri)
    prefix = (
        "artifacts/research/data-first-football-v1/possession-v1/evidence/runs/"
        f"{identity.get('run_id', '')}"
    )
    if input_uri != f"{prefix}/input-descriptor.json":
        raise EvidenceVerificationError(
            "input descriptor reference is outside this run"
        )
    if (
        hashlib.sha256(input_raw).hexdigest() != input_ref.get("raw_sha256")
        or input_ref.get("raw_sha256") != identity.get("input_descriptor_sha256")
        or len(input_raw) != input_ref.get("byte_count")
    ):
        raise EvidenceVerificationError("input descriptor digest mismatch")
    config_ref = manifest.get("config_ref") or {}
    config_uri = str(config_ref.get("uri", ""))
    config_raw = storage.read_bytes(config_uri)
    if (
        config_uri != f"{prefix}/config.yaml"
        or hashlib.sha256(config_raw).hexdigest() != config_ref.get("raw_sha256")
        or config_ref.get("raw_sha256") != identity.get("config_sha256")
        or len(config_raw) != config_ref.get("byte_count")
    ):
        raise EvidenceVerificationError("Contract 06 config snapshot digest mismatch")
    descriptor = json.loads(input_raw)
    inputs = collect_verified_sources(
        storage, descriptor=descriptor, expected_code_sha=expected_code_sha
    )
    if inputs["candidate"] != manifest.get("candidate"):
        raise EvidenceVerificationError(
            "candidate differs from verified source lineage"
        )
    parents = sorted(
        inputs["parents"], key=lambda row: (str(row["role"]), str(row["uri"]))
    )
    if _canonical(parents) != _canonical(manifest.get("parents") or []):
        raise EvidenceVerificationError(
            "evidence manifest parent roles or digests differ"
        )
    attempts = inputs["attempts"]
    evaluations = inputs["evaluations"]
    if evaluations.empty:
        evaluations = pd.DataFrame(
            columns=[
                "candidate",
                "season",
                "week",
                "run_id",
                "outcome_version",
                "score_completed_at",
                "last_game_completed_at",
                "outcome_ref",
                "evaluation_ref",
                "evaluation_manifest_sha256",
                "evaluation_verified",
                "supersedes_score_manifest_uri",
            ]
        )
    ledger_rows = _independent_dispositions(
        attempts, evaluations, candidate=str(inputs["candidate"])
    )
    qualifying = int(
        ledger_rows.loc[ledger_rows["qualifying"], ["season", "week"]]
        .drop_duplicates()
        .shape[0]
    )
    reason_counts = Counter(
        reason
        for value in ledger_rows.get("reason", pd.Series(dtype=str)).astype(str)
        if value
        for reason in value.split(";")
        if reason
    )
    versions = {
        key: _independent_metrics(frame)
        for key, frame in sorted(inputs["football_by_version"].items())
    }
    aggregate = _independent_metrics(inputs["football_latest"])
    quote_population = inputs["football_quote_population"]
    quote_summary = _quote_summary(
        quote_population, inputs["quotes"], str(inputs["quote_cutoff"])
    )
    outputs = manifest.get("output_refs") or {}
    if set(outputs) != set(OUTPUT_NAMES):
        raise EvidenceVerificationError("evidence manifest has the wrong output roles")
    output_values: dict[str, Any] = {}
    for role, ref in outputs.items():
        if ref.get("uri") != f"{prefix}/{OUTPUT_NAMES[role]}":
            raise EvidenceVerificationError(
                f"{role} output reference is outside this run"
            )
        output_bytes = storage.read_bytes(str(ref.get("uri", "")))
        if hashlib.sha256(output_bytes).hexdigest() != ref.get("raw_sha256") or len(
            output_bytes
        ) != ref.get("byte_count"):
            raise EvidenceVerificationError(f"{role} output digest mismatch")
        try:
            output_values[role] = json.loads(output_bytes)
        except json.JSONDecodeError as exc:
            raise EvidenceVerificationError(f"{role} output is invalid JSON") from exc
    ledger_output = output_values["attempt_ledger"]
    expected_ledger_count = qualifying
    if (
        ledger_output.get("qualifying_slates") != expected_ledger_count
        or ledger_output.get("attempts") != _records(attempts)
        or ledger_output.get("outcome_dispositions") != _records(ledger_rows)
    ):
        raise EvidenceVerificationError(
            "attempt ledger differs from independent reconstruction"
        )
    if manifest.get("qualifying_slates") != expected_ledger_count:
        raise EvidenceVerificationError(
            "terminal qualifying count differs from independent derivation"
        )
    football = output_values["football_report"]
    expected_operational = {
        "attempted_slates": int(len(attempts)),
        "independently_verified_readiness": int(
            attempts.get("readiness_verified", pd.Series(dtype=bool)).astype(bool).sum()
        ),
        "independently_verified_freezes": int(
            attempts.get("freeze_manifest_sha256", pd.Series(dtype=str))
            .fillna("")
            .astype(str)
            .ne("")
            .sum()
        ),
        "attempt_dispositions": [
            {
                "season": int(row.season),
                "week": int(row.week),
                "run_id": str(row.run_id),
                "diagnostic_only": bool(row.diagnostic_only),
                "readiness": str(row.readiness_overall),
                "source_blocker": str(row.readiness_blocker or ""),
            }
            for row in attempts.itertuples(index=False)
        ],
    }
    if (
        not _equivalent(football.get("outcome_version_reports"), versions)
        or not _equivalent(football.get("latest_per_freeze_aggregate"), aggregate)
        or football.get("exclusion_reasons") != dict(sorted(reason_counts.items()))
        or not _equivalent(
            football.get("operational_reliability"), expected_operational
        )
        or football.get("attempted_freezes") != len(attempts)
        or football.get("verified_evaluations")
        != int(
            evaluations.get("evaluation_verified", pd.Series(dtype=bool))
            .astype(bool)
            .sum()
        )
    ):
        raise EvidenceVerificationError(
            "football report differs from independent reconstruction"
        )
    quote = output_values["quote_diagnostic"]
    if quote.get("quote_coverage") != quote_summary or quote.get(
        "declared_population", {}
    ).get("game_target_count") != quote_summary.get("declared_game_targets"):
        raise EvidenceVerificationError(
            "quote diagnostic differs from independent reconstruction"
        )
    quote_source = next(
        (
            {"uri": parent["uri"], "raw_sha256": parent["raw_sha256"]}
            for parent in parents
            if parent["role"] == "authentic_quotes"
        ),
        None,
    )
    if quote.get("source_ref") != quote_source or quote.get(
        "authentic_quote_rows"
    ) != _records(inputs["quotes"]):
        raise EvidenceVerificationError(
            "quote source lineage differs from its diagnostic"
        )
    review = inputs.get("review")
    flags = (
        {
            "validity_passed": False,
            "material_regression": False,
            "operational_problem": False,
            "satisfactory_review": False,
        }
        if review is None
        else {
            key: review.get(key)
            for key in (
                "validity_passed",
                "material_regression",
                "operational_problem",
                "satisfactory_review",
            )
        }
    )
    if any(not isinstance(value, bool) for value in flags.values()):
        raise EvidenceVerificationError("signed review judgments are incomplete")
    category = _policy_recommendation(qualifying, flags)
    blockers: list[str] = []
    if qualifying < REQUIRED_SLATES:
        blockers.append(
            f"{REQUIRED_SLATES - qualifying} additional qualifying slate(s) required"
        )
    for row in ledger_rows.loc[~ledger_rows["qualifying"].astype(bool)].itertuples(
        index=False
    ):
        blockers.append(
            f"{int(row.season)} week {int(row.week)} attempt {row.run_id}: "
            f"{row.reason or 'not qualifying'}"
        )
    if qualifying >= REQUIRED_SLATES and review is None:
        blockers.append("signed Contract 06 review input is missing")
    if qualifying >= REQUIRED_SLATES and not flags["satisfactory_review"]:
        blockers.append(
            "satisfactory football, calibration, coverage, and operations review is not recorded"
        )
    expected_review_ref = next(
        (
            {"uri": parent["uri"], "raw_sha256": parent["raw_sha256"]}
            for parent in parents
            if parent["role"] == "recommendation_review"
        ),
        None,
    )
    recommendation_output = output_values["recommendation"]
    if (
        recommendation_output.get("category") != category
        or manifest.get("recommendation") != category
        or recommendation_output.get("blockers") != blockers
        or recommendation_output.get("review_flags") != flags
        or recommendation_output.get("review_ref") != expected_review_ref
        or recommendation_output.get("production_activation_authorized") is not False
    ):
        raise EvidenceVerificationError(
            "recommendation differs from independent Contract 06 policy"
        )
    return {
        "verified": True,
        "kind": "prospective_evidence",
        "manifest_uri": manifest_uri,
        "qualifying_slates": qualifying,
        "recommendation": category,
        "output_roles": sorted(outputs),
    }


def _policy_recommendation(count: int, flags: Mapping[str, bool]) -> str:
    if count < REQUIRED_SLATES:
        return "continue_shadowing"
    if (
        not flags["validity_passed"]
        or flags["material_regression"]
        or flags["operational_problem"]
    ):
        return "retain_v4"
    if flags["satisfactory_review"]:
        return "prepare_phase7"
    return "continue_shadowing"
