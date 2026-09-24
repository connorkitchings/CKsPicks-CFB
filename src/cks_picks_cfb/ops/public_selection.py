"""Explicit, transactional public selection of one immutable weekly run."""

from __future__ import annotations

from typing import Any


class PublicSelectionError(ValueError):
    """A run cannot be exposed as the selected public week."""


def select_week_run(
    cur: Any,
    *,
    season: int,
    week: int,
    run_id: str,
    reason: str,
    allow_v4_fallback: bool = False,
) -> str | None:
    """Select a verified run inside the caller's transaction.

    Callers must hold the normal pipeline lease. A missing or partial run never
    becomes public; the current-week pointer and historic selection stay in sync.
    """
    if not reason.strip():
        raise PublicSelectionError("selection reason is required")
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
        cur.execute(
            "SELECT model_id, inference_bundle_sha256, first_live_season, first_live_week "
            "FROM v5_release_policy WHERE id = 1"
        )
        policy = cur.fetchone()
        if not policy or policy[0] != model_id or policy[1] != bundle_sha:
            raise PublicSelectionError("V5 run differs from approved model bundle")
        if evidence_class == "pending" and (season, week) < (policy[2], policy[3]):
            raise PublicSelectionError(
                "prospective V5 slate predates approved activation"
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
