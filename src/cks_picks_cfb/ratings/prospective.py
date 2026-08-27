"""Phase 5 policy, authenticity gates, and cumulative evidence contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.shadow import load_shadow_config

PROSPECTIVE_POLICY_VERSION = "prospective_evidence_v1"
FREEZE_CODE_PATHS = (
    "conf/ratings/prospective_evidence_v1.yaml",
    "conf/ratings/shadow_operations_v1.yaml",
    "conf/ratings/measurement_baseline_v3.yaml",
    "conf/ratings/team_state_baseline_v2.yaml",
    "scripts/pipeline/build_team_game_dataset.py",
    "scripts/pipeline/build_rating_shadow_freeze.py",
    "src/cks_picks_cfb/data/lake.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "src/cks_picks_cfb/ops/__main__.py",
    "src/cks_picks_cfb/ratings/contracts.py",
    "src/cks_picks_cfb/ratings/observations.py",
    "src/cks_picks_cfb/ratings/predictions.py",
    "src/cks_picks_cfb/ratings/score_models.py",
    "src/cks_picks_cfb/ratings/shadow.py",
    "src/cks_picks_cfb/ratings/snapshots.py",
    "src/cks_picks_cfb/ratings/state_contracts.py",
    "src/cks_picks_cfb/ratings/states.py",
)
EVALUATOR_CODE_PATHS = (
    "scripts/pipeline/build_rating_shadow_score.py",
    "scripts/pipeline/audit_rating_prospective_evidence.py",
    "src/cks_picks_cfb/ratings/prospective.py",
    "src/cks_picks_cfb/ratings/shadow.py",
)


def _canonical_sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _utc(value: datetime | str) -> datetime:
    parsed = pd.Timestamp(value).to_pydatetime()
    if parsed.tzinfo is None:
        raise MeasurementContractError("Prospective timestamps must include UTC offset")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProspectiveEvidencePolicy:
    raw_config: Mapping[str, Any]
    shadow_config_path: str
    shadow_design_id: str
    candidate: Mapping[str, str]
    production_v4: Mapping[str, str]
    season: int
    first_eligible_week: int
    normal_coverage_min_games: int
    target_lead_seconds: int
    hard_lead_seconds: int
    score_stabilization_seconds: int
    required_eligible_slates: int

    @property
    def policy_sha256(self) -> str:
        return _canonical_sha(self.raw_config)

    def canonical_prefix(self, shadow_prefix: str, through_week: int) -> str:
        return (
            f"{shadow_prefix}/{self.shadow_design_id}/prospective-evidence-v1/"
            f"{self.policy_sha256}/through-week={through_week:02d}"
        )


def load_prospective_policy(path: str | Path) -> ProspectiveEvidencePolicy:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("prospective_evidence_version") != PROSPECTIVE_POLICY_VERSION
    ):
        raise MeasurementContractError("Unsupported prospective evidence policy")
    try:
        policy = ProspectiveEvidencePolicy(
            raw_config=raw,
            shadow_config_path=str(raw["shadow_config_path"]),
            shadow_design_id=str(raw["shadow_design_id"]),
            candidate={str(k): str(v) for k, v in raw["candidate"].items()},
            production_v4={str(k): str(v) for k, v in raw["production_v4"].items()},
            season=int(raw["season"]),
            first_eligible_week=int(raw["first_eligible_week"]),
            normal_coverage_min_games=int(raw["normal_coverage_min_games"]),
            target_lead_seconds=int(raw["target_lead_seconds"]),
            hard_lead_seconds=int(raw["hard_lead_seconds"]),
            score_stabilization_seconds=int(raw["score_stabilization_seconds"]),
            required_eligible_slates=int(raw["required_eligible_slates"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementContractError(
            "Incomplete prospective evidence policy"
        ) from exc
    if not (policy.season == 2026 and policy.first_eligible_week >= 1):
        raise MeasurementContractError("Policy must protect 2026 Week 1 or later")
    if not (policy.normal_coverage_min_games > 0 and policy.hard_lead_seconds > 0):
        raise MeasurementContractError("Policy gates must be positive")
    if not policy.target_lead_seconds >= policy.hard_lead_seconds:
        raise MeasurementContractError("Target lead cannot be less than the hard lead")
    if policy.required_eligible_slates != 6:
        raise MeasurementContractError("Phase 5 requires exactly six eligible slates")
    shadow = load_shadow_config(policy.shadow_config_path)
    if shadow.design_id != policy.shadow_design_id:
        raise MeasurementContractError(
            "Prospective policy does not pin the shadow design"
        )
    for key, value in policy.candidate.items():
        if str(shadow.candidate.get(key)) != value:
            raise MeasurementContractError(f"Prospective candidate pin differs: {key}")
    for key, value in policy.production_v4.items():
        if str(shadow.production_v4.get(key)) != value:
            raise MeasurementContractError(f"Prospective V4 pin differs: {key}")
    return policy


def committed_code_manifest(
    *, repo_root: Path, code_sha: str | None, paths: Sequence[str], policy_sha256: str
) -> dict[str, Any]:
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    resolved_sha = code_sha or current
    if not resolved_sha:
        raise MeasurementContractError("Prospective artifacts require committed code")
    files: list[dict[str, str]] = []
    for relative in paths:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if tracked.returncode:
            raise MeasurementContractError(
                f"Prospective code path is not committed: {relative}"
            )
        if subprocess.run(
            ["git", "diff", "--quiet", resolved_sha, "--", relative],
            cwd=repo_root,
            check=False,
        ).returncode:
            raise MeasurementContractError(
                f"Prospective code path differs from lane commit: {relative}"
            )
        payload = (repo_root / relative).read_bytes()
        files.append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = {
        "code_sha": resolved_sha,
        "policy_sha256": policy_sha256,
        "files": files,
    }
    return {**manifest, "manifest_sha256": _canonical_sha(manifest)}


def validate_freeze_clock(
    *,
    requested_as_of: datetime,
    freeze_started_at: datetime,
    freeze_completed_at: datetime,
    earliest_kickoff: datetime,
    policy: ProspectiveEvidencePolicy,
) -> dict[str, float]:
    requested, started, completed, kickoff = (
        _utc(requested_as_of),
        _utc(freeze_started_at),
        _utc(freeze_completed_at),
        _utc(earliest_kickoff),
    )
    if requested > started:
        raise MeasurementContractError("Requested as-of cannot be after freeze start")
    if completed < started:
        raise MeasurementContractError("Freeze completion precedes freeze start")
    requested_lead = (kickoff - requested).total_seconds()
    measured_lead = (kickoff - completed).total_seconds()
    if measured_lead < policy.hard_lead_seconds:
        raise MeasurementContractError(
            "Candidate freeze missed the prospective hard lead"
        )
    return {
        "requested_lead_seconds": requested_lead,
        "measured_lead_seconds": measured_lead,
    }


def validate_parent_manifest(
    manifest: Mapping[str, Any],
    *,
    ref: Mapping[str, Any],
    as_of: datetime,
    freeze_started_at: datetime,
) -> None:
    if manifest.get("version_id") != ref.get("version_id") or manifest.get(
        "content_sha"
    ) != ref.get("content_sha"):
        raise MeasurementContractError("Parent ref and manifest disagree")
    parent_as_of, created_at = (
        _utc(str(manifest["as_of"])),
        _utc(str(manifest["created_at"])),
    )
    if parent_as_of > _utc(as_of):
        raise MeasurementContractError("Parent data cutoff is after freeze cutoff")
    if created_at > _utc(freeze_started_at):
        raise MeasurementContractError(
            "Parent was created after prospective freeze started"
        )


def validate_source_times(frame: pd.DataFrame, *, as_of: datetime) -> None:
    """Reject rows whose authentic capture/effective time is after the cutoff."""
    cutoff = _utc(as_of)
    for column in ("captured_at", "effective_at", "observed_at", "as_of"):
        if column not in frame:
            continue
        values = pd.to_datetime(frame[column], utc=True, errors="coerce").dropna()
        if not values.empty and values.max().to_pydatetime() > cutoff:
            raise MeasurementContractError(
                f"Source {column} exceeds the prospective data cutoff"
            )


def validate_exact_game_keys(
    *, schedule: pd.DataFrame, v4: pd.DataFrame, predictions: pd.DataFrame | None = None
) -> set[int]:
    schedule_ids = set(
        pd.to_numeric(schedule["game_id"], errors="coerce").dropna().astype(int)
    )
    v4_ids = set(pd.to_numeric(v4["game_id"], errors="coerce").dropna().astype(int))
    if not schedule_ids or schedule_ids != v4_ids:
        raise MeasurementContractError("Schedule and frozen V4 game keys differ")
    if predictions is not None:
        pairs = {
            (int(row.game_id), str(row.target))
            for row in predictions[["game_id", "target"]].itertuples(index=False)
        }
        expected = {
            (game_id, target)
            for game_id in schedule_ids
            for target in ("margin", "total")
        }
        if pairs != expected:
            raise MeasurementContractError(
                "Candidate predictions do not exactly pair frozen V4"
            )
    return schedule_ids


def descriptive_metrics(evidence: pd.DataFrame) -> dict[str, Any]:
    if evidence.empty:
        return {"rows": 0, "targets": {}}
    result: dict[str, Any] = {"rows": int(len(evidence)), "targets": {}}
    for target, rows in evidence.groupby("target", sort=True):
        actual = pd.to_numeric(rows["actual"], errors="coerce")
        candidate = pd.to_numeric(rows["prediction_mean"], errors="coerce")
        v4 = pd.to_numeric(rows["v4_prediction"], errors="coerce")
        error = candidate - actual
        result["targets"][str(target)] = {
            "count": int(len(rows)),
            "mae": float(error.abs().mean()),
            "rmse": float(np.sqrt((error**2).mean())),
            "bias": float(error.mean()),
            "paired_v4_mae_delta": float(
                error.abs().mean() - (v4 - actual).abs().mean()
            ),
        }
    return result
