"""Immutable evidence helpers for original V5 prospective freeze records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload


class ProspectiveRecordError(ValueError):
    """A prospective freeze receipt or database designation conflicts."""


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def write_immutable(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        existing = storage.read_bytes(uri)
        if existing != raw:
            raise ProspectiveRecordError(f"immutable prospective receipt already differs: {uri}")
        return
    storage.write_bytes(raw, uri)
    if storage.read_bytes(uri) != raw:
        raise ProspectiveRecordError("prospective freeze receipt failed readback")


def register_prospective_freeze(
    cur: Any,
    *,
    storage: Any,
    environment: str,
    season: int,
    week: int,
    run_id: str,
    model_id: str,
    bundle_sha256: str,
    prediction_artifact_uri: str,
    prediction_artifact_sha256: str,
    manifest_uri: str,
    manifest_sha256: str,
    frozen_at: datetime,
    first_kickoff_utc: datetime,
    decision_ref: str,
    code_sha: str,
) -> dict[str, Any]:
    """Persist a content-signed receipt and same-transaction DB designation."""
    if season != 2026 or week < 5 or not decision_ref.strip():
        raise ProspectiveRecordError("only a packet-authorized 2026 Week 5+ freeze is prospective")
    receipt = signed_payload(
        {
            "schema_version": "v5_prospective_freeze_receipt_v1",
            "state": "frozen",
            "environment": environment,
            "season": season,
            "week": week,
            "run_id": run_id,
            "model_id": model_id,
            "inference_bundle_sha256": bundle_sha256,
            "prediction_artifact_uri": prediction_artifact_uri,
            "prediction_artifact_sha256": prediction_artifact_sha256,
            "forecast_manifest_uri": manifest_uri,
            "forecast_manifest_sha256": manifest_sha256,
            "frozen_at": frozen_at.isoformat(),
            "first_kickoff_utc": first_kickoff_utc.isoformat(),
            "decision_ref": decision_ref,
            "code_sha": code_sha,
        }
    )
    verify_signed_payload(receipt, label="prospective freeze receipt")
    raw = canonical_json(receipt)
    receipt_sha = hashlib.sha256(raw).hexdigest()
    uri = (
        f"artifacts/prospective/v5/season={season}/week={week}/"
        f"{run_id}/freeze-{receipt_sha}.json"
    )
    write_immutable(storage, uri, raw)

    cur.execute(
        "SELECT run_id, freeze_receipt_uri, freeze_receipt_sha256, frozen_at, "
        "first_kickoff_utc, decision_ref FROM public.prospective_week_records "
        "WHERE season = %s AND week = %s FOR UPDATE",
        (season, week),
    )
    prior = cur.fetchone()
    values = (run_id, uri, receipt_sha, frozen_at, first_kickoff_utc, decision_ref)
    if prior is None:
        cur.execute(
            "INSERT INTO public.prospective_week_records "
            "(season, week, run_id, freeze_receipt_uri, freeze_receipt_sha256, "
            "frozen_at, first_kickoff_utc, decision_ref) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (season, week, *values),
        )
    elif tuple(prior) == values:
        pass
    elif prior[0] == run_id:
        raise ProspectiveRecordError("same frozen run has conflicting prospective receipt")
    else:
        cur.execute(
            "UPDATE public.prospective_week_records SET run_id = %s, "
            "freeze_receipt_uri = %s, freeze_receipt_sha256 = %s, frozen_at = %s, "
            "first_kickoff_utc = %s, decision_ref = %s WHERE season = %s AND week = %s",
            (*values, season, week),
        )
    cur.execute(
        "SELECT run_id, freeze_receipt_uri, freeze_receipt_sha256, frozen_at, "
        "first_kickoff_utc, decision_ref FROM public.prospective_week_records "
        "WHERE season = %s AND week = %s",
        (season, week),
    )
    if tuple(cur.fetchone() or ()) != values:
        raise ProspectiveRecordError("prospective freeze record readback differs")
    return {"uri": uri, "sha256": receipt_sha, "receipt": receipt}
