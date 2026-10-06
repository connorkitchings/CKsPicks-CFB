"""Fail-closed authorization checks shared by every V5 freeze entrypoint."""

from __future__ import annotations

import os
from typing import Any

from cks_picks_cfb.artifacts import prediction_run_manifest_path, read_json_artifact
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.v5_release import (
    V5ReleaseError,
    assert_v5_database_environment,
    require_release_record,
    require_replay_release_record,
)
from cks_picks_cfb.ops.v5_revocations import (
    V5RevocationError,
    assert_release_records_active,
)


def require_v5_freeze_authorization(
    cur: Any,
    *,
    run_id: str,
    season: int,
    week: int,
    model_id: str,
    bundle_sha256: str | None,
    artifact_uri: str | None,
    artifact_sha256: str | None,
    evidence_class: str,
    environment: str,
) -> dict[str, Any]:
    """Validate exact bundle/run records and hold revocation locks to commit."""
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise V5ReleaseError("V5 freeze requires the immutable R2 artifact backend")
    assert_v5_database_environment(cur, environment)
    if not bundle_sha256:
        raise V5ReleaseError("V5 freeze run has no inference bundle identity")
    cur.execute(
        "SELECT CASE WHEN COUNT(*) = 1 THEN MIN(approval_id) ELSE NULL END "
        "FROM v5_model_bundle_approvals "
        "WHERE model_id = %s AND inference_bundle_sha256 = %s",
        (model_id, bundle_sha256),
    )
    approval = cur.fetchone()
    if approval is None or approval[0] is None:
        raise V5ReleaseError("exact V5 bundle approval is absent")
    try:
        assert_release_records_active(cur, [("bundle_approval", str(approval[0]))])
    except V5RevocationError as exc:
        raise V5ReleaseError(str(exc)) from exc

    storage = get_storage(environment=environment)
    manifest = read_json_artifact(
        prediction_run_manifest_path(season, week, run_id), storage
    )
    if (
        manifest.get("run_id") != run_id
        or manifest.get("model_id") != model_id
        or manifest.get("inference_bundle_sha256") != bundle_sha256
        or manifest.get("evidence_class") != evidence_class
        or manifest.get("artifact_uri") != artifact_uri
        or manifest.get("artifact_sha256") != artifact_sha256
    ):
        raise V5ReleaseError("V5 freeze manifest differs from the selected database run")

    if model_id == "v5-intended-update-2026-v1":
        from cks_picks_cfb.ops.v5_intended_update_release import (
            IntendedUpdateReleaseError,
            require_intended_update_release_record,
        )

        try:
            require_intended_update_release_record(
                cur,
                manifest=manifest,
                storage=storage,
                season=season,
                week=week,
                environment=environment,
            )
        except IntendedUpdateReleaseError as exc:
            raise V5ReleaseError(str(exc)) from exc
    elif evidence_class == "replay":
        require_replay_release_record(
            cur,
            manifest=manifest,
            storage=storage,
            environment=environment,
            season=season,
            week=week,
        )
    elif environment == "production":
        require_release_record(
            cur, manifest=manifest, storage=storage, season=season, week=week
        )
    return manifest
