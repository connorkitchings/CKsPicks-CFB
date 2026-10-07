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
            raise ProspectiveRecordError(
                f"immutable prospective receipt already differs: {uri}"
            )
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
        raise ProspectiveRecordError(
            "only a packet-authorized 2026 Week 5+ freeze is prospective"
        )
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
        raise ProspectiveRecordError(
            "same frozen run has conflicting prospective receipt"
        )
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


LEGACY_SCHEMA = "v5_legacy_freeze_attestation_v1"
LEGACY_LIMITATIONS = [
    "No contemporaneous freeze receipt exists in the bounded retained-source search.",
    "This retrospective attestation was prepared after kickoff; it is not an original receipt.",
    "The canonical checksum establishes content integrity, not cryptographic signer authentication.",
]
PREVIEW_PIPELINE_LIMITATION = (
    "In Preview staging, the original Week 5 freeze was executed directly via "
    "freeze_week.py and recorded in ops.activation_history without an enclosing "
    "ops.pipeline_runs harness record."
)


def legacy_limitations_for_environment(
    environment: str, *, has_pipeline: bool = True
) -> list[str]:
    if environment == "preview" and not has_pipeline:
        return [*LEGACY_LIMITATIONS, PREVIEW_PIPELINE_LIMITATION]
    return list(LEGACY_LIMITATIONS)


def _utc(value: Any) -> datetime:
    from datetime import timezone

    result = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if result.tzinfo is None:
        raise ProspectiveRecordError("evidence timestamp must include timezone")
    return result.astimezone(timezone.utc)


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, default=lambda item: item.isoformat()))


def read_legacy_freeze_sources(
    cur: Any, *, environment: str, run_id: str
) -> dict[str, Any]:
    """Re-read the complete original slate timeline without trusting current selection."""
    from cks_picks_cfb.ops.v5_release import assert_v5_database_environment

    assert_v5_database_environment(cur, environment)

    def rows(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        cur.execute(sql, params)
        return _json_value(
            [
                dict(zip([col.name for col in cur.description], row, strict=True))
                for row in cur.fetchall()
            ]
        )

    runs = rows(
        "SELECT * FROM prediction_runs WHERE season=2026 AND week=5 ORDER BY created_at,run_id",
        (),
    )
    history = rows(
        "SELECT * FROM site_week_selection_history WHERE season=2026 AND week=5 ORDER BY selected_at,selection_id",
        (),
    )
    activations = rows(
        "SELECT * FROM ops.activation_history WHERE season=2026 AND week=5 ORDER BY activated_at,activation_id",
        (),
    )
    pipelines = rows(
        "SELECT * FROM ops.pipeline_runs WHERE season=2026 AND week=5 ORDER BY started_at,pipeline_run_id",
        (),
    )
    steps = rows(
        "SELECT s.* FROM ops.pipeline_steps s JOIN ops.pipeline_runs p USING(pipeline_run_id) WHERE p.season=2026 AND p.week=5 ORDER BY p.started_at,s.ordinal",
        (),
    )
    schedule = rows(
        "SELECT g.game_id,g.start_date FROM games g JOIN predictions p USING(game_id) WHERE p.run_id=%s ORDER BY g.game_id",
        (run_id,),
    )
    return dict(
        environment=environment,
        runs=runs,
        selection_history=history,
        activations=activations,
        pipelines=pipelines,
        steps=steps,
        schedule=schedule,
    )


def _derive_legacy_evidence(
    sources: Mapping[str, Any], *, run_id: str, environment: str
) -> dict[str, Any]:
    if sources.get("environment") != environment or environment not in {
        "preview",
        "production",
    }:
        raise ProspectiveRecordError("legacy source environment differs")
    runs = {r["run_id"]: r for r in sources["runs"]}
    run = runs.get(run_id)
    if (
        not run
        or run.get("season") != 2026
        or run.get("week") != 5
        or run.get("model_id") != "v5-intended-update-2026-v1"
        or run.get("evidence_class") != "live"
    ):
        raise ProspectiveRecordError(
            "legacy attestation is restricted to original 2026 Week 5 V5"
        )
    schedule = sources["schedule"]
    if (
        not schedule
        or len({r["game_id"] for r in schedule}) != len(schedule)
        or len(schedule) != run["expected_games"]
    ):
        raise ProspectiveRecordError("original slate schedule coverage is incomplete")
    kickoff = min(_utc(r["start_date"]) for r in schedule)
    frozen = _utc(run["frozen_at"])
    if frozen >= kickoff or run.get("state") not in {"frozen", "scored"}:
        raise ProspectiveRecordError("original freeze is not before kickoff")
    history = sources["selection_history"]
    ordered = sorted(history, key=lambda r: (_utc(r["selected_at"]), r["selection_id"]))
    if history != ordered or len({r["selection_id"] for r in history}) != len(history):
        raise ProspectiveRecordError("selection history is ambiguous or unordered")
    pre = [r for r in history if _utc(r["selected_at"]) < kickoff]
    if not pre or pre[-1]["run_id"] != run_id:
        raise ProspectiveRecordError(
            "run is not the last publicly selected run before kickoff"
        )
    for previous, current in zip(history, history[1:]):
        if current["prior_run_id"] != previous["run_id"]:
            raise ProspectiveRecordError("selection history chain conflicts")
    freezes = [
        r
        for r in sources["activations"]
        if r["run_id"] == run_id and r["action"] == "freeze"
    ]
    if len(freezes) != 1:
        raise ProspectiveRecordError(
            "original freeze activation is missing or ambiguous"
        )
    activation = freezes[0]
    if (
        activation["environment"] != environment
        or _utc(activation["activated_at"]) != frozen
        or activation["metadata"].get("freeze_coverage_complete") is not True
    ):
        raise ProspectiveRecordError("original freeze activation conflicts")
    candidates = []
    for pipeline in sources["pipelines"]:
        if (
            pipeline["environment"] != environment
            or pipeline["command"] != "freeze-week"
            or pipeline["state"] != "succeeded"
        ):
            continue
        if not (
            _utc(pipeline["started_at"])
            <= frozen
            <= _utc(pipeline["finished_at"])
            < kickoff
        ):
            continue
        for step in sources["steps"]:
            if (
                step["pipeline_run_id"] == pipeline["pipeline_run_id"]
                and step["step_name"] == "freeze"
                and step["state"] == "succeeded"
                and step["error_category"] is None
            ):
                outputs = step["output_refs"]
                if (
                    len(outputs) == 1
                    and outputs[0].get("returncode") == 0
                    and "scripts/pipeline/freeze_week.py" in outputs[0].get("argv", [])
                ):
                    candidates.append(dict(pipeline=pipeline, step=step))
    freeze_week_pipelines = [
        p
        for p in sources["pipelines"]
        if p.get("environment") == environment and p.get("command") == "freeze-week"
    ]
    if len(candidates) == 1:
        freeze_pipeline = candidates[0]
    elif (
        environment == "preview"
        and len(candidates) == 0
        and len(freeze_week_pipelines) == 0
    ):
        freeze_pipeline = None
    else:
        raise ProspectiveRecordError(
            "successful original freeze pipeline/step is missing or ambiguous"
        )
    return dict(
        run_frozen_at=frozen.isoformat(),
        first_kickoff_utc=kickoff.isoformat(),
        freeze_activation=activation,
        pre_kickoff_selection_history=pre,
        later_selection_history=[
            r for r in history if _utc(r["selected_at"]) >= kickoff
        ],
        freeze_pipeline=freeze_pipeline,
        current_schedule_check=schedule,
    )


def build_legacy_freeze_attestation(
    *,
    sources: Mapping[str, Any],
    environment: str,
    run_id: str,
    decision_ref: str,
    historical_freeze_code_sha: str,
    original_prediction_manifest: Mapping[str, Any],
    original_prediction_artifact: Mapping[str, Any],
    contemporaneous_schedule_evidence: Mapping[str, Any],
    source_snapshot_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create actual-time retrospective evidence; caller cannot supply attested_at."""
    from datetime import timezone

    evidence = _derive_legacy_evidence(sources, run_id=run_id, environment=environment)
    if (
        not decision_ref.strip()
        or len(historical_freeze_code_sha) != 40
        or not source_snapshot_refs
    ):
        raise ProspectiveRecordError(
            "decision, historical code or source snapshots are missing"
        )
    now = datetime.now(timezone.utc)
    if now <= _utc(evidence["first_kickoff_utc"]):
        raise ProspectiveRecordError("legacy attestation must be created after kickoff")
    return signed_payload(
        _json_value(
            dict(
                schema_version=LEGACY_SCHEMA,
                evidence_class="legacy_attested_prospective",
                environment=environment,
                season=2026,
                week=5,
                run_id=run_id,
                attested_at=now.isoformat(),
                decision_ref=decision_ref,
                historical_freeze_code_sha=historical_freeze_code_sha,
                original_prediction_manifest=dict(original_prediction_manifest),
                original_prediction_artifact=dict(original_prediction_artifact),
                contemporaneous_schedule_evidence=dict(
                    contemporaneous_schedule_evidence
                ),
                source_snapshot_refs=source_snapshot_refs,
                limitations=legacy_limitations_for_environment(
                    environment,
                    has_pipeline=(evidence.get("freeze_pipeline") is not None),
                ),
                **evidence,
            )
        )
    )


def legacy_attestation_uri(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return (
        f"artifacts/prospective/v5/environment={payload['environment']}/season=2026/week=5/"
        f"{payload['run_id']}/legacy-attestation-v1-{digest}.json"
    )


def verify_legacy_freeze_attestation(
    payload: Mapping[str, Any], *, cur: Any, storage: Any, environment: str
) -> None:
    """Verify content integrity and independently re-read DB and immutable source bytes."""
    verify_signed_payload(dict(payload), label="legacy freeze attestation")
    expected_limitations = legacy_limitations_for_environment(
        environment,
        has_pipeline=(payload.get("freeze_pipeline") is not None),
    )
    if (
        payload.get("schema_version") != LEGACY_SCHEMA
        or payload.get("evidence_class") != "legacy_attested_prospective"
        or payload.get("season") != 2026
        or payload.get("week") != 5
        or payload.get("environment") != environment
        or payload.get("limitations") != expected_limitations
        or not str(payload.get("decision_ref") or "").strip()
    ):
        raise ProspectiveRecordError(
            "legacy attestation schema, scope or disclosure differs"
        )
    from datetime import timezone

    if not (
        _utc(payload["first_kickoff_utc"])
        < _utc(payload["attested_at"])
        <= datetime.now(timezone.utc)
    ):
        raise ProspectiveRecordError("legacy creation timestamp is invalid")
    sources = read_legacy_freeze_sources(
        cur, environment=environment, run_id=payload["run_id"]
    )
    derived = _derive_legacy_evidence(
        sources, run_id=payload["run_id"], environment=environment
    )
    if any(payload.get(key) != value for key, value in derived.items()):
        raise ProspectiveRecordError("live original source evidence changed")

    def read(ref: Mapping[str, Any]) -> bytes:
        raw = storage.read_bytes(ref["uri"])
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ProspectiveRecordError("legacy immutable source hash differs")
        return raw

    snapshots = payload["source_snapshot_refs"]
    if len(snapshots) != 2 or json.loads(read(snapshots[0])) != sources:
        raise ProspectiveRecordError(
            "retained query snapshot differs from live sources"
        )
    code = json.loads(read(snapshots[1]))
    import subprocess

    code_sha = payload["historical_freeze_code_sha"]
    if len(code_sha) != 40 or any(c not in "0123456789abcdef" for c in code_sha):
        raise ProspectiveRecordError("historical code identity is invalid")
    original_code = subprocess.check_output(
        ["git", "show", code_sha + ":scripts/pipeline/freeze_week.py"], text=True
    )
    committed_at = int(
        subprocess.check_output(
            ["git", "show", "-s", "--format=%ct", code_sha], text=True
        )
    )
    if (
        code.get("freeze_source") != original_code
        or committed_at > _utc(payload["run_frozen_at"]).timestamp()
    ):
        raise ProspectiveRecordError(
            "historical freeze source is not authentic pre-freeze code"
        )
    if code.get("code_sha") != payload["historical_freeze_code_sha"] or not code.get(
        "freeze_source"
    ):
        raise ProspectiveRecordError("historical freeze code evidence differs")
    run = next(r for r in sources["runs"] if r["run_id"] == payload["run_id"])
    manifest_ref = payload["original_prediction_manifest"]
    expected_prefix = f"artifacts/{environment}/predictions/year=2026/week=5/run_id={payload['run_id']}/"
    if manifest_ref["uri"] != expected_prefix + "manifest.json":
        raise ProspectiveRecordError("original manifest environment/run differs")
    manifest = json.loads(read(manifest_ref))
    artifact_ref = payload["original_prediction_artifact"]
    read(artifact_ref)
    identity_keys = (
        "run_id",
        "season",
        "week",
        "model_id",
        "model_bundle_sha256",
        "config_sha",
    )
    if (
        artifact_ref["uri"] != run["artifact_uri"]
        or artifact_ref["sha256"] != run["artifact_sha256"]
        or manifest.get("artifact_uri") != artifact_ref["uri"]
        or manifest.get("artifact_sha256") != artifact_ref["sha256"]
        or any(manifest.get(k) != run.get(k) for k in identity_keys)
        or _utc(manifest["data_as_of"]) != _utc(run["data_as_of"])
    ):
        raise ProspectiveRecordError("original prediction identity differs")
    import io

    import pandas as pd

    schedule_ref = payload["contemporaneous_schedule_evidence"]
    if schedule_ref["uri"] not in [
        r["uri"] for r in run["input_dataset_refs"] if r.get("dataset") == "games"
    ]:
        raise ProspectiveRecordError("schedule is not pinned by the original run")
    frame = pd.read_parquet(io.BytesIO(read(schedule_ref)))
    frame = frame[frame["game_id"].isin([r["game_id"] for r in sources["schedule"]])]
    if "kickoff_utc" not in frame or frame["game_id"].duplicated().any():
        raise ProspectiveRecordError(
            "retained games_v2 schedule keys or kickoff column are invalid"
        )
    if "__captured_at" not in frame or any(
        _utc(value) >= _utc(payload["run_frozen_at"])
        for value in frame["__captured_at"]
    ):
        raise ProspectiveRecordError(
            "schedule capture is not contemporaneous pre-freeze evidence"
        )
    retained = {
        str(r["game_id"]): _utc(r["kickoff_utc"]) for r in frame.to_dict("records")
    }

    current = {str(r["game_id"]): _utc(r["start_date"]) for r in sources["schedule"]}
    if retained != current:
        raise ProspectiveRecordError("contemporaneous and current schedule disagree")


def verify_prospective_record(
    row: Mapping[str, Any], *, cur: Any, storage: Any, environment: str
) -> None:
    uri = row["freeze_receipt_uri"]
    raw = storage.read_bytes(uri)
    if hashlib.sha256(raw).hexdigest() != row["freeze_receipt_sha256"]:
        raise ProspectiveRecordError("prospective receipt raw checksum differs")
    payload = json.loads(raw)
    verify_signed_payload(payload, label="prospective evidence")
    if "/legacy-attestation-v1-" in uri:
        if uri != legacy_attestation_uri(payload):
            raise ProspectiveRecordError("legacy URI kind or identity differs")
        verify_legacy_freeze_attestation(
            payload, cur=cur, storage=storage, environment=environment
        )
        frozen = payload["run_frozen_at"]
    elif (
        "/freeze-" in uri
        and payload.get("schema_version") == "v5_prospective_freeze_receipt_v1"
    ):
        expected_uri = (
            f"artifacts/prospective/v5/season={row['season']}/week={row['week']}/"
            f"{row['run_id']}/freeze-{row['freeze_receipt_sha256']}.json"
        )
        if uri != expected_uri or payload.get("state") != "frozen":
            raise ProspectiveRecordError("ordinary receipt URI or state differs")
        frozen = payload["frozen_at"]
    else:
        raise ProspectiveRecordError("unknown prospective receipt kind")
    if _utc(frozen) >= _utc(payload["first_kickoff_utc"]):
        raise ProspectiveRecordError("receipt freeze must precede kickoff")
    if (
        any(
            payload.get(k) != row[k]
            for k in ("season", "week", "run_id", "decision_ref")
        )
        or payload.get("environment") != environment
        or _utc(frozen) != _utc(row["frozen_at"])
        or _utc(payload["first_kickoff_utc"]) != _utc(row["first_kickoff_utc"])
    ):
        raise ProspectiveRecordError("prospective designation differs from receipt")


def register_legacy_freeze_attestation(
    cur: Any, *, storage: Any, environment: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Insert only; an exact retry is a no-op and cannot reassign historical evidence."""
    verify_legacy_freeze_attestation(
        payload, cur=cur, storage=storage, environment=environment
    )
    raw = canonical_json(payload)
    uri = legacy_attestation_uri(payload)
    sha = hashlib.sha256(raw).hexdigest()
    values = (
        payload["run_id"],
        uri,
        sha,
        _utc(payload["run_frozen_at"]),
        _utc(payload["first_kickoff_utc"]),
        payload["decision_ref"],
    )
    query = (
        "SELECT run_id,freeze_receipt_uri,freeze_receipt_sha256,frozen_at,first_kickoff_utc,decision_ref "
        "FROM public.prospective_week_records WHERE season=2026 AND week=5"
    )
    cur.execute(query)
    prior = cur.fetchone()
    if prior is not None and tuple(prior) != values:
        raise ProspectiveRecordError(
            "existing legacy prospective designation conflicts"
        )
    if prior is None:
        write_immutable(storage, uri, raw)
        cur.execute(
            "INSERT INTO public.prospective_week_records "
            "(season,week,run_id,freeze_receipt_uri,freeze_receipt_sha256,frozen_at,first_kickoff_utc,decision_ref) "
            "VALUES (2026,5,%s,%s,%s,%s,%s,%s)",
            values,
        )
    elif storage.read_bytes(uri) != raw:
        raise ProspectiveRecordError("existing attestation bytes differ")
    cur.execute(query)
    if tuple(cur.fetchone() or ()) != values:
        raise ProspectiveRecordError("legacy registration readback differs")
    return dict(
        uri=uri, sha256=sha, receipt=dict(payload), idempotent=prior is not None
    )
