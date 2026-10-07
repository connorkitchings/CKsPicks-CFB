"""Fail-closed v2 atomic intended-update selection and compensating rollback."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import Phase2dError, verify_signed_payload
from cks_picks_cfb.data.team_stats import UPSERT_TEAM_STAT_SQL
from cks_picks_cfb.ops.lease import assert_active_pipeline_lease
from cks_picks_cfb.ops.prospective_records import verify_prospective_record
from cks_picks_cfb.ops.public_selection import select_week_run
from cks_picks_cfb.ops.v5_intended_update_release import (
    AUTH_COLUMNS,
    IntendedUpdateReleaseError,
    validate_intended_update_release_record,
)
from cks_picks_cfb.ops.v5_release import assert_v5_database_environment
from cks_picks_cfb.ops.v5_revocations import (
    V5RevocationError,
    assert_release_records_active,
)
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

STAT_COLUMNS = (
    "season",
    "as_of_week",
    "team",
    "role",
    "metric",
    "value",
    "n",
    "games",
    "rank",
    "cohort_size",
    "source_versions",
)
STAT_KEY = ("season", "as_of_week", "team", "role", "metric")
PROSPECTIVE_COLUMNS = (
    "season", "week", "run_id", "freeze_receipt_uri", "freeze_receipt_sha256",
    "frozen_at", "first_kickoff_utc", "decision_ref",
)


class V5BatchSelectionError(ValueError):
    """A signed release packet cannot safely select or roll back its run set."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _week_map(value: Any, label: str) -> dict[int, str]:
    if not isinstance(value, Mapping) or not value:
        raise V5BatchSelectionError(f"{label} must be a nonempty week map")
    result: dict[int, str] = {}
    for raw_week, raw_run in value.items():
        try:
            week = int(raw_week)
        except (TypeError, ValueError) as exc:
            raise V5BatchSelectionError(f"{label} has an invalid week") from exc
        if str(week) != str(raw_week) or week in result or not str(raw_run).strip():
            raise V5BatchSelectionError(f"{label} has a duplicate or empty normalized entry")
        result[week] = str(raw_run)
    return result


def _read_signed_ref(storage: Any, ref: Any, label: str) -> dict[str, Any]:
    if not isinstance(ref, Mapping) or not ref.get("uri") or not ref.get("sha256"):
        raise V5BatchSelectionError(f"{label} reference is incomplete")
    raw = storage.read_bytes(str(ref["uri"]))
    if _sha(raw) != ref["sha256"]:
        raise V5BatchSelectionError(f"{label} raw-byte checksum differs")
    value = json.loads(raw)
    try:
        verify_signed_payload(value, label=label)
    except Phase2dError as exc:
        raise V5BatchSelectionError(str(exc)) from exc
    return value


def validate_v2_packet(packet: dict[str, Any], *, environment: str, storage: Any, cur: Any = None) -> dict[str, Any]:
    if packet.get("schema_version") not in {
        "v5_intended_update_batch_selection_v2",
        "v5_intended_update_batch_rollback_v2",
    }:
        raise V5BatchSelectionError("unknown v2 release packet")
    try:
        verify_signed_payload(packet, label="V5 batch packet")
    except Phase2dError as exc:
        raise V5BatchSelectionError(str(exc)) from exc
    if packet.get("environment") != environment or packet.get("season") != 2026:
        raise V5BatchSelectionError("packet database identity differs")
    cutover = packet.get("cutover_week")
    if not isinstance(cutover, int) or cutover < 5:
        raise V5BatchSelectionError("packet cutover week is invalid")
    decision_ref = str(packet.get("decision_ref") or "").strip()
    if not decision_ref:
        raise V5BatchSelectionError("packet decision reference is missing")

    before = _week_map(packet.get("expected_current_runs"), "expected_current_runs")
    after = _week_map(packet.get("replacement_runs"), "replacement_runs")
    expected_weeks = set(range(cutover + 1))
    if set(before) != expected_weeks or set(after) != expected_weeks:
        raise V5BatchSelectionError("selection maps must cover Weeks 0 through N exactly")
    if set(before.values()) & set(after.values()):
        raise V5BatchSelectionError("replacement packet reuses a prior run")
    if packet.get("certified_completed_weeks") != list(range(cutover)):
        raise V5BatchSelectionError("certified replay weeks must be contiguous 0 through N-1")
    if set(_week_map(packet.get("protected_runs"), "protected_runs")) & expected_weeks:
        raise V5BatchSelectionError("protected run scope overlaps the replacement slate")

    current_before = packet.get("expected_current_week")
    current_after = packet.get("replacement_current_week")
    if (
        not isinstance(current_before, Mapping)
        or not isinstance(current_after, Mapping)
        or current_before.get("season") != 2026
        or current_before.get("week") != cutover
        or current_before.get("run_id") != before[cutover]
        or current_after.get("season") != 2026
        or current_after.get("week") != cutover
        or current_after.get("run_id") != after[cutover]
    ):
        raise V5BatchSelectionError("current-week before/after bindings are incomplete")

    auth = packet.get("run_authorizations")
    bundle = packet.get("bundle_approval")
    if not isinstance(bundle, Mapping) or not isinstance(auth, list):
        raise V5BatchSelectionError("packet authorization references are missing")
    bundle_fields = (
        "approval_id",
        "model_id",
        "inference_bundle_sha256",
        "first_live_season",
        "first_live_week",
        "decision_ref",
    )
    bundle_body = {key: bundle.get(key) for key in bundle_fields}
    if bundle.get("record_sha256") != _sha(canonical_json(bundle_body)):
        raise V5BatchSelectionError("bundle approval canonical hash differs")
    auth_by_week = {}
    for record in auth:
        if not isinstance(record, Mapping):
            raise V5BatchSelectionError("run authorization entry is malformed")
        week = int(record.get("week", -1))
        if week in auth_by_week or week not in expected_weeks:
            raise V5BatchSelectionError("run authorization weeks are duplicate or out of range")
        if (
            record.get("environment") != environment
            or record.get("season") != 2026
            or record.get("week") != week
            or record.get("prediction_run_id") != after[week]
            or record.get("evidence_class") != ("pending" if week == cutover else "replay")
            or record.get("model_id") != bundle_body["model_id"]
            or record.get("inference_bundle_sha256") != bundle_body["inference_bundle_sha256"]
            or record.get("decision_ref") != decision_ref
        ):
            raise V5BatchSelectionError("run authorization points to another replacement run")
        auth_body = {key: record.get(key) for key in AUTH_COLUMNS}
        if record.get("record_sha256") != _sha(canonical_json(auth_body)):
            raise V5BatchSelectionError("run authorization canonical hash differs")
        auth_by_week[week] = dict(record)
    if set(auth_by_week) != expected_weeks:
        raise V5BatchSelectionError("packet lacks an exact authorization for every selected run")
    if bundle.get("first_live_season") != 2026 or bundle.get("first_live_week") != cutover:
        raise V5BatchSelectionError("bundle approval is not bound to cutover N")

    payloads = {}
    for name in (
        "team_stats_before", "team_stats_after", "team_stats_verifier",
        "prospective_records_before", "prospective_records_after",
    ):
        payloads[name] = _read_signed_ref(storage, packet.get(name), name)
    before_payload, after_payload, verifier = (
        payloads["team_stats_before"],
        payloads["team_stats_after"],
        payloads["team_stats_verifier"],
    )
    for payload in (before_payload, after_payload):
        if (
            payload.get("schema_version") != "v5_team_stats_release_payload_v1"
            or payload.get("environment") != environment
            or payload.get("season") != 2026
            or not isinstance(payload.get("rows"), list)
        ):
            raise V5BatchSelectionError("team-stats payload schema or scope differs")
    if before_payload.get("scope") != after_payload.get("scope"):
        raise V5BatchSelectionError("team-stats before/after scope differs")
    _validate_stat_rows(before_payload["rows"], "before")
    _validate_stat_rows(after_payload["rows"], "after")
    before_by_key = {_stat_key(row): row for row in before_payload["rows"]}
    after_by_key = {_stat_key(row): row for row in after_payload["rows"]}
    if before_by_key.keys() != after_by_key.keys():
        raise V5BatchSelectionError("team-stats payloads do not have identical complete keys")
    if any(
        before_by_key[key].get("source_versions") != after_by_key[key].get("source_versions")
        for key in before_by_key
    ):
        raise V5BatchSelectionError("team-stats provenance changed across the packet")
    prospective_before = payloads["prospective_records_before"]
    prospective_after = payloads["prospective_records_after"]
    for payload in (prospective_before, prospective_after):
        if (
            payload.get("schema_version") != "v5_prospective_records_release_payload_v1"
            or payload.get("environment") != environment
            or payload.get("season") != 2026
            or not isinstance(payload.get("rows"), list)
        ):
            raise V5BatchSelectionError("prospective-record payload schema or scope differs")
        _validate_prospective_rows(payload["rows"])
    prospective_before_by_key = {_prospective_key(row): row for row in prospective_before["rows"]}
    prospective_after_by_key = {_prospective_key(row): row for row in prospective_after["rows"]}
    if prospective_before_by_key != prospective_after_by_key:
        raise V5BatchSelectionError("selection and rollback packets must preserve prospective records exactly")
    if not set(range(5, cutover)).issubset({row["week"] for row in prospective_before["rows"]}):
        raise V5BatchSelectionError("completed prospective Week 5 onward evidence is missing")
    for row in prospective_before["rows"]:
        if "/legacy-attestation-v1-" in row["freeze_receipt_uri"] and cur is None:
            raise V5BatchSelectionError("legacy attestation requires live source verification")
        verify_prospective_record(row, cur=cur, storage=storage, environment=environment)
    if (
        verifier.get("state") != "verified"
        or verifier.get("before_sha256") != packet["team_stats_before"]["sha256"]
        or verifier.get("after_sha256") != packet["team_stats_after"]["sha256"]
        or verifier.get("decision_ref") != decision_ref
    ):
        raise V5BatchSelectionError("team-stats verifier is not bound to both payloads")
    return {
        "before": before,
        "after": after,
        "cutover_week": cutover,
        "bundle": dict(bundle),
        "authorizations": auth_by_week,
        "payloads": payloads,
        "decision_ref": decision_ref,
        "rollback": packet["schema_version"].endswith("rollback_v2"),
    }


def _stat_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in STAT_KEY)


def _prospective_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return int(row["season"]), int(row["week"])


def _validate_prospective_rows(rows: list[Any]) -> None:
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(PROSPECTIVE_COLUMNS) - set(row):
            raise V5BatchSelectionError("prospective-record row lacks required columns")
        key = _prospective_key(row)
        if key in seen or key[0] != 2026 or key[1] < 5:
            raise V5BatchSelectionError("prospective-record payload has duplicate or out-of-scope keys")
        seen.add(key)


def _validate_stat_rows(rows: list[Any], label: str) -> None:
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(STAT_COLUMNS) - set(row):
            raise V5BatchSelectionError(f"team-stats {label} row lacks required columns")
        key = _stat_key(row)
        if key in seen:
            raise V5BatchSelectionError(f"team-stats {label} payload has duplicate keys")
        seen.add(key)


def _database_stats(cur: Any, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    scope = payload.get("scope")
    if not isinstance(scope, list) or not scope:
        raise V5BatchSelectionError("team-stats snapshot scope is incomplete")
    clauses = []
    params = []
    for item in scope:
        if not isinstance(item, Mapping):
            raise V5BatchSelectionError("team-stats scope row is malformed")
        clauses.append("(season = %s AND as_of_week = %s)")
        params.extend((item["season"], item["as_of_week"]))
    cur.execute(
        "SELECT season, as_of_week, team, role, metric, value, n, games, rank, "
        "cohort_size, source_versions FROM team_season_stats WHERE "
        + " OR ".join(clauses)
        + " ORDER BY season, as_of_week, team, role, metric",
        tuple(params),
    )
    rows = cur.fetchall()
    return [dict(zip(STAT_COLUMNS, row, strict=True)) for row in rows]


def _assert_payload_rows(cur: Any, payload: Mapping[str, Any], label: str) -> None:
    actual = _database_stats(cur, payload)
    expected = sorted(payload["rows"], key=_stat_key)
    if actual != expected:
        raise V5BatchSelectionError(f"database team-stats {label} rows differ from retained payload")


def _assert_prospective_rows(cur: Any, payload: Mapping[str, Any], label: str) -> None:
    cur.execute(
        "SELECT " + ", ".join(PROSPECTIVE_COLUMNS) +
        " FROM public.prospective_week_records WHERE season = 2026 ORDER BY week"
    )
    actual = []
    for db_row in cur.fetchall():
        record = dict(zip(PROSPECTIVE_COLUMNS, db_row, strict=True))
        for column in ("frozen_at", "first_kickoff_utc"):
            if hasattr(record[column], "isoformat"):
                record[column] = record[column].isoformat()
        actual.append(record)
    expected = sorted(payload["rows"], key=_prospective_key)
    if actual != expected:
        raise V5BatchSelectionError(f"database prospective {label} rows differ from retained payload")


def _verify_registered_authorizations(
    cur: Any, plan: Mapping[str, Any], storage: Any
) -> None:
    bundle = plan["bundle"]
    cur.execute(
        "SELECT approval_id, model_id, inference_bundle_sha256, first_live_season, "
        "first_live_week, decision_ref FROM v5_model_bundle_approvals WHERE approval_id = %s",
        (bundle["approval_id"],),
    )
    expected_bundle = tuple(bundle[key] for key in (
        "approval_id", "model_id", "inference_bundle_sha256", "first_live_season",
        "first_live_week", "decision_ref",
    ))
    if cur.fetchone() != expected_bundle:
        raise V5BatchSelectionError("registered bundle approval differs from packet")
    from cks_picks_cfb.artifacts import prediction_run_manifest_path

    records = [("bundle_approval", str(bundle["approval_id"]))]
    for week in sorted(plan["authorizations"]):
        record = plan["authorizations"][week]
        cur.execute(
            "SELECT " + ", ".join(AUTH_COLUMNS) +
            " FROM v5_intended_update_release_authorizations WHERE authorization_id = %s",
            (record["authorization_id"],),
        )
        if cur.fetchone() != tuple(record[key] for key in AUTH_COLUMNS):
            raise V5BatchSelectionError(f"registered Week {week} authorization differs from packet")
        manifest = json.loads(
            storage.read_bytes(
                prediction_run_manifest_path(2026, week, record["prediction_run_id"])
            )
        )
        try:
            validate_intended_update_release_record(
                record,
                manifest=manifest,
                storage=storage,
                season=2026,
                week=week,
                environment=record["environment"],
            )
        except IntendedUpdateReleaseError as exc:
            raise V5BatchSelectionError(str(exc)) from exc
        records.append(("intended_update_authorization", str(record["authorization_id"])))
    try:
        assert_release_records_active(cur, records)
    except V5RevocationError as exc:
        raise V5BatchSelectionError(str(exc)) from exc


def _verify_week_evidence(cur: Any, packet: Mapping[str, Any], plan: Mapping[str, Any], storage: Any) -> None:
    certifications = packet.get("completed_week_certifications")
    if not isinstance(certifications, list):
        raise V5BatchSelectionError("completed-week certification refs are missing")
    by_week = {}
    for ref in certifications:
        if not isinstance(ref, Mapping) or not isinstance(ref.get("week"), int):
            raise V5BatchSelectionError("completed-week certification ref is malformed")
        week = ref["week"]
        if week in by_week:
            raise V5BatchSelectionError("duplicate completed-week certification ref")
        receipt = _read_signed_ref(storage, ref, f"Week {week} certification")
        if (
            receipt.get("state") != "verified"
            or receipt.get("season") != 2026
            or receipt.get("week") != week
            or receipt.get("run_id") != plan["after"][week]
            or receipt.get("finals_complete") is not True
        ):
            raise V5BatchSelectionError(f"Week {week} certification does not bind complete finals")
        stabilized = receipt.get("finals_stabilized_at")
        try:
            stabilized_at = datetime.fromisoformat(str(stabilized).replace("Z", "+00:00"))
        except ValueError as exc:
            raise V5BatchSelectionError(f"Week {week} stabilization time is invalid") from exc
        if stabilized_at.tzinfo is None:
            raise V5BatchSelectionError(f"Week {week} stabilization time lacks timezone")
        by_week[week] = stabilized_at
    if set(by_week) != set(range(plan["cutover_week"])):
        raise V5BatchSelectionError("certification refs do not cover all completed replay weeks")
    cur.execute("SELECT NOW()")
    db_now = cur.fetchone()[0]

    for week in range(plan["cutover_week"]):
        if db_now < by_week[week] + timedelta(hours=24):
            raise V5BatchSelectionError(f"Week {week} has not stabilized for 24 hours")
        cur.execute(
            "SELECT pr.state, pr.evidence_class, pr.expected_games, pr.predicted_games, "
            "COUNT(p.game_id), COUNT(gr.game_id), "
            "COUNT(*) FILTER (WHERE g.season <> 2026 OR g.week <> %s), "
            "COUNT(DISTINCT p.game_id) "
            "FROM prediction_runs pr LEFT JOIN predictions p ON p.run_id = pr.run_id "
            "LEFT JOIN games g ON g.game_id = p.game_id "
            "LEFT JOIN game_results gr ON gr.game_id = p.game_id "
            "WHERE pr.run_id = %s GROUP BY pr.run_id",
            (week, plan["after"][week]),
        )
        row = cur.fetchone()
        if (
            row is None
            or row[0] != "scored"
            or row[1] != "replay"
            or row[2] != row[3]
            or row[3] != row[4]
            or row[4] != row[5]
            or row[6] != 0
            or row[7] != row[2]
        ):
            raise V5BatchSelectionError(f"Week {week} is not a complete scored replay in Neon")

    pending = plan["after"][plan["cutover_week"]]
    cur.execute(
        "SELECT pr.state, pr.evidence_class, pr.expected_games, pr.predicted_games, "
        "pr.lined_games, COUNT(p.game_id), MIN(g.start_date), NOW(), "
        "COUNT(*) FILTER (WHERE g.season <> 2026 OR g.week <> %s), "
        "COUNT(DISTINCT p.game_id) "
        "FROM prediction_runs pr LEFT JOIN predictions p ON p.run_id = pr.run_id "
        "LEFT JOIN games g ON g.game_id = p.game_id WHERE pr.run_id = %s GROUP BY pr.run_id",
        (plan["cutover_week"], pending),
    )
    row = cur.fetchone()
    if (
        row is None
        or row[0] != "published"
        or row[1] != "pending"
        or row[2] != row[3]
        or row[3] != row[4]
        or row[4] != row[5]
        or row[6] is None
        or row[7] >= row[6] - timedelta(hours=1)
        or row[8] != 0
        or row[9] != row[2]
    ):
        raise V5BatchSelectionError("cutover N run is not complete and safely pre-kickoff")


def apply_v2_packet(cur: Any, packet: dict[str, Any], *, environment: str, storage: Any) -> dict[str, Any]:
    """Apply signed select/rollback state in the caller's sole transaction."""
    plan = validate_v2_packet(packet, environment=environment, storage=storage, cur=cur)
    assert_v5_database_environment(cur, environment)
    assert_active_pipeline_lease(cur)
    for table in (
        "site_week_selections",
        "current_week",
        "public.prospective_week_records",
        "team_season_stats",
        "system_stats",
    ):
        cur.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
    weeks = sorted(plan["before"])
    for week in weeks:
        cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (2026, week))
    _verify_registered_authorizations(cur, plan, storage)
    _verify_week_evidence(cur, packet, plan, storage)
    for row in plan["payloads"]["prospective_records_before"]["rows"]:
        verify_prospective_record(row, cur=cur, storage=storage, environment=environment)

    cur.execute(
        "SELECT week, run_id FROM site_week_selections WHERE season = 2026 "
        "AND week = ANY(%s) ORDER BY week FOR UPDATE",
        (weeks,),
    )
    actual_runs = {int(week): str(run_id) for week, run_id in cur.fetchall()}
    protected = _week_map(packet.get("protected_runs"), "protected_runs")
    cur.execute(
        "SELECT week, run_id FROM site_week_selections WHERE season = 2026 "
        "AND week = ANY(%s) ORDER BY week FOR UPDATE",
        (sorted(protected),),
    )
    if {int(week): str(run_id) for week, run_id in cur.fetchall()} != protected:
        raise V5BatchSelectionError("protected public selections changed")
    current_expected = packet["expected_current_week"]
    current_replacement = packet["replacement_current_week"]
    cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1 FOR UPDATE")
    current = cur.fetchone()
    if actual_runs == plan["after"] and current == (
        current_replacement["season"],
        current_replacement["week"],
        current_replacement["run_id"],
    ):
        _assert_payload_rows(cur, plan["payloads"]["team_stats_after"], "idempotent retry")
        _assert_prospective_rows(cur, plan["payloads"]["prospective_records_after"], "idempotent retry")
        return {
            "state": "already_applied",
            "environment": environment,
            "season": 2026,
            "cutover_week": plan["cutover_week"],
            "selected_runs": plan["after"],
        }
    if actual_runs != plan["before"]:
        raise V5BatchSelectionError("live selected runs differ from exact packet prior state")
    if current != (
        current_expected["season"], current_expected["week"], current_expected["run_id"]
    ):
        raise V5BatchSelectionError("current-week pointer differs from packet before-state")

    before_payload = plan["payloads"]["team_stats_before"]
    after_payload = plan["payloads"]["team_stats_after"]
    _assert_payload_rows(cur, before_payload, "before")
    _assert_prospective_rows(cur, plan["payloads"]["prospective_records_before"], "before")

    target_runs = plan["after"]
    target_stats = after_payload
    target_current = current_replacement
    if plan["rollback"] and current != (
        current_expected["season"], current_expected["week"], current_expected["run_id"]
    ):
        raise V5BatchSelectionError("rollback current-week pointer is stale")
    if plan["rollback"]:
        cur.execute(
            "SELECT MIN(g.start_date) FROM predictions p JOIN games g ON g.game_id = p.game_id "
            "WHERE p.run_id = %s",
            (plan["after"][plan["cutover_week"]],),
        )
        kickoff = cur.fetchone()[0]
        cur.execute("SELECT NOW()")
        if kickoff is None or cur.fetchone()[0] >= kickoff:
            raise V5BatchSelectionError("rollback is unsafe after cutover week has started")

    prior = {}
    for week in weeks:
        prior[week] = select_week_run(
            cur,
            season=2026,
            week=week,
            run_id=target_runs[week],
            reason=("V5 intended-update rollback: " if plan["rollback"] else "V5 intended-update batch: ")
            + plan["decision_ref"],
            environment=environment,
        )
    for row in sorted(target_stats["rows"], key=_stat_key):
        record = dict(row)
        record["source_versions"] = json.dumps(record["source_versions"], sort_keys=True)
        cur.execute(UPSERT_TEAM_STAT_SQL, record)
    cur.execute(
        "UPDATE current_week SET season = %s, week = %s, active_run_id = %s, updated_at = NOW() WHERE id = 1",
        (target_current["season"], target_current["week"], target_current["run_id"]),
    )
    from scripts.pipeline.score_to_db import RECOMPUTE_STATS_SQL

    cur.execute(RECOMPUTE_STATS_SQL, {"season": 2026})
    cur.execute(
        "SELECT week, run_id FROM site_week_selections WHERE season = 2026 "
        "AND week = ANY(%s) ORDER BY week",
        (weeks,),
    )
    readback_runs = {int(week): str(run_id) for week, run_id in cur.fetchall()}
    if readback_runs != target_runs:
        raise V5BatchSelectionError("selection readback differs after batch mutation")
    cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1")
    if cur.fetchone() != (target_current["season"], target_current["week"], target_current["run_id"]):
        raise V5BatchSelectionError("current-week readback differs after batch mutation")
    _assert_payload_rows(cur, target_stats, "after")
    _assert_prospective_rows(cur, plan["payloads"]["prospective_records_after"], "after")
    return {
        "state": "rolled_back" if plan["rollback"] else "selected",
        "environment": environment,
        "season": 2026,
        "cutover_week": plan["cutover_week"],
        "prior_runs": prior,
        "selected_runs": target_runs,
    }


def preflight_v2_packet(cur: Any, packet: dict[str, Any], *, environment: str, storage: Any) -> dict[str, Any]:
    """Read-only preflight; apply repeats every comparison while holding locks."""
    plan = validate_v2_packet(packet, environment=environment, storage=storage, cur=cur)
    assert_v5_database_environment(cur, environment)
    _verify_registered_authorizations(cur, plan, storage)
    _verify_week_evidence(cur, packet, plan, storage)
    weeks = sorted(plan["before"])
    cur.execute(
        "SELECT week, run_id FROM site_week_selections WHERE season = 2026 "
        "AND week = ANY(%s) ORDER BY week",
        (weeks,),
    )
    current_runs = {int(week): str(run_id) for week, run_id in cur.fetchall()}
    protected = _week_map(packet.get("protected_runs"), "protected_runs")
    cur.execute(
        "SELECT week, run_id FROM site_week_selections WHERE season = 2026 "
        "AND week = ANY(%s) ORDER BY week",
        (sorted(protected),),
    )
    protected_now = {int(week): str(run_id) for week, run_id in cur.fetchall()}
    expected = packet["expected_current_week"]
    cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1")
    current_pointer = cur.fetchone()
    if (
        current_runs == plan["after"]
        and protected_now == protected
        and current_pointer == (
            packet["replacement_current_week"]["season"],
            packet["replacement_current_week"]["week"],
            packet["replacement_current_week"]["run_id"],
        )
    ):
        _assert_payload_rows(cur, plan["payloads"]["team_stats_after"], "idempotent retry")
        _assert_prospective_rows(cur, plan["payloads"]["prospective_records_after"], "idempotent retry")
        return {
            "state": "already_applied",
            "environment": environment,
            "season": 2026,
            "cutover_week": plan["cutover_week"],
            "current_runs": plan["after"],
            "candidate_runs": plan["after"],
            "rollback": plan["rollback"],
        }
    if current_runs != plan["before"]:
        raise V5BatchSelectionError("live selected runs differ from exact packet prior state")
    if protected_now != protected:
        raise V5BatchSelectionError("protected public selections changed")
    if current_pointer != (expected["season"], expected["week"], expected["run_id"]):
        raise V5BatchSelectionError("current-week pointer differs from packet before-state")
    _assert_payload_rows(cur, plan["payloads"]["team_stats_before"], "before")
    _assert_prospective_rows(cur, plan["payloads"]["prospective_records_before"], "before")
    return {
        "state": "preflight",
        "environment": environment,
        "season": 2026,
        "cutover_week": plan["cutover_week"],
        "current_runs": plan["before"],
        "candidate_runs": plan["after"],
        "rollback": plan["rollback"],
    }
