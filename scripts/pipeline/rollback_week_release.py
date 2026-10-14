#!/usr/bin/env python3
"""Roll back a published, pending, unfrozen Week N release to the Week N-1 site.

Undoes what opening Week N exposed, and nothing else:
- deletes the Week N ``site_week_selections`` row through the shared deselect
  path (history keeps a ``DESELECTED:`` row);
- restores ``current_week`` to (season, N-1) with the Week N-1 selected run active;
- deletes the as-of-N ``team_season_stats`` rows and the ``v5_rating_snapshots``
  rows only when the release receipt declares this release published them and
  the database agrees (team stats: same season, as-of week and Silver
  ``source_versions``; snapshots: the run's own ``rating_manifest_sha256``, not
  referenced by any other run). Without a receipt both scopes are kept.

The run row, its predictions and market rows stay: runs are immutable, and an
unselected published run is an audit record, not a public one. Never touched:
R2 artifacts, catalog registrations, approval/authorization rows, schedule and
venue rows, and Week N matchup rows (``team_possession_*``,
``team_rating_components``, ``matchup_data_publications``): in ``predictions``
mode the site renders a matchup only for a week with a selected run, so they go
inert once Week N is deselected (``market`` mode would still show them).

Fail-closed contract:
- The run must be state='published', evidence_class='pending', never frozen
  and ungraded. ``validation.display_only`` is not consulted.
- The Week N selection (if any) and ``current_week.active_run_id`` (if set) must
  reference this run; ``current_week`` must be (season, N); Week N-1 must have a
  selected run to restore.
- Snapshots still referenced by ``team_rating_components`` (matchup data) abort
  the rollback: restore the prior matchup payload first.
- ``--apply`` needs the owner/migrator login; the pipeline role is refused up
  front (it cannot DELETE the selection anyway). Dry run is the default and
  prints the before state and the planned after state; ``--apply`` prints the
  read-back after state and commits only when it equals the plan.

    zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/rollback_week_release.py \\
      --environment preview --week 7 --run-id <run id from docs/status.md> \\
      --release-receipt <receipt.json> --reason "<contract-ref>"     # dry run
    # ... review, then add --apply (user-run, owner/migrator login) ...

Release receipt (``week_release_receipt_v1``; both ``published`` entries optional)::

    {"schema_version": "week_release_receipt_v1", "environment": "preview",
     "run_id": "...", "season": 2026, "week": 7,
     "published": {
       "team_season_stats": {"as_of_week": 7, "source_versions": {"byplay": "...", ...}},
       "v5_rating_snapshots": {"source_manifest_sha256": "<64 hex>"}}}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.ops.public_selection import PublicSelectionError, deselect_week_run

RECEIPT_SCHEMA = "week_release_receipt_v1"


class WeekRollbackError(ValueError):
    """The database or receipt does not match a reversible Week N release."""


def load_receipt(
    raw: dict[str, Any], *, environment: str, run_id: str, season: int, week: int
) -> dict[str, Any]:
    """Validate the receipt's identity and return its ``published`` scopes."""
    if raw.get("schema_version") != RECEIPT_SCHEMA:
        raise WeekRollbackError(f"receipt schema is not {RECEIPT_SCHEMA}")
    identity = (raw.get("environment"), raw.get("run_id"), raw.get("season"))
    if identity != (environment, run_id, season) or raw.get("week") != week:
        raise WeekRollbackError("receipt belongs to another environment, run or week")
    published = raw.get("published") or {}
    stats = published.get("team_season_stats")
    if stats is not None and (
        stats.get("as_of_week") != week
        or not isinstance(stats.get("source_versions"), dict)
        or not stats["source_versions"]
    ):
        raise WeekRollbackError(
            "receipt team stats must be as-of this week with versions"
        )
    snapshots = published.get("v5_rating_snapshots")
    if (
        snapshots is not None
        and len(str(snapshots.get("source_manifest_sha256") or "")) != 64
    ):
        raise WeekRollbackError("receipt rating snapshots need a 64-hex manifest sha")
    return {"team_season_stats": stats, "v5_rating_snapshots": snapshots}


def assert_owner_login(cur: Any) -> str:
    cur.execute("SELECT current_user")
    who = str(cur.fetchone()[0])
    if who.endswith("_pipeline"):
        raise WeekRollbackError(
            f"connected as restricted pipeline role {who}; use the owner/migrator login"
        )
    return who


def _count(cur: Any, sql: str, params: tuple) -> int:
    cur.execute(sql, params)
    return int(cur.fetchone()[0])


def read_state(
    cur: Any,
    *,
    season: int,
    week: int,
    stats_versions: str | None,
    rating_sha: str | None,
) -> dict[str, Any]:
    """The serving facts this rollback changes, in one comparable dict."""
    cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1")
    pointer = cur.fetchone()
    if pointer is None:
        raise WeekRollbackError("current_week has no row (id = 1) to restore")
    cw_season, cw_week, active = pointer
    # Every week of the season, so the read-back proves Weeks 0..N-1 unchanged.
    cur.execute(
        "SELECT week, run_id FROM site_week_selections WHERE season = %s ORDER BY week",
        (season,),
    )
    selections: dict[str, str | None] = {str(w): None for w in (week - 1, week)}
    selections.update({str(w): str(r) for w, r in cur.fetchall()})
    state = {
        "current_week": [cw_season, cw_week, active],
        "selections": selections,
        "team_season_stats_as_of_week": _count(
            cur,
            "SELECT count(*) FROM team_season_stats WHERE season = %s AND as_of_week = %s",
            (season, week),
        ),
        "team_season_stats_release_rows": None,
        "v5_rating_snapshots_run_manifest": None,
    }
    if stats_versions is not None:
        state["team_season_stats_release_rows"] = _count(
            cur,
            "SELECT count(*) FROM team_season_stats WHERE season = %s "
            "AND as_of_week = %s AND source_versions = %s::jsonb",
            (season, week, stats_versions),
        )
    if rating_sha is not None:
        state["v5_rating_snapshots_run_manifest"] = _count(
            cur,
            "SELECT count(*) FROM v5_rating_snapshots WHERE source_manifest_sha256 = %s",
            (rating_sha,),
        )
    return state


def plan_rollback(
    cur: Any,
    *,
    season: int,
    week: int,
    run_id: str,
    receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    """Check every guard read-only and return the before state and the planned after."""
    if week < 1:
        raise WeekRollbackError("week must be at least 1 so Week N-1 can be restored")
    cur.execute(
        "SELECT state, evidence_class, frozen_at, rating_manifest_sha256 "
        "FROM prediction_runs WHERE run_id = %s AND season = %s AND week = %s",
        (run_id, season, week),
    )
    run = cur.fetchone()
    if run is None:
        raise WeekRollbackError(f"run {run_id} not present for {season} week {week}")
    state, evidence, frozen_at, rating_sha = run
    if state in {"frozen", "scored"} or frozen_at is not None:
        raise WeekRollbackError(
            f"run is {state} (frozen_at={frozen_at}); never rolled back"
        )
    if state != "published" or evidence != "pending":
        raise WeekRollbackError(
            f"run is state={state} evidence={evidence}; only a published pending run qualifies"
        )
    grades = _count(
        cur, "SELECT count(*) FROM prediction_grades WHERE run_id = %s", (run_id,)
    )
    if grades:
        raise WeekRollbackError(
            f"run has {grades} grade(s); a scored week is never rolled back"
        )
    cur.execute(
        "SELECT run_id FROM site_week_selections WHERE season = %s AND week = %s",
        (season, week - 1),
    )
    prior = cur.fetchone()
    if prior is None:
        raise WeekRollbackError(f"week {week - 1} has no selected run to restore")
    prior_run = str(prior[0])

    scopes = receipt or {"team_season_stats": None, "v5_rating_snapshots": None}
    stats = scopes["team_season_stats"]
    stats_versions = (
        json.dumps(stats["source_versions"], sort_keys=True) if stats else None
    )
    snapshots = scopes["v5_rating_snapshots"]
    snapshot_sha = snapshots["source_manifest_sha256"] if snapshots else None
    notes: list[str] = []
    if receipt is None:
        notes.append("no release receipt: team stats and rating snapshots are kept")
    if snapshot_sha is not None:
        if snapshot_sha != rating_sha:
            raise WeekRollbackError(
                "receipt rating manifest differs from the run's own manifest"
            )
        cur.execute(
            "SELECT run_id FROM prediction_runs "
            "WHERE rating_manifest_sha256 = %s AND run_id <> %s ORDER BY run_id",
            (snapshot_sha, run_id),
        )
        sharers = [str(r[0]) for r in cur.fetchall()]
        if sharers:
            notes.append(f"rating snapshots kept: manifest also used by {sharers}")
            snapshot_sha = None
        else:
            dependents = _count(
                cur,
                "SELECT count(*) FROM team_rating_components WHERE v5_snapshot_id IN "
                "(SELECT snapshot_id FROM v5_rating_snapshots WHERE source_manifest_sha256 = %s)",
                (snapshot_sha,),
            )
            if dependents:
                raise WeekRollbackError(
                    f"{dependents} team_rating_components row(s) reference the snapshots; "
                    "restore the prior matchup payload first"
                )

    before = read_state(
        cur,
        season=season,
        week=week,
        stats_versions=stats_versions,
        rating_sha=rating_sha,
    )
    if before["current_week"][:2] != [season, week] or before["current_week"][
        2
    ] not in (
        run_id,
        None,
    ):
        raise WeekRollbackError(
            f"current_week is {before['current_week']}; expected ({season}, {week}, this run or NULL)"
        )
    if before["selections"][str(week)] not in (run_id, None):
        raise WeekRollbackError(
            f"week selection points at {before['selections'][str(week)]}, not this run"
        )

    after = json.loads(json.dumps(before))
    after["current_week"] = [season, week - 1, prior_run]
    after["selections"][str(week)] = None
    if stats_versions is not None:
        removed = before["team_season_stats_release_rows"]
        after["team_season_stats_as_of_week"] -= removed
        after["team_season_stats_release_rows"] = 0
    if snapshot_sha is not None:
        after["v5_rating_snapshots_run_manifest"] = 0
    return {
        "season": season,
        "week": week,
        "run_id": run_id,
        "prior_run_id": prior_run,
        "stats_versions": stats_versions,
        "snapshot_sha": snapshot_sha,
        "rating_sha": rating_sha,
        "notes": notes,
        "before": before,
        "after": after,
    }


def apply_rollback(cur: Any, plan: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Apply the plan in the caller's transaction and return the read-back state."""
    assert_owner_login(cur)
    season, week = plan["season"], plan["week"]
    deselect_week_run(cur, season=season, week=week, reason=reason)
    cur.execute(
        "UPDATE current_week SET season = %s, week = %s, active_run_id = %s, "
        "updated_at = NOW() WHERE id = 1",
        (season, week - 1, plan["prior_run_id"]),
    )
    if plan["stats_versions"] is not None:
        cur.execute(
            "DELETE FROM team_season_stats WHERE season = %s AND as_of_week = %s "
            "AND source_versions = %s::jsonb",
            (season, week, plan["stats_versions"]),
        )
    if plan["snapshot_sha"] is not None:
        cur.execute(
            "DELETE FROM v5_rating_snapshots WHERE source_manifest_sha256 = %s",
            (plan["snapshot_sha"],),
        )
    return read_state(
        cur,
        season=season,
        week=week,
        stats_versions=plan["stats_versions"],
        rating_sha=plan["rating_sha"],
    )


def _print_state(label: str, state: dict[str, Any]) -> None:
    print(f"{label}: {json.dumps(state, sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--release-receipt", type=Path, default=None)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--apply", action="store_true", help="Write (default: dry run)")
    args = parser.parse_args(argv)

    url = args.database_url or os.getenv("DATABASE_URL")
    if not url:
        print(
            "Set --database-url or DATABASE_URL (owner/migrator login).",
            file=sys.stderr,
        )
        return 2
    try:
        receipt = None
        if args.release_receipt is not None:
            receipt = load_receipt(
                json.loads(args.release_receipt.read_text()),
                environment=args.environment,
                run_id=args.run_id,
                season=args.season,
                week=args.week,
            )
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            if args.apply:
                assert_owner_login(cur)
            plan = plan_rollback(
                cur,
                season=args.season,
                week=args.week,
                run_id=args.run_id,
                receipt=receipt,
            )
            print(f"reason: {args.reason}")
            for note in plan["notes"]:
                print(f"note: {note}")
            _print_state("before", plan["before"])
            if not args.apply:
                _print_state("after (planned)", plan["after"])
                print("Dry run: nothing written.")
                return 0
            after = apply_rollback(cur, plan, reason=args.reason)
            _print_state("after", after)
            if after != plan["after"]:
                conn.rollback()
                print(
                    "VERIFY FAIL: read-back differs from the plan; rolled back.",
                    file=sys.stderr,
                )
                return 3
            conn.commit()
            print(
                f"Rollback applied and verified: site restored to week {args.week - 1}."
            )
            return 0
    # Leaving the connection block on an error rolls the transaction back first.
    except (
        WeekRollbackError,
        PublicSelectionError,
        psycopg.errors.InsufficientPrivilege,
    ) as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
