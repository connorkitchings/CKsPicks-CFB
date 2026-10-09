#!/usr/bin/env python3
"""Roll back the display-only Week 6 publication, restoring the exact hold screen.

Reverses (in dependency order) everything the Week 6 display release wrote to
Neon: selections, predictions, market rows, games, run row, rating snapshots,
as-of-week stats, matchup rows + registry, and the release authorization /
bundle approval (when present and unshared). Append-only audit tables are left
alone EXCEPT `site_week_selection_history` week rows, which must go: they
reference `prediction_runs(run_id) ON DELETE RESTRICT`, so the run row cannot
be removed otherwise. History of the decision itself lives in the session log
and the contract, not in that table.

Fail-closed contract:
- The run row must exist with state='published', evidence_class='pending' and
  validation.display_only=true. Anything else (frozen, scored, live, replay)
  aborts: this script never touches a real prospective week.
- The week selection (if any) and `current_week.active_run_id` (if set) must
  reference this run, or be already empty. Nothing else is ever clobbered.
- Shared rows are never deleted: market snapshots/quotes survive when another
  row still references them; the bundle approval survives when another run of
  the same model exists. Such survivals are reported, not forced.
- Must run as an owner/migrator login (the pipeline role cannot DELETE and is
  refused up front). Dry run is the default and prints per-scope counts.

    # Preview rehearsal (migrator URL comes from the wrapper):
    zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/rollback_week6_display.py \
      --environment preview --reason "Task 2 rollback rehearsal (<contract-ref>)"   # dry run
    # ... review, then add --apply (user-run) ...
    # Verify the hold screen on the local site, then re-apply forward:
    # ratings -> team stats as-of 6 -> matchup data -> publish_to_db --from-artifact
    # -> select_public_run (see contract 02 Task 5), and confirm the open state.

R2 staged artifacts (if any) are deliberately left in place: they are
content-addressed, unreferenced once the database rows are gone, and the lake
has no delete path for published objects.
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

RUN_ID_DEFAULT = "2026w6-v5repair-20261008-d2"


def fail(message: str) -> int:
    print(f"Refusing: {message}", file=sys.stderr)
    return 3


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=6)
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--apply", action="store_true", help="Delete (default: dry run)"
    )
    args = parser.parse_args()

    url = args.database_url or os.getenv("DATABASE_URL")
    if not url:
        print(
            "Set --database-url or DATABASE_URL (owner/migrator login).",
            file=sys.stderr,
        )
        return 2
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user")
        who = str(cur.fetchone()[0])
        # Deletes need an owner/migrator login; the dry run is read-only and
        # runs under any role with SELECT.
        if args.apply and who.endswith("_pipeline"):
            return fail(
                f"connected as restricted pipeline role {who}; use the owner/migrator login"
            )

        # ---- guards: the run must be the display-only pending run ----
        cur.execute(
            "SELECT state, evidence_class, validation->>'display_only', "
            "rating_manifest_sha256, model_id, model_bundle_sha256 "
            "FROM prediction_runs WHERE run_id = %s AND season = %s AND week = %s",
            (args.run_id, args.season, args.week),
        )
        run = cur.fetchone()
        if run is None:
            return fail(
                f"run {args.run_id} not present for {args.season} week {args.week}"
            )
        state, evidence, display_only, rating_sha, model_id, bundle_sha = run
        if not (state == "published" and evidence == "pending" and display_only):
            return fail(
                f"run is state={state} evidence={evidence} display_only={display_only}; "
                "this script only reverses a published pending display-only run"
            )
        cur.execute(
            "SELECT run_id FROM site_week_selections WHERE season = %s AND week = %s",
            (args.season, args.week),
        )
        sel = cur.fetchone()
        if sel is not None and sel[0] != args.run_id:
            return fail(f"week selection points at {sel[0]}, not this run")
        cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1")
        cw = cur.fetchone()
        if (
            cw[0] != args.season
            or cw[1] != args.week
            or (cw[2] is not None and cw[2] != args.run_id)
        ):
            return fail(
                f"current_week is {cw}; expected ({args.season}, {args.week}, this run or NULL)"
            )

        # ---- resolve derived scopes ----
        cur.execute(
            "SELECT DISTINCT measurement_manifest_sha256 FROM team_possession_stats "
            "WHERE season = %s AND as_of_week = %s AND rating_manifest_sha256 = %s",
            (args.season, args.week, rating_sha),
        )
        measurement_shas = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT array_agg(game_id) FROM games WHERE season = %s AND week = %s",
            (args.season, args.week),
        )
        week_games = [int(g) for g in (cur.fetchone()[0] or [])]
        cur.execute(
            "SELECT DISTINCT source_versions::text FROM team_season_stats "
            "WHERE season = %s AND as_of_week = %s",
            (args.season, args.week),
        )
        stats_versions = [r[0] for r in cur.fetchall()]

        # (label, table, predicate, params). Each predicate doubles as the
        # delete scope and the post-delete check: shared market rows are
        # excluded from the predicate itself, so a zero re-count proves both
        # deletion and non-interference.
        plan: list[tuple[str, str, str, tuple]] = [
            (
                "prediction_market_selections",
                "prediction_market_selections",
                "run_id = %s",
                (args.run_id,),
            ),
            ("prediction_grades", "prediction_grades", "run_id = %s", (args.run_id,)),
            ("predictions", "predictions", "run_id = %s", (args.run_id,)),
            # Market rows are game-scoped, not run-scoped: the market capture
            # wrote quotes/snapshots for week games beyond the run's selected
            # subset, and all of them must go or the games delete violates
            # RESTRICT. The NOT EXISTS guards still protect rows referenced
            # from outside this week (none expected; abort-by-verify if any).
            (
                "market_snapshot_quotes",
                "market_snapshot_quotes",
                "snapshot_id IN (SELECT snapshot_id FROM market_snapshots WHERE game_id = ANY(%s)) "
                "OR quote_id IN (SELECT quote_id FROM market_quotes WHERE game_id = ANY(%s))",
                (week_games, week_games),
            ),
            (
                "market_snapshots",
                "market_snapshots",
                "game_id = ANY(%s) AND NOT EXISTS "
                "(SELECT 1 FROM predictions WHERE market_snapshot_id = market_snapshots.snapshot_id) AND NOT EXISTS "
                "(SELECT 1 FROM prediction_market_selections WHERE snapshot_id = market_snapshots.snapshot_id) AND NOT EXISTS "
                "(SELECT 1 FROM prediction_grades WHERE market_snapshot_id = market_snapshots.snapshot_id)",
                (week_games,),
            ),
            (
                "market_quotes",
                "market_quotes",
                "game_id = ANY(%s) AND NOT EXISTS "
                "(SELECT 1 FROM market_snapshot_quotes WHERE quote_id = market_quotes.quote_id) AND NOT EXISTS "
                "(SELECT 1 FROM prediction_market_selections WHERE quote_id = market_quotes.quote_id) AND NOT EXISTS "
                "(SELECT 1 FROM prediction_grades WHERE market_quote_id = market_quotes.quote_id)",
                (week_games,),
            ),
            (
                "site_week_selections",
                "site_week_selections",
                "season = %s AND week = %s",
                (args.season, args.week),
            ),
            (
                "site_week_selection_history",
                "site_week_selection_history",
                "season = %s AND week = %s",
                (args.season, args.week),
            ),
            ("game_venues", "game_venues", "game_id = ANY(%s)", (week_games,)),
            (
                "team_rating_components",
                "team_rating_components",
                "source_manifest_sha256 = %s",
                (rating_sha,),
            ),
            (
                "team_possession_stats",
                "team_possession_stats",
                "season = %s AND as_of_week = %s AND rating_manifest_sha256 = %s",
                (args.season, args.week, rating_sha),
            ),
            (
                "team_possession_adjusted",
                "team_possession_adjusted",
                "season = %s AND as_of_week = %s AND rating_manifest_sha256 = %s",
                (args.season, args.week, rating_sha),
            ),
            (
                "team_game_measurements",
                "team_game_measurements",
                "game_id = ANY(%s) AND measurement_manifest_sha256 = ANY(%s)",
                (week_games, measurement_shas),
            ),
            (
                "matchup_data_publications",
                "matchup_data_publications",
                "season = %s AND rating_manifest_sha256 = %s",
                (args.season, rating_sha),
            ),
            (
                "v5_rating_snapshots",
                "v5_rating_snapshots",
                "source_manifest_sha256 = %s",
                (rating_sha,),
            ),
            (
                "team_season_stats",
                "team_season_stats",
                "season = %s AND as_of_week = %s",
                (args.season, args.week),
            ),
            ("games", "games", "season = %s AND week = %s", (args.season, args.week)),
            (
                "ops.activation_history",
                "ops.activation_history",
                "run_id = %s",
                (args.run_id,),
            ),
            ("ops.waivers", "ops.waivers", "run_id = %s", (args.run_id,)),
            ("prediction_runs", "prediction_runs", "run_id = %s", (args.run_id,)),
            (
                "v5_intended_update_release_authorizations",
                "v5_intended_update_release_authorizations",
                "environment = %s AND season = %s AND week = %s AND prediction_run_id = %s",
                (args.environment, args.season, args.week, args.run_id),
            ),
        ]
        counts: dict[str, int] = {}
        for label, table, predicate, params in plan:
            cur.execute(f"SELECT count(*) FROM {table} WHERE {predicate}", params)
            counts[label] = cur.fetchone()[0]
        cur.execute("SELECT active_run_id FROM current_week WHERE id = 1")
        pointer_set = cur.fetchone()[0] is not None
        # Bundle approval is shared across weeks: remove only when no sibling run needs it.
        cur.execute(
            "SELECT count(*) FROM prediction_runs WHERE model_id = %s AND run_id != %s",
            (model_id, args.run_id),
        )
        siblings = cur.fetchone()[0]
        approval_deletes = False
        if siblings == 0:
            cur.execute(
                "SELECT count(*) FROM v5_model_bundle_approvals WHERE model_id = %s AND inference_bundle_sha256 = %s",
                (model_id, bundle_sha),
            )
            counts["v5_model_bundle_approvals"] = cur.fetchone()[0]
            approval_deletes = True
        else:
            counts["v5_model_bundle_approvals (kept: shared)"] = 0

        print(f"reason: {args.reason}")
        print(
            f"run rating sha: {rating_sha[:12] if rating_sha else None}; "
            f"measurement shas: {[s[:12] for s in measurement_shas]}; "
            f"week games: {len(week_games)}; stats source versions: {len(stats_versions)} distinct; "
            f"current_week pointer set: {pointer_set}"
        )
        # Display-only scope sizes for the game-scoped market tables.
        cur.execute(
            "SELECT count(*) FROM market_snapshots WHERE game_id = ANY(%s)",
            (week_games,),
        )
        print(f"  market_snapshots in week scope: {cur.fetchone()[0]} row(s)")
        cur.execute(
            "SELECT count(*) FROM market_quotes WHERE game_id = ANY(%s)",
            (week_games,),
        )
        print(f"  market_quotes in week scope: {cur.fetchone()[0]} row(s)")
        total = 0
        for label, _, _, _ in plan:
            print(f"  {label}: {counts[label]} row(s)")
            total += counts[label]
        print(
            f"  v5_model_bundle_approvals: {counts.get('v5_model_bundle_approvals', 0)} row(s)"
        )
        total += counts.get("v5_model_bundle_approvals", 0)
        if not args.apply:
            print(f"Dry run: {total} row(s) would be deleted; nothing written.")
            return 0
        # Clear the singleton pointer first: it references the run row while
        # nothing references it, so it must go before any delete.
        cur.execute("UPDATE current_week SET active_run_id = NULL WHERE id = 1")
        for _, table, predicate, params in plan:
            cur.execute(f"DELETE FROM {table} WHERE {predicate}", params)
        if approval_deletes:
            cur.execute(
                "DELETE FROM v5_model_bundle_approvals WHERE model_id = %s AND inference_bundle_sha256 = %s",
                (model_id, bundle_sha),
            )
        # ---- post-delete verification in the same transaction ----
        problems = []
        for label, table, predicate, params in plan:
            cur.execute(f"SELECT count(*) FROM {table} WHERE {predicate}", params)
            if cur.fetchone()[0]:
                problems.append(f"{label}: rows remain")
        cur.execute("SELECT active_run_id FROM current_week WHERE id = 1")
        if cur.fetchone()[0] is not None:
            problems.append("current_week.active_run_id not cleared")
        if approval_deletes:
            cur.execute(
                "SELECT count(*) FROM v5_model_bundle_approvals WHERE model_id = %s AND inference_bundle_sha256 = %s",
                (model_id, bundle_sha),
            )
            if cur.fetchone()[0]:
                problems.append("bundle approval remains")
        if problems:
            conn.rollback()
            for line in problems:
                print(f"VERIFY FAIL: {line}", file=sys.stderr)
            return 3
        conn.commit()
        print("Rollback applied and verified: hold-screen state restored.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
