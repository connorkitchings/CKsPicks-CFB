"""Immutable, release-qualified serving with caller-owned transactions.

Every function leaves commit/rollback to its caller. Staging never changes the active
release. Activation and rollback read back all projections before returning.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from cks_picks_cfb.ops.v5_release import assert_v5_database_environment

PROJECTION_KEYS = {
    "games": ("game_id",),
    "game_venues": ("game_id",),
    "game_results": ("game_id",),
    "predictions": ("run_id", "game_id"),
    "prediction_grades": ("run_id", "game_id", "target"),
    "market_quotes": ("quote_id",),
    "market_snapshots": ("snapshot_id",),
    "market_snapshot_quotes": ("snapshot_id", "quote_id", "target"),
    "prediction_market_selections": ("run_id", "game_id", "target"),
    "system_stats": ("season",),
    "v5_rating_snapshots": ("snapshot_id",),
    "team_season_stats": ("season", "as_of_week", "team", "role", "metric"),
    "matchup_data_publications": ("publication_id",),
    "team_game_measurements": (
        "season",
        "game_id",
        "team",
        "unit_role",
        "measurement_id",
    ),
    "team_possession_stats": ("season", "as_of_week", "team", "role", "metric"),
    "team_possession_adjusted": (
        "season",
        "as_of_week",
        "team",
        "role",
        "measurement_id",
    ),
    "team_rating_components": ("component_id",),
    "site_week_selections": ("season", "week"),
}
IDENTITY_FIELDS = (
    "season",
    "active_week",
    "model_manifest_sha256",
    "revision_manifest_sha256",
    "workflow_version",
    "grading_policy_sha256",
    "code_sha",
    "config_sha",
)
RELEASE_COLUMNS = (
    "release_id",
    "environment",
    *IDENTITY_FIELDS,
    "run_manifest_uri",
    "run_manifest_sha256",
    "verification_uri",
    "verification_sha256",
    "projection_checks",
)


class SeasonReleaseError(ValueError):
    """A release does not satisfy its immutable scope, approval or before-state."""


def _json(raw: bytes, label: str) -> dict:
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise SeasonReleaseError(f"invalid {label} JSON") from error
    if not isinstance(doc, dict):
        raise SeasonReleaseError(f"{label} must be an object")
    return doc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_candidate(manifest: Mapping, verification: Mapping) -> None:
    if manifest.get("schema_version") != "season_run_v1":
        raise SeasonReleaseError("unknown season run schema")
    if verification.get("state") != "passed":
        raise SeasonReleaseError("candidate verification did not pass")
    identity = verification.get("identity", {})
    for field in IDENTITY_FIELDS:
        if field not in manifest or identity.get(field) != manifest[field]:
            raise SeasonReleaseError(f"verification identity mismatch: {field}")
    for field in (
        "model_manifest_sha256",
        "revision_manifest_sha256",
        "grading_policy_sha256",
        "config_sha",
    ):
        digest = manifest[field]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise SeasonReleaseError(f"invalid checksum: {field}")
    if verification.get("output_refs") != manifest.get(
        "output_refs"
    ) or not manifest.get("output_refs"):
        raise SeasonReleaseError("verification output bindings differ")
    checks = verification.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise SeasonReleaseError("candidate checks missing or failed")
    if (
        not isinstance(manifest.get("release_id"), str)
        or not manifest["release_id"].strip()
    ):
        raise SeasonReleaseError("release identity missing")


def _normal(value: Any, column: str = "") -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise SeasonReleaseError("naive timestamp in release projection")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, str) and (
        column.endswith(("_at", "_utc")) or column in {"start_date", "as_of_cutoff"}
    ):
        return _normal(datetime.fromisoformat(value.replace("Z", "+00:00")))
    if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
        number = Decimal(str(value))
        if not number.is_finite():
            raise SeasonReleaseError("nonfinite number in release projection")
        return format(number.normalize(), "f")
    if isinstance(value, str) and "profit_units" in column:
        return _normal(Decimal(value))
    if isinstance(value, Mapping):
        return {k: _normal(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normal(v) for v in value]
    return value


def projection_check(rows: list[dict]) -> dict:
    """Stable full-row content identity; timestamps are normalized, not dropped."""
    encoded = sorted(
        json.dumps(
            {k: v for k, v in _normal(row).items() if k != "environment"},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        for row in rows
    )
    return {"rows": len(rows), "sha256": _sha(("\n".join(encoded) + "\n").encode())}


def _columns(cur, base: str) -> dict[str, str]:
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
        ("season_release_" + base,),
    )
    columns = dict(cur.fetchall())
    columns.pop("release_id", None)
    if not columns:
        raise SeasonReleaseError(f"projection schema missing: {base}")
    return columns


def _readback(cur, release_id: str, checks: Mapping) -> dict:
    if set(checks) != set(PROJECTION_KEYS):
        raise SeasonReleaseError("all serving projection checks are required")
    actual = {}
    for base in PROJECTION_KEYS:
        columns = _columns(cur, base)
        cur.execute(
            sql.SQL("SELECT {} FROM {} WHERE release_id = %s").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.Identifier("season_release_" + base),
            ),
            (release_id,),
        )
        rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
        actual[base] = projection_check(rows)
    if actual != checks:
        raise SeasonReleaseError("entire-view projection readback differs")
    return actual


def _lock(cur, environment: str, season: int) -> None:
    if environment not in {"preview", "production"}:
        raise SeasonReleaseError("explicit environment is required")
    cur.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"season-release:{environment}:{season}",),
    )


def _release(cur, release_id: str) -> dict:
    columns = (*RELEASE_COLUMNS, "status")
    cur.execute(
        sql.SQL(
            "SELECT {} FROM season_releases WHERE release_id = %s FOR UPDATE"
        ).format(sql.SQL(", ").join(map(sql.Identifier, columns))),
        (release_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise SeasonReleaseError("release does not exist")
    return dict(zip(columns, row, strict=True))


def _active(cur, environment: str, season: int) -> str | None:
    cur.execute(
        "SELECT release_id FROM season_releases WHERE environment = %s AND season = %s AND status = 'active' FOR UPDATE",
        (environment, season),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise SeasonReleaseError("multiple active season releases")
    return str(rows[0][0]) if rows else None


def _policy(cur, release: Mapping) -> str:
    cur.execute(
        "SELECT model_manifest_sha256, workflow_version, grading_policy_sha256, enabled, decision_ref FROM season_release_policies WHERE environment = %s AND season = %s FOR SHARE",
        (release["environment"], release["season"]),
    )
    policy = cur.fetchone()
    expected = tuple(
        release[k]
        for k in ("model_manifest_sha256", "workflow_version", "grading_policy_sha256")
    )
    if not policy or tuple(policy[:3]) != expected or policy[3] is not True:
        raise SeasonReleaseError(
            "owner-installed automatic release policy does not authorize candidate"
        )
    return str(policy[4])


def _check_projection_scope(
    projections: Mapping, season: int, active_week: int
) -> None:
    if set(projections) != set(PROJECTION_KEYS):
        raise SeasonReleaseError("complete fixed serving projections are required")
    for base, keys in PROJECTION_KEYS.items():
        rows = projections[base]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise SeasonReleaseError(f"invalid projection rows: {base}")
        seen = set()
        for row in rows:
            key = tuple(row[k] for k in keys)
            if key in seen:
                raise SeasonReleaseError(f"duplicate projection key: {base}")
            seen.add(key)
            if "release_id" in row or ("season" in row and row["season"] != season):
                raise SeasonReleaseError(f"foreign projection scope: {base}")
    selections = projections["site_week_selections"]
    if {row["week"] for row in selections} != set(range(active_week + 1)):
        raise SeasonReleaseError(
            "release must select the complete season through active week"
        )
    games = {row["game_id"]: row for row in projections["games"]}
    results = {row["game_id"] for row in projections["game_results"]}
    if not games or results - set(games):
        raise SeasonReleaseError("release schedule/finals mismatch")
    selected = {row["week"]: row["run_id"] for row in selections}
    for row in projections["predictions"]:
        game = games.get(row["game_id"])
        if not game or selected.get(game["week"]) != row["run_id"]:
            raise SeasonReleaseError("prediction is outside the selected schedule")
    predicted = {row["game_id"] for row in projections["predictions"]}
    if predicted != set(games):
        raise SeasonReleaseError("full release schedule must have predictions")
    prior = {gid for gid, row in games.items() if row["week"] < active_week}
    if prior - results:
        raise SeasonReleaseError("prior-week finals are incomplete")
    for row in projections["game_results"]:
        if row.get("home_points") is None or row.get("away_points") is None:
            raise SeasonReleaseError("final score missing")
    for row in projections["prediction_grades"]:
        game = games.get(row["game_id"])
        if not game or selected.get(game["week"]) != row["run_id"]:
            raise SeasonReleaseError("grade is outside the selected run")
        if row["game_id"] not in results or row["game_id"] not in predicted:
            raise SeasonReleaseError("grade lacks prediction or final")
    if active_week > 0 and any(
        not projections[name]
        for name in (
            "team_season_stats",
            "team_game_measurements",
            "team_possession_stats",
            "team_possession_adjusted",
            "team_rating_components",
            "matchup_data_publications",
        )
    ):
        raise SeasonReleaseError("complete football serving projections are required")
    if not projections["v5_rating_snapshots"] or not projections["system_stats"]:
        raise SeasonReleaseError("ratings and performance projections are required")


def _register_runs(cur, records: list[dict], season: int) -> None:
    """Reuse the existing immutable run registry; never alter an existing row."""
    if not isinstance(records, list):
        raise SeasonReleaseError("prediction run registry payload must be a list")
    if not records:
        return
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'prediction_runs' ORDER BY ordinal_position"
    )
    columns = dict(cur.fetchall())
    stable = set(columns) - {
        "state",
        "published_at",
        "frozen_at",
        "scored_at",
        "created_at",
    }
    for record in records:
        if set(record) != set(columns) or record["season"] != season:
            raise SeasonReleaseError("prediction run registry scope/columns differ")
        if (
            record["state"] not in {"published", "scored"}
            or record["frozen_at"] is not None
        ):
            raise SeasonReleaseError("reconstruction cannot manufacture a freeze")
        cur.execute(
            sql.SQL(
                "SELECT {} FROM prediction_runs WHERE run_id = %s FOR UPDATE"
            ).format(sql.SQL(", ").join(map(sql.Identifier, columns))),
            (record["run_id"],),
        )
        found = cur.fetchone()
        if found:
            existing = dict(zip(columns, found, strict=True))
            if _normal({key: existing[key] for key in stable}) != _normal(
                {key: record[key] for key in stable}
            ):
                raise SeasonReleaseError("immutable prediction run collision")
            continue
        cur.execute(
            sql.SQL("INSERT INTO prediction_runs ({}) VALUES ({})").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            ),
            tuple(
                Jsonb(record[key]) if columns[key] == "jsonb" else record[key]
                for key in columns
            ),
        )


def stage_release(
    conn,
    *,
    manifest_raw: bytes,
    run_manifest_uri: str,
    verification_raw: bytes,
    projection_raw: bytes,
    environment: str,
) -> str:
    """Stage fully verified rows without altering public selection; never commits."""
    if getattr(conn, "autocommit", False):
        raise SeasonReleaseError(
            "release operations require a caller-owned transaction"
        )
    manifest = _json(manifest_raw, "manifest")
    verification = _json(verification_raw, "verification")
    if _sha(verification_raw) != manifest.get("verification_sha256"):
        raise SeasonReleaseError("verification bytes changed")
    validate_candidate(manifest, verification)
    ref = manifest["output_refs"].get("serving_projections", {})
    if _sha(projection_raw) != ref.get("sha256"):
        raise SeasonReleaseError("serving projection bytes are not verified")
    projections = _json(projection_raw, "projections")
    registry = projections.pop("prediction_runs", [])
    _check_projection_scope(projections, manifest["season"], manifest["active_week"])
    if any(
        row.get("environment", environment) != environment
        for rows in projections.values()
        for row in rows
    ):
        raise SeasonReleaseError("projection belongs to another environment")
    checks = {base: projection_check(rows) for base, rows in projections.items()}
    release_id = f"{environment}-{manifest['release_id']}"
    record = {
        "release_id": release_id,
        "environment": environment,
        **{k: manifest[k] for k in IDENTITY_FIELDS},
        "run_manifest_uri": run_manifest_uri,
        "run_manifest_sha256": _sha(manifest_raw),
        "verification_uri": manifest["verification_uri"],
        "verification_sha256": _sha(verification_raw),
        "projection_checks": checks,
    }
    with conn.cursor() as cur:
        assert_v5_database_environment(cur, environment)
        _lock(cur, environment, manifest["season"])
        _register_runs(cur, registry, manifest["season"])
        cur.execute(
            "SELECT release_id FROM season_releases WHERE release_id = %s",
            (release_id,),
        )
        if cur.fetchone():
            existing = _release(cur, release_id)
            if any(existing[k] != record[k] for k in RELEASE_COLUMNS):
                raise SeasonReleaseError("immutable release collision")
            _readback(cur, release_id, checks)
            return release_id
        cur.execute(
            sql.SQL("INSERT INTO season_releases ({}) VALUES ({})").format(
                sql.SQL(", ").join(map(sql.Identifier, RELEASE_COLUMNS)),
                sql.SQL(", ").join(sql.Placeholder() for _ in RELEASE_COLUMNS),
            ),
            tuple(
                Jsonb(record[k]) if k == "projection_checks" else record[k]
                for k in RELEASE_COLUMNS
            ),
        )
        for base, rows in projections.items():
            columns = _columns(cur, base)
            for row in rows:
                if set(row) != set(columns):
                    raise SeasonReleaseError(f"projection columns differ: {base}")
            statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier("season_release_" + base),
                sql.SQL(", ").join(map(sql.Identifier, ("release_id", *columns))),
                sql.SQL(", ").join(sql.Placeholder() for _ in range(len(columns) + 1)),
            )
            cur.executemany(
                statement,
                [
                    (
                        release_id,
                        *(
                            Jsonb(row[k]) if columns[k] == "jsonb" else row[k]
                            for k in columns
                        ),
                    )
                    for row in rows
                ],
            )
        _readback(cur, release_id, checks)
    return release_id


def _preview_proof(conn, candidate: Mapping) -> None:
    if conn is None or not conn.read_only:
        raise SeasonReleaseError(
            "Production requires independently read-only Preview rehearsal"
        )
    with conn.cursor() as cur:
        assert_v5_database_environment(cur, "preview")
        cur.execute(
            "SELECT release_id FROM season_releases WHERE environment = 'preview' AND season = %s AND model_manifest_sha256 = %s AND revision_manifest_sha256 = %s AND workflow_version = %s AND grading_policy_sha256 = %s AND code_sha = %s AND config_sha = %s AND active_week = %s",
            tuple(
                candidate[k]
                for k in (
                    "season",
                    "model_manifest_sha256",
                    "revision_manifest_sha256",
                    "workflow_version",
                    "grading_policy_sha256",
                    "code_sha",
                    "config_sha",
                    "active_week",
                )
            ),
        )
        ids = [row[0] for row in cur.fetchall()]
        for release_id in ids:
            # This read-only transaction deliberately does not acquire row locks.
            cur.execute(
                "SELECT projection_checks FROM season_releases WHERE release_id = %s",
                (release_id,),
            )
            checks = cur.fetchone()[0]
            if checks != candidate["projection_checks"]:
                continue
            cur.execute(
                "SELECT readback_sha256 FROM season_release_history WHERE release_id = %s AND environment = 'preview' AND action = 'activate'",
                (release_id,),
            )
            expected = _sha(
                json.dumps(checks, sort_keys=True, separators=(",", ":")).encode()
            )
            if any(row[0] == expected for row in cur.fetchall()):
                _readback(cur, release_id, checks)
                return
    raise SeasonReleaseError("matching verified Preview activation is absent")


def _activate(
    conn,
    *,
    environment: str,
    season: int,
    release_id: str,
    expected_previous_release_id: str | None,
    rollback: bool,
    decision_ref: str | None = None,
    preview_conn=None,
) -> dict:
    if getattr(conn, "autocommit", False):
        raise SeasonReleaseError(
            "release operations require a caller-owned transaction"
        )
    with conn.cursor() as cur:
        if not rollback:
            assert_v5_database_environment(cur, environment)
        _lock(cur, environment, season)
        previous = _active(cur, environment, season)
        if previous != expected_previous_release_id:
            raise SeasonReleaseError("active release changed since review")
        candidate = _release(cur, release_id)
        if (candidate["environment"], candidate["season"]) != (environment, season):
            raise SeasonReleaseError(
                "candidate belongs to another environment or season"
            )
        allowed = {"superseded", "rolled_back"} if rollback else {"staged"}
        if candidate["status"] not in allowed:
            raise SeasonReleaseError("candidate has invalid activation status")
        if rollback and previous is None:
            raise SeasonReleaseError("rollback requires an active release")
        if not rollback:
            decision_ref = _policy(cur, candidate)
            if environment == "production":
                _preview_proof(preview_conn, candidate)
        checks = _readback(cur, release_id, candidate["projection_checks"])
        if previous:
            cur.execute(
                "UPDATE season_releases SET status = %s WHERE release_id = %s",
                ("rolled_back" if rollback else "superseded", previous),
            )
        cur.execute(
            "UPDATE season_releases SET status = 'active', activated_at = NOW() WHERE release_id = %s",
            (release_id,),
        )
        if _active(cur, environment, season) != release_id:
            raise SeasonReleaseError("activation pointer readback differs")
        _readback(cur, release_id, checks)
        digest = _sha(
            json.dumps(checks, sort_keys=True, separators=(",", ":")).encode()
        )
        action = "rollback" if rollback else "activate"
        cur.execute(
            "INSERT INTO season_release_history (environment, season, prior_release_id, release_id, action, decision_ref, readback_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (environment, season, previous, release_id, action, decision_ref, digest),
        )
        return {
            "environment": environment,
            "season": season,
            "release_id": release_id,
            "prior_release_id": previous,
            "action": action,
            "readback_sha256": digest,
        }


def activate_release(
    conn,
    *,
    environment: str,
    season: int,
    release_id: str,
    expected_previous_release_id: str | None,
    preview_conn=None,
) -> dict:
    return _activate(
        conn,
        environment=environment,
        season=season,
        release_id=release_id,
        expected_previous_release_id=expected_previous_release_id,
        rollback=False,
        preview_conn=preview_conn,
    )


def rollback_release(
    conn,
    *,
    environment: str,
    season: int,
    release_id: str,
    expected_previous_release_id: str,
    owner_authorized: bool,
    decision_ref: str,
) -> dict:
    if owner_authorized is not True or not decision_ref.strip():
        raise SeasonReleaseError(
            "rollback requires explicit owner approval and decision"
        )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT session_user, current_user, has_table_privilege(current_user, 'season_release_policies', 'UPDATE')"
        )
        login, role, owner = cur.fetchone()
        if login != role or not owner or str(role).endswith(("_pipeline", "_web")):
            raise SeasonReleaseError("rollback requires owner/migrator login")
    return _activate(
        conn,
        environment=environment,
        season=season,
        release_id=release_id,
        expected_previous_release_id=expected_previous_release_id,
        rollback=True,
        decision_ref=decision_ref,
    )
