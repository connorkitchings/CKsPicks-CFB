import json
import os
import sys

import psycopg

env = sys.argv[1]
url = (
    os.environ["DATABASE_URL"]
    if env == "production"
    else os.environ["PREVIEW_DATABASE_URL"]
)
R = "2026w4-v5replay-bestquote-20260926-r3"
with psycopg.connect(url, options="-c default_transaction_read_only=on") as c:
    cur = c.cursor()

    def q(s, p=None):
        cur.execute(s, p)
        return cur.fetchall()

    out = {"env": env}
    out["run"] = [
        str(x)
        for x in q(
            "SELECT state, evidence_class, published_at, frozen_at, scored_at, artifact_sha256 FROM prediction_runs WHERE run_id=%s",
            (R,),
        )[0]
    ]
    out["predictions"] = q("SELECT count(*) FROM predictions WHERE run_id=%s", (R,))[0][
        0
    ]
    out["grades"] = [
        list(r)
        for r in q(
            "SELECT target, result, count(*) FROM prediction_grades WHERE run_id=%s GROUP BY 1,2 ORDER BY 1,2",
            (R,),
        )
    ]
    out["w4_results_scored"] = q(
        "SELECT count(*) FROM game_results r JOIN games g USING (game_id) WHERE g.season=2026 AND g.week=4"
    )[0][0]
    out["selected_in_site_week"] = q(
        "SELECT count(*) FROM site_week_selections WHERE run_id=%s", (R,)
    )[0][0]
    out["ops_history"] = (
        [
            [str(x) for x in r]
            for r in q(
                "SELECT action, environment, activated_at FROM ops.activation_history WHERE run_id=%s ORDER BY 3",
                (R,),
            )
        ]
        if q("SELECT to_regclass('ops.activation_history') IS NOT NULL")[0][0]
        else "no table"
    )
print(json.dumps(out, indent=1, default=str))
