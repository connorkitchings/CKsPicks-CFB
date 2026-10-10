"""Pure builders for the signed successor cutover packets.

The authorization packet (``v5_intended_update_authorization_packet_v1``) registers one
bundle approval plus one run authorization per week 0..N. The selection packet
(``v5_intended_update_batch_selection_v2``) atomically swaps the public selection to those
runs; the rollback packet is its exact inverse. Every packet is built from retained
``prediction_run_v1`` manifests and is checked by the same validators that apply it, so a
packet that this module emits cannot pass here and fail there for a structural reason.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_intended_update_release import AUTH_COLUMNS
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

AUTHORIZATION_SCHEMA = "v5_intended_update_authorization_packet_v1"
SELECTION_SCHEMA = "v5_intended_update_batch_selection_v2"
ROLLBACK_SCHEMA = "v5_intended_update_batch_rollback_v2"
BUNDLE_FIELDS = (
    "approval_id",
    "model_id",
    "inference_bundle_sha256",
    "first_live_season",
    "first_live_week",
    "decision_ref",
)
PAYLOAD_REFS = (
    "team_stats_before",
    "team_stats_after",
    "team_stats_verifier",
    "prospective_records_before",
    "prospective_records_after",
)


class PacketBuildError(ValueError):
    """The inputs cannot form a packet that the controller would accept."""


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def authorization_record(
    manifest: Mapping[str, Any], *, environment: str, decision_ref: str
) -> dict[str, Any]:
    """Bind one run authorization to every immutable hash in a packaged run manifest."""
    if not str(decision_ref).strip():
        raise PacketBuildError("a decision reference is required")
    if environment not in {"preview", "production"}:
        raise PacketBuildError("environment must be preview or production")
    namespace = f"/{environment}/"
    if namespace not in str(manifest.get("artifact_uri")):
        raise PacketBuildError(
            f"run {manifest.get('run_id')} artifact is not in the {environment} namespace"
        )
    return {
        "authorization_id": (
            f"{environment}-{manifest['run_id']}-{manifest['artifact_sha256'][:12]}"
        ),
        "environment": environment,
        "season": 2026,
        "week": int(manifest["week"]),
        "prediction_run_id": manifest["run_id"],
        "evidence_class": manifest["evidence_class"],
        "model_id": manifest["model_id"],
        "inference_bundle_sha256": manifest["inference_bundle_sha256"],
        "rating_manifest_sha256": manifest["v5_rating_replay_manifest_sha256"],
        "forecast_manifest_uri": manifest["v5_live_forecast_manifest_uri"],
        "forecast_manifest_sha256": manifest["v5_live_forecast_manifest_sha256"],
        "serving_manifest_uri": manifest["v5_intended_update_serving_manifest_uri"],
        "serving_manifest_sha256": manifest[
            "v5_intended_update_serving_manifest_sha256"
        ],
        "verifier_uri": manifest["v5_intended_update_verifier_uri"],
        "verifier_sha256": manifest["v5_intended_update_verifier_sha256"],
        "prediction_artifact_uri": manifest["artifact_uri"],
        "prediction_artifact_sha256": manifest["artifact_sha256"],
        "decision_ref": decision_ref,
    }


def bundle_approval(
    *,
    model_id: str,
    inference_bundle_sha256: str,
    cutover_week: int,
    decision_ref: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    body = {
        "approval_id": approval_id
        or f"bundle-{inference_bundle_sha256[:12]}-w{cutover_week}",
        "model_id": model_id,
        "inference_bundle_sha256": inference_bundle_sha256,
        "first_live_season": 2026,
        "first_live_week": cutover_week,
        "decision_ref": decision_ref,
    }
    return {**body, "record_sha256": _sha(body)}


def _signed_authorizations(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**record, "record_sha256": _sha({key: record[key] for key in AUTH_COLUMNS})}
        for record in records
    ]


def registered_bundle_approval(
    registered: Mapping[str, Any], *, model_id: str, inference_bundle_sha256: str
) -> dict[str, Any]:
    """Re-sign an approval row that is already registered, unchanged.

    The registry keeps one approval per model and bundle, so a bundle first approved for an
    earlier display-only week is carried into the cutover packet exactly as registered
    (its first live week and decision reference are not rewritten).
    """
    if set(registered) != set(BUNDLE_FIELDS):
        raise PacketBuildError(
            f"registered bundle approval must have exactly: {', '.join(BUNDLE_FIELDS)}"
        )
    body = {key: registered[key] for key in BUNDLE_FIELDS}
    if (
        body["model_id"] != model_id
        or body["inference_bundle_sha256"] != inference_bundle_sha256
        or body["first_live_season"] != 2026
    ):
        raise PacketBuildError("registered bundle approval is for another bundle")
    return {**body, "record_sha256": _sha(body)}


def registered_authorization_record(
    row: Mapping[str, Any], *, manifest: Mapping[str, Any], environment: str, week: int
) -> dict[str, Any]:
    """Re-sign a release authorization that is already registered, unchanged.

    A rollback restores runs that were released earlier under their own decisions, so
    their registered rows are carried verbatim; only identity against the run's retained
    manifest is checked here (the controller re-reads the row and re-validates the
    source chain at apply time).
    """
    if set(row) != set(AUTH_COLUMNS):
        raise PacketBuildError(
            "registered authorization must have exactly the authorization columns"
        )
    body = {key: row[key] for key in AUTH_COLUMNS}
    if (
        body["environment"] != environment
        or body["season"] != 2026
        or body["week"] != week
        or body["prediction_run_id"] != manifest.get("run_id")
        or body["evidence_class"] != manifest.get("evidence_class")
        or body["model_id"] != manifest.get("model_id")
        or body["inference_bundle_sha256"] != manifest.get("inference_bundle_sha256")
    ):
        raise PacketBuildError(
            f"registered Week {week} authorization is for another run or environment"
        )
    return {**body, "record_sha256": _sha(body)}


def _records_for_cutover(
    manifests: Mapping[int, Mapping[str, Any]],
    *,
    environment: str,
    cutover_week: int,
    decision_ref: str,
    registered_bundle: Mapping[str, Any] | None = None,
    last_week: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Authorization records and the bundle approval for ``manifests``.

    ``last_week`` is the last week the manifests cover (default: the cutover week). An
    advance rollback restores only Weeks 0..N-1, so it passes ``cutover_week - 1``.
    """
    if not isinstance(cutover_week, int) or cutover_week < 5:
        raise PacketBuildError("cutover week must be an integer of at least 5")
    last = cutover_week if last_week is None else last_week
    if sorted(manifests) != list(range(last + 1)):
        raise PacketBuildError("manifests must cover contiguous Weeks 0 through N")
    models = {m["model_id"] for m in manifests.values()}
    bundles = {m["inference_bundle_sha256"] for m in manifests.values()}
    if len(models) != 1 or len(bundles) != 1:
        raise PacketBuildError("every run must share one model and inference bundle")
    records = []
    for week in range(last + 1):
        manifest = manifests[week]
        expected = "pending" if week == cutover_week else "replay"
        if manifest.get("evidence_class") != expected:
            raise PacketBuildError(
                f"Week {week} run is {manifest.get('evidence_class')}, expected {expected}"
            )
        records.append(
            authorization_record(
                manifest, environment=environment, decision_ref=decision_ref
            )
        )
    model_id, bundle_sha = models.pop(), bundles.pop()
    if registered_bundle is not None:
        bundle = registered_bundle_approval(
            registered_bundle, model_id=model_id, inference_bundle_sha256=bundle_sha
        )
    else:
        bundle = bundle_approval(
            model_id=model_id,
            inference_bundle_sha256=bundle_sha,
            cutover_week=cutover_week,
            decision_ref=decision_ref,
        )
    return records, bundle


def build_authorization_packet(
    manifests: Mapping[int, Mapping[str, Any]],
    *,
    environment: str,
    cutover_week: int,
    decision_ref: str,
    registered_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    records, bundle = _records_for_cutover(
        manifests,
        environment=environment,
        cutover_week=cutover_week,
        decision_ref=decision_ref,
        registered_bundle=registered_bundle,
    )
    return signed_payload(
        {
            "schema_version": AUTHORIZATION_SCHEMA,
            "environment": environment,
            "season": 2026,
            "cutover_week": cutover_week,
            "decision_ref": decision_ref,
            "bundle_approval": bundle,
            "run_authorizations": _signed_authorizations(records),
        }
    )


def build_selection_packet(
    manifests: Mapping[int, Mapping[str, Any]],
    *,
    environment: str,
    cutover_week: int,
    decision_ref: str,
    expected_current_runs: Mapping[int, str],
    protected_runs: Mapping[int, str],
    certifications: list[Mapping[str, Any]],
    payload_refs: Mapping[str, Mapping[str, Any]],
    registered_bundle: Mapping[str, Any] | None = None,
    advance: bool = False,
) -> dict[str, Any]:
    """Build the signed select packet.

    ``certifications`` are ``{uri, sha256, week}`` refs for Weeks 0..N-1 and
    ``payload_refs`` carries the five retained signed payload refs. ``registered_bundle``
    carries an approval row that is already registered (see ``registered_bundle_approval``).

    ``advance`` opens Week N, which has no public selection yet: ``expected_current_runs``
    then covers Weeks 0..N-1 (the site is at Week N-1) and the packet selects Weeks 0..N
    and moves the current week to N in one transaction.
    """
    records, bundle = _records_for_cutover(
        manifests,
        environment=environment,
        cutover_week=cutover_week,
        decision_ref=decision_ref,
        registered_bundle=registered_bundle,
    )
    weeks = list(range(cutover_week + 1))
    before_weeks = weeks[:-1] if advance else weeks
    if sorted(expected_current_runs) != before_weeks:
        raise PacketBuildError(
            "expected current runs must cover Weeks 0 through "
            + ("N-1 (advance)" if advance else "N")
        )
    replacement = {week: manifests[week]["run_id"] for week in weeks}
    if set(expected_current_runs.values()) & set(replacement.values()):
        raise PacketBuildError("replacement runs reuse a currently selected run")
    if set(protected_runs) & set(weeks):
        raise PacketBuildError("protected runs overlap the replacement slate")
    # Empty is valid when the cutover replaces every existing selection.
    if missing := [name for name in PAYLOAD_REFS if name not in payload_refs]:
        raise PacketBuildError(f"payload refs missing: {', '.join(missing)}")
    if sorted(c.get("week") for c in certifications) != list(range(cutover_week)):
        raise PacketBuildError("certifications must cover Weeks 0 through N-1")
    return signed_payload(
        {
            "schema_version": SELECTION_SCHEMA,
            "environment": environment,
            "season": 2026,
            "cutover_week": cutover_week,
            "decision_ref": decision_ref,
            **({"opens_week": cutover_week} if advance else {}),
            "expected_current_runs": {
                str(w): expected_current_runs[w] for w in before_weeks
            },
            "replacement_runs": {str(w): replacement[w] for w in weeks},
            "certified_completed_weeks": list(range(cutover_week)),
            "protected_runs": {str(w): r for w, r in sorted(protected_runs.items())},
            "expected_current_week": {
                "season": 2026,
                "week": before_weeks[-1],
                "run_id": expected_current_runs[before_weeks[-1]],
            },
            "replacement_current_week": {
                "season": 2026,
                "week": cutover_week,
                "run_id": replacement[cutover_week],
            },
            "bundle_approval": bundle,
            "run_authorizations": _signed_authorizations(records),
            "completed_week_certifications": [dict(c) for c in certifications],
            **{name: dict(payload_refs[name]) for name in PAYLOAD_REFS},
        }
    )


def build_rollback_packet(
    selection: Mapping[str, Any],
    *,
    prior_manifests: Mapping[int, Mapping[str, Any]],
    certifications: list[Mapping[str, Any]] | None = None,
    payload_refs: Mapping[str, Mapping[str, Any]],
    registered_bundle: Mapping[str, Any] | None = None,
    registered_bundles: list[Mapping[str, Any]] | None = None,
    registered_authorizations: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Invert a select packet.

    The prior runs become the replacement, so each needs an authorization record and
    team-stats refs whose before/after are swapped (``payload_refs``).

    Normally the prior runs were released earlier under their own registered
    authorizations and bundle approvals (possibly two bundles, as with the repaired
    Weeks 0-5 and the successor Week 6): pass them as ``registered_authorizations``
    (week -> registered row) and ``registered_bundles`` and they are carried verbatim.
    Without them, records are built from ``prior_manifests`` under the packet decision
    (only valid for a rollback set that is registered at the cutover).
    ``certifications`` are optional: a rollback restores history that needs no fresh
    finals certification.
    """
    if selection.get("schema_version") != SELECTION_SCHEMA:
        raise PacketBuildError("rollback requires a select packet")
    cutover = selection["cutover_week"]
    environment = selection["environment"]
    decision_ref = selection["decision_ref"]
    prior = {int(w): r for w, r in selection["expected_current_runs"].items()}
    certifications = certifications or []
    extra_bundles: list[dict[str, Any]] = []
    # An advance packet opened Week N, so its rollback restores Weeks 0..N-1 only.
    if registered_authorizations is not None:
        last = max(prior)
        if sorted(prior_manifests) != list(range(last + 1)) or sorted(
            registered_authorizations
        ) != list(range(last + 1)):
            raise PacketBuildError(
                "prior manifests and registered authorizations must cover the prior weeks"
            )
        if not registered_bundles:
            raise PacketBuildError("registered authorizations need registered bundles")
        records = [
            registered_authorization_record(
                registered_authorizations[week],
                manifest=prior_manifests[week],
                environment=environment,
                week=week,
            )
            for week in range(last + 1)
        ]
        used = list(
            dict.fromkeys(
                (record["model_id"], record["inference_bundle_sha256"])
                for record in records
            )
        )
        by_pair = {
            (item.get("model_id"), item.get("inference_bundle_sha256")): item
            for item in registered_bundles
        }
        if len(by_pair) != len(registered_bundles) or set(by_pair) != set(used):
            raise PacketBuildError(
                "registered bundles must match the bundles of the restored runs exactly"
            )
        approvals = [
            registered_bundle_approval(
                by_pair[pair], model_id=pair[0], inference_bundle_sha256=pair[1]
            )
            for pair in used
        ]
        bundle, extra_bundles = approvals[0], approvals[1:]
    else:
        records, bundle = _records_for_cutover(
            prior_manifests,
            environment=environment,
            cutover_week=cutover,
            decision_ref=decision_ref,
            registered_bundle=registered_bundle,
            last_week=max(prior),
        )
    for week, record in enumerate(records):
        if record["prediction_run_id"] != prior[week]:
            raise PacketBuildError(f"Week {week} prior manifest is another run")
    if certifications and sorted(c.get("week") for c in certifications) != list(
        range(cutover)
    ):
        raise PacketBuildError("certifications must cover Weeks 0 through N-1")
    if missing := [name for name in PAYLOAD_REFS if name not in payload_refs]:
        raise PacketBuildError(f"payload refs missing: {', '.join(missing)}")
    body = {
        key: value
        for key, value in selection.items()
        if key not in {"manifest_sha256", *PAYLOAD_REFS}
    }
    body.update(
        schema_version=ROLLBACK_SCHEMA,
        expected_current_runs=dict(selection["replacement_runs"]),
        replacement_runs=dict(selection["expected_current_runs"]),
        expected_current_week=dict(selection["replacement_current_week"]),
        replacement_current_week=dict(selection["expected_current_week"]),
        bundle_approval=bundle,
        run_authorizations=_signed_authorizations(records),
        completed_week_certifications=[dict(c) for c in certifications],
        **{name: dict(payload_refs[name]) for name in PAYLOAD_REFS},
    )
    if extra_bundles:
        body["additional_bundle_approvals"] = extra_bundles
    return signed_payload(body)
