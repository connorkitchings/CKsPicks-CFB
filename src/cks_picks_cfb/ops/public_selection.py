"""Explicit, transactional public selection of one immutable weekly run."""

from __future__ import annotations

import os
from typing import Any

# A display-only run (Contract 04, Amendment 9) may go public only this long after its cutoff.
MAX_DISPLAY_AGE_HOURS = 6


class PublicSelectionError(ValueError):
    """A run cannot be exposed as the selected public week."""


def _run_manifest(
    storage: Any, *, season: int, week: int, run_id: str, artifact_sha: str
) -> dict[str, Any]:
    """The immutable run manifest, bound to the stored run by its artifact hash."""
    from cks_picks_cfb.artifacts import prediction_run_manifest_path, read_json_artifact

    manifest = read_json_artifact(
        prediction_run_manifest_path(season, week, run_id), storage
    )
    if manifest.get("artifact_sha256") != artifact_sha:
        raise PublicSelectionError("stored run differs from immutable artifact")
    return manifest


def _require_open_pending_window(
    cur: Any, *, season: int, week: int, run_id: str, as_of: Any
) -> None:
    """A pending run is selectable only while it is recent and none of its games has started.

    Its games must be exactly the week's games scheduled after its cutoff, so a run cannot
    hide a game that kicked off since it was built. One database clock reading decides it.
    """
    if not as_of:
        raise PublicSelectionError("pending run manifest has no data cutoff")
    cur.execute(
        "WITH clock AS (SELECT clock_timestamp() AS now) "
        "SELECT (SELECT now FROM clock) < %s::timestamptz + make_interval(hours => %s), "
        "COUNT(*) FILTER (WHERE p.game_id IS NOT NULL "
        "AND g.start_date <= (SELECT now FROM clock)), "
        "COUNT(*) FILTER (WHERE p.game_id IS NULL OR g.start_date <= %s::timestamptz) "
        "FROM games g LEFT JOIN predictions p "
        "ON p.game_id = g.game_id AND p.run_id = %s "
        "WHERE g.season = %s AND g.week = %s "
        "AND (g.start_date > %s::timestamptz OR p.game_id IS NOT NULL)",
        (as_of, MAX_DISPLAY_AGE_HOURS, as_of, run_id, season, week, as_of),
    )
    fresh, started, mismatched = cur.fetchone()
    if not fresh:
        raise PublicSelectionError(
            f"pending run is older than {MAX_DISPLAY_AGE_HOURS} hours"
        )
    if int(started):
        raise PublicSelectionError("pending run includes a game that has kicked off")
    if int(mismatched):
        raise PublicSelectionError(
            "pending run's games differ from the games scheduled after its cutoff"
        )


def select_week_run(
    cur: Any,
    *,
    season: int,
    week: int,
    run_id: str,
    reason: str,
    allow_v4_fallback: bool = False,
    environment: str | None = None,
) -> str | None:
    """Select a verified run inside the caller's transaction.

    Callers must hold the normal pipeline lease. A missing or partial run never
    becomes public; the current-week pointer and historic selection stay in sync.
    """
    if not reason.strip():
        raise PublicSelectionError("selection reason is required")
    environment = environment or os.getenv("CFB_ARTIFACT_ENV", "production")
    if environment not in {"preview", "production"}:
        raise PublicSelectionError("invalid selection environment")
    # A row lock cannot serialize the first selection because no row exists yet.
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (season, week))
    cur.execute(
        "SELECT season, week, state, expected_games, predicted_games, model_id, "
        "artifact_sha256, evidence_class, model_bundle_sha256 FROM prediction_runs "
        "WHERE run_id = %s FOR UPDATE",
        (run_id,),
    )
    candidate = cur.fetchone()
    if candidate is None:
        raise PublicSelectionError(f"unknown prediction run: {run_id}")
    (
        run_season,
        run_week,
        state,
        expected,
        predicted,
        model_id,
        artifact_sha,
        evidence_class,
        bundle_sha,
    ) = candidate
    manifest = None
    if (run_season, run_week) != (season, week):
        raise PublicSelectionError("selected run belongs to another season or week")
    if (
        state not in {"published", "frozen", "scored"}
        or not expected
        or predicted != expected
    ):
        raise PublicSelectionError("selected run is incomplete or not published")
    if not artifact_sha or len(str(artifact_sha)) != 64:
        raise PublicSelectionError("selected run has no verified immutable artifact")
    if not str(model_id or "").startswith("v5-"):
        if not allow_v4_fallback or evidence_class != "legacy":
            raise PublicSelectionError("public selection requires V5")
    elif evidence_class not in {"pending", "replay", "live"}:
        raise PublicSelectionError("V5 run lacks a truthful evidence class")
    else:
        from cks_picks_cfb.ops.v5_release import (
            V5ReleaseError,
            assert_v5_database_environment,
        )

        try:
            assert_v5_database_environment(cur, environment)
        except V5ReleaseError as exc:
            raise PublicSelectionError(str(exc)) from exc
        cur.execute(
            "SELECT CASE WHEN COUNT(*) = 1 THEN MIN(approval_id) ELSE NULL END, "
            "MIN(model_id), MIN(inference_bundle_sha256), MIN(first_live_season), MIN(first_live_week) "
            "FROM v5_model_bundle_approvals "
            "WHERE model_id = %s AND inference_bundle_sha256 = %s",
            (model_id, bundle_sha),
        )
        policy = cur.fetchone()
        if (
            not policy
            or policy[0] is None
            or policy[1] != model_id
            or policy[2] != bundle_sha
        ):
            raise PublicSelectionError("V5 run differs from approved model bundle")
        from cks_picks_cfb.ops.v5_revocations import (
            V5RevocationError,
            assert_release_records_active,
        )

        try:
            assert_release_records_active(cur, [("bundle_approval", str(policy[0]))])
        except V5RevocationError as exc:
            raise PublicSelectionError(str(exc)) from exc
        if evidence_class in {"pending", "live"} and (season, week) < (
            policy[3],
            policy[4],
        ):
            raise PublicSelectionError(
                "prospective V5 slate predates approved activation"
            )
        if environment == "production" or model_id == "v5-intended-update-2026-v1":
            if evidence_class not in {"pending", "live", "replay"}:
                raise PublicSelectionError(
                    "production V5 selection requires a reviewed release"
                )
            from cks_picks_cfb.data.storage import get_storage

            storage = get_storage(environment=environment)
            manifest = _run_manifest(
                storage,
                season=season,
                week=week,
                run_id=run_id,
                artifact_sha=artifact_sha,
            )
            if model_id == "v5-intended-update-2026-v1":
                from cks_picks_cfb.ops.v5_intended_update_release import (
                    require_intended_update_release_record,
                )

                require_intended_update_release_record(
                    cur,
                    manifest=manifest,
                    storage=storage,
                    season=season,
                    week=week,
                    environment=environment,
                )
            elif evidence_class == "replay":
                from cks_picks_cfb.ops.v5_release import (
                    require_replay_release_record,
                )

                require_replay_release_record(
                    cur,
                    manifest=manifest,
                    storage=storage,
                    environment="production",
                    season=season,
                    week=week,
                )
            else:
                from cks_picks_cfb.ops.v5_release import require_release_record

                require_release_record(
                    cur, manifest=manifest, storage=storage, season=season, week=week
                )
    cur.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE g.season <> %s OR g.week <> %s) "
        "FROM predictions p JOIN games g ON g.game_id = p.game_id "
        "WHERE p.run_id = %s",
        (season, week, run_id),
    )
    stored_count, foreign_count = cur.fetchone()
    if int(stored_count) != expected or int(foreign_count) != 0:
        raise PublicSelectionError("selected run's stored predictions are incomplete")
    # Frozen, scored and replay runs are exempt; a pending one must still be current.
    if evidence_class == "pending" and state == "published":
        if manifest is None:
            from cks_picks_cfb.data.storage import get_storage

            manifest = _run_manifest(
                get_storage(environment=environment),
                season=season,
                week=week,
                run_id=run_id,
                artifact_sha=artifact_sha,
            )
        _require_open_pending_window(
            cur,
            season=season,
            week=week,
            run_id=run_id,
            as_of=manifest.get("data_as_of"),
        )
    cur.execute(
        "SELECT run_id FROM site_week_selections WHERE season = %s AND week = %s FOR UPDATE",
        (season, week),
    )
    existing = cur.fetchone()
    previous = str(existing[0]) if existing else None
    if previous == run_id:
        return previous
    cur.execute(
        "INSERT INTO site_week_selections (season, week, run_id, reason, selected_at) "
        "VALUES (%s, %s, %s, %s, NOW()) "
        "ON CONFLICT (season, week) DO UPDATE SET run_id = EXCLUDED.run_id, "
        "reason = EXCLUDED.reason, selected_at = NOW()",
        (season, week, run_id, reason),
    )
    cur.execute(
        "INSERT INTO site_week_selection_history "
        "(season, week, prior_run_id, run_id, reason) VALUES (%s, %s, %s, %s, %s)",
        (season, week, previous, run_id, reason),
    )
    cur.execute(
        "UPDATE current_week SET active_run_id = %s, updated_at = NOW() "
        "WHERE id = 1 AND season = %s AND week = %s",
        (run_id, season, week),
    )
    return previous


def deselect_week_run(cur: Any, *, season: int, week: int, reason: str) -> str | None:
    """Remove a week's public selection inside the caller's transaction.

    Only a rollback of a cutover that opened a brand-new week needs this. The pipeline
    role cannot DELETE from ``site_week_selections``, so the statement fails closed
    (and the caller's transaction rolls back) unless the connection is the owner or
    migrator login. History keeps the removed run as both prior and current run because
    ``site_week_selection_history.run_id`` is NOT NULL; the reason says it was removed.
    """
    if not reason.strip():
        raise PublicSelectionError("deselection reason is required")
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (season, week))
    cur.execute(
        "SELECT run_id FROM site_week_selections WHERE season = %s AND week = %s "
        "FOR UPDATE",
        (season, week),
    )
    existing = cur.fetchone()
    if existing is None:
        return None
    previous = str(existing[0])
    cur.execute(
        "INSERT INTO site_week_selection_history "
        "(season, week, prior_run_id, run_id, reason) VALUES (%s, %s, %s, %s, %s)",
        (season, week, previous, previous, f"DESELECTED: {reason}"),
    )
    cur.execute(
        "DELETE FROM site_week_selections WHERE season = %s AND week = %s",
        (season, week),
    )
    return previous


def select_week_runs_batch(
    cur: Any,
    *,
    season: int,
    runs_by_week: dict[int, str],
    reason: str,
    environment: str | None = None,
) -> dict[int, str | None]:
    """Select a complete multiweek replacement in the caller's transaction.

    The caller commits once after this returns. Any failed run check raises and
    rolls back all week pointers, history inserts, and the statistics refresh.
    """
    if not runs_by_week or any(week < 0 for week in runs_by_week):
        raise PublicSelectionError("batch selection requires valid weeks")
    previous = {}
    for week in sorted(runs_by_week):
        previous[week] = select_week_run(
            cur,
            season=season,
            week=week,
            run_id=runs_by_week[week],
            reason=reason,
            environment=environment,
        )
    from scripts.pipeline.score_to_db import RECOMPUTE_STATS_SQL

    cur.execute(RECOMPUTE_STATS_SQL, {"season": season})
    return previous
