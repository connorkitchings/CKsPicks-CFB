"""Immutable, release-qualified serving with caller-owned transactions.

Every function leaves commit/rollback to its caller. Staging never changes the active
release. Activation and rollback read back all projections before returning.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from psycopg import errors, sql
from psycopg.types.json import Jsonb

from cks_picks_cfb.season.database_role import assert_v5_database_environment
from cks_picks_cfb.season.projection_common import (
    PROJECTION_ORDER,
    PROJECTION_SETS,
    SERVER_COLUMNS,
    STAGING_PROJECTION_SET,
    recognized_projection_set,
)

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
    "team_season_roster": ("season", "team"),
    "team_game_stats": ("season", "game_id", "team"),
    "team_adjusted_epa": ("season", "as_of_week", "team", "role"),
    "team_game_yardage": ("season", "game_id", "team"),
    "team_resume": ("period_id", "team"),
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


def _plain(value: Any) -> Any:
    """JSON-native form, so derived and decoded check entries compare exactly."""
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def validate_candidate(
    manifest: Mapping,
    verification: Mapping,
    projections: Mapping,
    *,
    revision_raw: bytes,
    derive=None,
    validate=None,
) -> None:
    """Refuse a candidate whose report does not pass on the verified payload.

    ``projections`` is the parsed, checksum-verified payload (``prediction_runs``
    plus every table of ``PROJECTION_ORDER``). Projection checks are re-derived
    with ``derive(projections, manifest)`` (default
    ``verification.derive_checks``) and must equal the reported entries, so a
    self-reported pass is never trusted; ``validate(report, projections=...,
    manifest=manifest)`` (default ``verification.validate_report``) then checks the
    whole report and binds its identity and output refs to the run manifest.

    ``revision_raw`` is the revision manifest the run identity pins. The
    ``chart_yardage_recomputed`` prepare evidence must name its pinned byplay
    input and the payload's own ``team_game_yardage`` digest. Nothing is read
    from storage: play-level recomputation happened at prepare.
    """
    from cks_picks_cfb.season import verification as verifier

    derive = derive or verifier.derive_checks
    validate = validate or verifier.validate_report
    if isinstance(projections, Mapping):
        _require_staging_set(set(projections) - {"prediction_runs"})
    if manifest.get("schema_version") != "season_run_v1":
        raise SeasonReleaseError("unknown season run schema")
    if verification.get("schema_version") != verifier.SCHEMA_VERSION:
        raise SeasonReleaseError("unknown season verification schema")
    if (
        not isinstance(manifest.get("release_id"), str)
        or not manifest["release_id"].strip()
    ):
        raise SeasonReleaseError("release identity missing")
    identity = manifest.get("identity")
    if not isinstance(identity, Mapping) or not isinstance(
        manifest.get("identities"), Mapping
    ):
        raise SeasonReleaseError("release identity missing: identity/identities")
    for field in IDENTITY_FIELDS:
        if field not in manifest:
            raise SeasonReleaseError(f"release identity missing: {field}")
        # The recorded release columns are the ones the checks were derived for.
        if identity.get(field) != manifest[field]:
            raise SeasonReleaseError(f"release identity differs from run: {field}")
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
    refs = manifest.get("output_refs")
    if not isinstance(refs, Mapping) or "serving_projections" not in refs:
        raise SeasonReleaseError("manifest output bindings missing")
    projection_names = verifier.REQUIRED_PROJECTION_CHECKS
    checks = verification.get("checks")
    if not isinstance(checks, Mapping) or set(checks) != (
        projection_names | verifier.REQUIRED_PREPARE_CHECKS
    ):
        raise SeasonReleaseError("candidate checks missing or unexpected")
    for name, entry in checks.items():
        source = "projection" if name in projection_names else "prepare"
        if (
            not isinstance(entry, Mapping)
            or entry.get("passed") is not True
            or entry.get("source") != source
        ):
            raise SeasonReleaseError(f"candidate check failed: {name}")
    try:
        derived = derive(projections, manifest)
        validate(verification, projections=projections, manifest=manifest)
    except ValueError as error:
        raise SeasonReleaseError(f"verification report rejected: {error}") from error
    if not isinstance(derived, Mapping) or set(derived) != projection_names:
        raise SeasonReleaseError("re-derived checks are incomplete")
    for name in sorted(projection_names):
        entry = _plain(derived[name])
        if not isinstance(entry, dict) or entry.get("passed") is not True:
            raise SeasonReleaseError(f"re-derived check failed: {name}")
        if _plain(checks[name]) != entry:
            raise SeasonReleaseError(f"reported check differs from payload: {name}")
    tables = {base: projections[base] for base in PROJECTION_ORDER}
    digests = {base: projection_check(rows) for base, rows in tables.items()}
    if verification.get("projection_checks") != digests or verification.get(
        "row_counts"
    ) != {base: len(rows) for base, rows in tables.items()}:
        raise SeasonReleaseError("verified projection checks differ from payload")
    _bind_yardage_evidence(checks, digests, manifest, revision_raw)


def _bind_yardage_evidence(
    checks: Mapping, digests: Mapping, manifest: Mapping, revision_raw: bytes
) -> None:
    """The passing ``chart_yardage_recomputed`` entry must be of this payload's
    ``team_game_yardage`` digest and of the byplay input the revision pins."""
    if _sha(revision_raw) != manifest["revision_manifest_sha256"]:
        raise SeasonReleaseError("revision manifest bytes differ from the run identity")
    revision = _json(revision_raw, "revision manifest")
    inputs = revision.get("inputs")
    byplay = inputs.get("byplay") if isinstance(inputs, Mapping) else None
    if not isinstance(byplay, Mapping):
        raise SeasonReleaseError("revision manifest pins no byplay input")
    observed = checks["chart_yardage_recomputed"].get("observed")
    if not isinstance(observed, Mapping):
        raise SeasonReleaseError("chart yardage evidence missing")
    digest = digests["team_game_yardage"]
    if (observed.get("projection_sha256"), observed.get("rows")) != (
        digest["sha256"],
        digest["rows"],
    ):
        raise SeasonReleaseError("chart yardage evidence is for another payload")
    if (observed.get("byplay_uri"), observed.get("byplay_sha256")) != (
        byplay.get("uri"),
        byplay.get("sha256"),
    ):
        raise SeasonReleaseError(
            "chart yardage evidence is for another byplay input than the revision pins"
        )


def _normal(value: Any, column: str = "") -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise SeasonReleaseError("naive timestamp in release projection")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, str) and (
        column.endswith(("_at", "_utc", "_as_of"))
        or column in {"start_date", "as_of_cutoff", "data_as_of"}
        or "as_of" in column
    ):
        return _normal(datetime.fromisoformat(value.replace("Z", "+00:00")), column)
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
    """Stable full-row content identity; timestamps are normalized, not dropped.

    Server-filled columns (``release_id``, ``environment``) are never part of it,
    so one payload has the same identity in every environment.
    """
    encoded = sorted(
        json.dumps(
            {k: v for k, v in _normal(row).items() if k not in SERVER_COLUMNS},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        for row in rows
    )
    return {"rows": len(rows), "sha256": _sha(("\n".join(encoded) + "\n").encode())}


def _columns(cur, base: str) -> tuple[dict[str, str], tuple[str, ...]]:
    """(payload columns -> data type, server-filled columns), in schema order."""
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
        ("season_release_" + base,),
    )
    columns = dict(cur.fetchall())
    server = tuple(column for column in columns if column in SERVER_COLUMNS)
    if "release_id" not in server:
        raise SeasonReleaseError(f"projection schema missing: {base}")
    payload = {k: v for k, v in columns.items() if k not in SERVER_COLUMNS}
    return payload, server


def _readback(cur, release_id: str, checks: Mapping, environment: str) -> dict:
    """Read back exactly the projection set the release recorded.

    Retained releases keep the set they were staged with (``core_v1`` or
    ``charts_v1``); unknown or partial recorded sets fail.
    """
    try:
        recorded = recognized_projection_set(checks)
    except ValueError as error:
        raise SeasonReleaseError(
            "all serving projection checks are required"
        ) from error
    actual = {}
    for base in PROJECTION_SETS[recorded]:
        columns, server = _columns(cur, base)
        table = sql.Identifier("season_release_" + base)
        cur.execute(
            sql.SQL("SELECT {} FROM {} WHERE release_id = %s").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)), table
            ),
            (release_id,),
        )
        rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
        actual[base] = projection_check(rows)
        if "environment" in server:
            cur.execute(
                sql.SQL(
                    "SELECT count(*) FROM {} WHERE release_id = %s AND environment IS DISTINCT FROM %s"
                ).format(table),
                (release_id, environment),
            )
            if cur.fetchone()[0]:
                raise SeasonReleaseError(
                    f"projection rows of another environment: {base}"
                )
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


def _release(cur, release_id: str, *, for_update: bool = False) -> dict:
    columns = (*RELEASE_COLUMNS, "status")
    cur.execute(
        sql.SQL("SELECT {} FROM season_releases WHERE release_id = %s{}").format(
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(" FOR UPDATE" if for_update else ""),
        ),
        (release_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise SeasonReleaseError("release does not exist")
    return dict(zip(columns, row, strict=True))


def _active(
    cur, environment: str, season: int, *, for_update: bool = False
) -> str | None:
    cur.execute(
        "SELECT release_id FROM season_releases WHERE environment = %s AND season = %s AND status = 'active'"
        + (" FOR UPDATE" if for_update else ""),
        (environment, season),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise SeasonReleaseError("multiple active season releases")
    return str(rows[0][0]) if rows else None


def _policy(cur, release: Mapping) -> None:
    """Early, readable refusal; activate_season_release() re-checks under lock."""
    cur.execute(
        "SELECT model_manifest_sha256, workflow_version, grading_policy_sha256, enabled FROM season_release_policies WHERE environment = %s AND season = %s",
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


def _require_staging_set(tables: Collection[str]) -> None:
    """New candidates must carry exactly the staging set (``charts_v2``)."""
    names = set(tables)
    if names == set(PROJECTION_ORDER):
        return
    try:
        recorded = recognized_projection_set(names - {"prediction_runs"})
    except ValueError:
        recorded = None
    if recorded is not None:
        raise SeasonReleaseError(
            f"{recorded} candidates are no longer staged; build a {STAGING_PROJECTION_SET} candidate"
        )
    raise SeasonReleaseError("complete fixed serving projections are required")


def _check_projection_scope(
    projections: Mapping, season: int, active_week: int
) -> None:
    """Payload-level scope; the 0025 foreign keys are the database backstop.

    ``games`` is the full season schedule, so it may hold games without
    predictions; every other game-keyed row must reference a release game.
    """
    _require_staging_set(projections)
    for base, keys in PROJECTION_KEYS.items():
        rows = projections[base]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise SeasonReleaseError(f"invalid projection rows: {base}")
        seen = set()
        for row in rows:
            if SERVER_COLUMNS & row.keys():
                raise SeasonReleaseError(
                    f"server-filled column in projection payload: {base}"
                )
            if any(k not in row for k in keys):
                raise SeasonReleaseError(f"projection key missing: {base}")
            key = tuple(row[k] for k in keys)
            if key in seen:
                raise SeasonReleaseError(f"duplicate projection key: {base}")
            seen.add(key)
            if "season" in row and row["season"] != season:
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
    for base in (
        "game_venues",
        "predictions",
        "prediction_grades",
        "market_quotes",
        "market_snapshots",
        "prediction_market_selections",
    ):
        if any(row.get("game_id") not in games for row in projections[base]):
            raise SeasonReleaseError(f"{base} reference a game outside the release")
    selected = {row["week"]: row["run_id"] for row in selections}
    for row in projections["predictions"]:
        if selected.get(games[row["game_id"]]["week"]) != row["run_id"]:
            raise SeasonReleaseError("prediction is outside the selected schedule")
    predicted = {(row["run_id"], row["game_id"]) for row in projections["predictions"]}
    prior = {gid for gid, row in games.items() if row["week"] < active_week}
    if prior - results:
        raise SeasonReleaseError("prior-week finals are incomplete")
    for row in projections["game_results"]:
        if row.get("home_points") is None or row.get("away_points") is None:
            raise SeasonReleaseError("final score missing")
    for row in projections["prediction_grades"]:
        if (row["run_id"], row["game_id"]) not in predicted:
            raise SeasonReleaseError("grade is outside the selected run")
        if row["game_id"] not in results:
            raise SeasonReleaseError("grade lacks prediction or final")
    for row in projections["prediction_market_selections"]:
        if (row["run_id"], row["game_id"]) not in predicted:
            raise SeasonReleaseError("market selection lacks its prediction")
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


def _check_resume_scope(projections: Mapping) -> None:
    """The résumé projection of a ``resume_v1`` candidate has rows for every period."""
    if not projections["team_resume"]:
        raise SeasonReleaseError("team resume projections are required")


def _check_chart_scope(projections: Mapping, active_week: int) -> None:
    """The chart tables of a ``charts_v2`` candidate: the roster always, game
    statistics and yardage once a week has completed, adjusted EPA from Week 3."""
    if not projections["team_season_roster"]:
        raise SeasonReleaseError("the FBS team roster is required")
    if active_week > 0 and not projections["team_game_stats"]:
        raise SeasonReleaseError("team game statistics are required")
    if active_week > 0 and not projections["team_game_yardage"]:
        raise SeasonReleaseError("team game yardage is required")
    if active_week >= 3 and not projections["team_adjusted_epa"]:
        raise SeasonReleaseError("adjusted team EPA is required from Week 3")


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
    revision_raw: bytes,
    environment: str,
) -> str:
    """Stage fully verified rows without altering public selection; never commits.

    ``revision_raw`` is the revision manifest the run identity pins (its sha256
    is ``revision_manifest_sha256``); staging reads nothing from storage.

    The payload is environment-free: ``release_id`` (and ``environment`` where the
    schema has it) are filled in here, so the same bytes stage in every
    environment with identical projection checks.

    The database records only logical ``season-run:`` URIs, never the local paths
    staging read the bytes from: ``run_manifest_uri`` must be the manifest's own
    ``run_manifest_logical_uri`` and the recorded verification URI is its
    ``verification_logical_uri``.
    """
    if getattr(conn, "autocommit", False):
        raise SeasonReleaseError(
            "release operations require a caller-owned transaction"
        )
    manifest = _json(manifest_raw, "manifest")
    verification = _json(verification_raw, "verification")
    if _sha(verification_raw) != manifest.get("verification_sha256"):
        raise SeasonReleaseError("verification bytes changed")
    logical = {
        key: manifest.get(key)
        for key in ("run_manifest_logical_uri", "verification_logical_uri")
    }
    prefix = f"season-run:{manifest.get('release_id')}/"
    if any(
        not isinstance(uri, str) or not uri.startswith(prefix)
        for uri in logical.values()
    ):
        raise SeasonReleaseError("run manifest lacks logical season-run URIs")
    if run_manifest_uri != logical["run_manifest_logical_uri"]:
        raise SeasonReleaseError("run manifest URI must be its logical URI")
    refs = manifest.get("output_refs")
    ref = refs.get("serving_projections") if isinstance(refs, Mapping) else None
    if not isinstance(ref, Mapping) or _sha(projection_raw) != ref.get("sha256"):
        raise SeasonReleaseError("serving projection bytes are not verified")
    payload = _json(projection_raw, "projections")
    _require_staging_set(set(payload) - {"prediction_runs"})
    if "prediction_runs" not in payload:
        raise SeasonReleaseError("complete fixed serving projections are required")
    projections = {base: payload[base] for base in PROJECTION_ORDER}
    registry = payload["prediction_runs"]
    try:
        season, active_week = manifest["season"], manifest["active_week"]
    except KeyError as error:
        raise SeasonReleaseError("release identity missing") from error
    _check_projection_scope(projections, season, active_week)
    _check_chart_scope(projections, active_week)
    _check_resume_scope(projections)
    validate_candidate(manifest, verification, payload, revision_raw=revision_raw)
    checks = {base: projection_check(rows) for base, rows in projections.items()}
    release_id = f"{environment}-{manifest['release_id']}"
    record = {
        "release_id": release_id,
        "environment": environment,
        **{k: manifest[k] for k in IDENTITY_FIELDS},
        "run_manifest_uri": run_manifest_uri,
        "run_manifest_sha256": _sha(manifest_raw),
        "verification_uri": logical["verification_logical_uri"],
        "verification_sha256": _sha(verification_raw),
        "projection_checks": checks,
    }
    with conn.cursor() as cur:
        assert_v5_database_environment(cur, environment)
        _lock(cur, environment, season)
        schemas = {base: _columns(cur, base) for base in PROJECTION_ORDER}
        for base, rows in projections.items():
            if any(set(row) != set(schemas[base][0]) for row in rows):
                raise SeasonReleaseError(f"projection columns differ: {base}")
        _register_runs(cur, registry, season)
        cur.execute(
            "SELECT release_id FROM season_releases WHERE release_id = %s",
            (release_id,),
        )
        if cur.fetchone():
            existing = _release(cur, release_id)
            if any(existing[k] != record[k] for k in RELEASE_COLUMNS):
                raise SeasonReleaseError("immutable release collision")
            _readback(cur, release_id, checks, environment)
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
        filled = {"release_id": release_id, "environment": environment}
        try:
            # Parents first; the deferred 0025 links are all checked below.
            for base in PROJECTION_ORDER:
                columns, server = schemas[base]
                names = (*server, *columns)
                cur.executemany(
                    sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier("season_release_" + base),
                        sql.SQL(", ").join(map(sql.Identifier, names)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in names),
                    ),
                    [
                        (
                            *(filled[k] for k in server),
                            *(
                                Jsonb(row[k]) if columns[k] == "jsonb" else row[k]
                                for k in columns
                            ),
                        )
                        for row in projections[base]
                    ],
                )
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        except errors.ForeignKeyViolation as error:
            raise SeasonReleaseError(
                f"projection links are broken: {error.diag.message_primary}"
            ) from error
        _readback(cur, release_id, checks, environment)
    return release_id


def _server_read_only(cur) -> bool:
    """Server-side state: session default and current transaction both read-only.

    psycopg's ``conn.read_only`` stays None when read-only is set through the
    connection ``options``, and a pending ``SET TRANSACTION READ ONLY`` alone
    does not make later transactions read-only, so both settings must be on.
    """
    cur.execute(
        "SELECT current_setting('default_transaction_read_only'), current_setting('transaction_read_only')"
    )
    return cur.fetchone() == ("on", "on")


def _preview_proof(conn, candidate: Mapping) -> None:
    if conn is None:
        raise SeasonReleaseError(
            "Production requires independently read-only Preview rehearsal"
        )
    with conn.cursor() as cur:
        if not _server_read_only(cur):
            raise SeasonReleaseError(
                "Production requires independently read-only Preview rehearsal"
            )
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
                _readback(cur, release_id, checks, "preview")
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
        # Rollback (owner) writes directly and locks rows here; the pipeline has
        # no UPDATE privilege and activate_season_release() takes the row locks.
        previous = _active(cur, environment, season, for_update=rollback)
        if previous != expected_previous_release_id:
            raise SeasonReleaseError("active release changed since review")
        candidate = _release(cur, release_id, for_update=rollback)
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
            _policy(cur, candidate)
            if environment == "production":
                _preview_proof(preview_conn, candidate)
        checks = _readback(cur, release_id, candidate["projection_checks"], environment)
        digest = _sha(
            json.dumps(checks, sort_keys=True, separators=(",", ":")).encode()
        )
        action = "rollback" if rollback else "activate"
        if rollback:
            cur.execute(
                "UPDATE season_releases SET status = 'rolled_back' WHERE release_id = %s",
                (previous,),
            )
            cur.execute(
                "UPDATE season_releases SET status = 'active', activated_at = NOW() WHERE release_id = %s",
                (release_id,),
            )
            cur.execute(
                "INSERT INTO season_release_history (environment, season, prior_release_id, release_id, action, decision_ref, readback_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    environment,
                    season,
                    previous,
                    release_id,
                    action,
                    decision_ref,
                    digest,
                ),
            )
        else:
            try:
                cur.execute(
                    "SELECT activate_season_release(%s, %s, %s)",
                    (release_id, previous, digest),
                )
            except errors.RaiseException as error:
                raise SeasonReleaseError(error.diag.message_primary) from error
        if _active(cur, environment, season) != release_id:
            raise SeasonReleaseError("activation pointer readback differs")
        _readback(cur, release_id, checks, environment)
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
