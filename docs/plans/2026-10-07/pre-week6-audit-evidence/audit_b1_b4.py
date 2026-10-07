"""Read-only pre-Week-6 audit (B1-B4). Never prints or stores the URL."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import psycopg

env = sys.argv[1]
url = os.environ["DATABASE_URL"] if env == "production" else os.environ["PREVIEW_DATABASE_URL"]

ROLLBACK = [f"2026w{w}-v5replay-bestquote-20260926-r3" for w in range(5)] + ["2026w5-5d436e58c072"]
PROSPECTIVE_W5 = "2026w5-v5repair-20260929-p2"


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


out = {"environment": env, "captured_at": datetime.now(timezone.utc).isoformat()}
with psycopg.connect(url, options="-c default_transaction_read_only=on") as conn:
    cur = conn.cursor()

    def q(sql, params=None):
        cur.execute(sql, params)
        return cur.fetchall()

    out["identity"] = {"user": q("SELECT current_user")[0][0],
                       "read_only": q("SELECT current_setting('transaction_read_only')")[0][0]}

    # B1 serving state
    out["current_week"] = [list(r) for r in q("SELECT season, week, active_run_id FROM current_week")]
    sel = q("SELECT season, week, run_id FROM site_week_selections ORDER BY season, week")
    out["site_week_selections"] = [list(r) for r in sel]
    out["site_week_selections_sha256"] = digest(sel)
    runs = q(
        "SELECT run_id, state, evidence_class, expected_games, predicted_games, lined_games, "
        "frozen_at, scored_at FROM prediction_runs WHERE run_id = ANY(%s) OR run_id = %s ORDER BY run_id",
        (ROLLBACK, PROSPECTIVE_W5),
    )
    out["rollback_and_w5_runs"] = [list(r) for r in runs]
    out["rollback_present"] = sorted(set(ROLLBACK) - {r[0] for r in runs}) == []
    out["games_by_week_2026"] = [list(r) for r in q(
        "SELECT week, count(*), min(start_date), max(start_date) FROM games WHERE season=2026 GROUP BY week ORDER BY week")]

    # B2 week-5 grades
    grades = q(
        "SELECT target, result, count(*) FROM prediction_grades WHERE run_id=%s GROUP BY 1,2 ORDER BY 1,2",
        (PROSPECTIVE_W5,),
    )
    out["w5_grades_by_target_result"] = [list(r) for r in grades]
    rowhash = q(
        "SELECT game_id, target, side, result, profit_units, grading_version, market_snapshot_id "
        "FROM prediction_grades WHERE run_id=%s ORDER BY game_id, target",
        (PROSPECTIVE_W5,),
    )
    out["w5_grade_rows"] = len(rowhash)
    out["w5_grade_rows_sha256"] = digest(rowhash)
    out["w5_predictions"] = q("SELECT count(*) FROM predictions WHERE run_id=%s", (PROSPECTIVE_W5,))[0][0]
    pred = q(
        "SELECT game_id, predicted_spread, predicted_total, spread_lean, total_lean "
        "FROM predictions WHERE run_id=%s ORDER BY game_id",
        (PROSPECTIVE_W5,),
    )
    out["w5_predictions_sha256"] = digest(pred)
    out["w5_results_scored"] = q(
        "SELECT count(*) FROM game_results r JOIN games g USING (game_id) WHERE g.season=2026 AND g.week=5")[0][0]

    # B3 prospective registrations
    out["prospective_week_records"] = [
        [str(c) for c in r] for r in q(
            "SELECT season, week, run_id, freeze_receipt_uri, freeze_receipt_sha256, frozen_at, "
            "first_kickoff_utc, decision_ref FROM prospective_week_records ORDER BY season, week")]

    # B4 schema and grants
    tbls = q("SELECT table_schema, table_name FROM information_schema.tables "
             "WHERE table_name ILIKE '%migration%' ORDER BY 1,2")
    out["migration_tables"] = [list(r) for r in tbls]
    roles = [r[0] for r in q(
        "SELECT rolname FROM pg_roles WHERE rolname ~ '^(cks_|neon)' ORDER BY 1")]
    out["roles"] = roles
    checks = [
        ("public.prospective_week_records", "SELECT"), ("public.prospective_week_records", "INSERT"),
        ("public.market_quotes", "SELECT"), ("ops.v5_release_revocations", "SELECT"),
        ("ops.v5_release_revocations", "INSERT"),
    ]
    grants = {}
    for role in roles:
        if role in ("cks_release_authorizer",) or role.startswith("cks_"):
            grants[role] = {f"{t}:{p}": q("SELECT has_table_privilege(%s, %s, %s)", (role, t, p))[0][0]
                            for t, p in checks}
    out["grants"] = grants
    out["triggers_prospective"] = [r[0] for r in q(
        "SELECT tgname FROM pg_trigger WHERE tgrelid='public.prospective_week_records'::regclass AND NOT tgisinternal")]

print(json.dumps(out, indent=2, default=str))
