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
R = "2026w5-v5repair-20260929-p2"
with psycopg.connect(url, options="-c default_transaction_read_only=on") as c:
    cur = c.cursor()
    cur.execute(
        """SELECT s.game_id, s.target, s.side AS selection_side, g.side AS grade_side, g.result
                   FROM prediction_market_selections s JOIN prediction_grades g
                     ON g.run_id=s.run_id AND g.game_id=s.game_id AND g.target=s.target
                   WHERE s.run_id=%s AND s.side <> g.side ORDER BY 1,2""",
        (R,),
    )
    diff = [list(r) for r in cur.fetchall()]
    cur.execute(
        "SELECT count(*) FROM prediction_market_selections WHERE run_id=%s", (R,)
    )
    nsel = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FROM predictions WHERE run_id=%s AND spread_lean IS NULL", (R,)
    )
    nsl = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FROM predictions WHERE run_id=%s AND total_lean IS NULL", (R,)
    )
    ntl = cur.fetchone()[0]
print(
    json.dumps(
        {
            "env": env,
            "selections": nsel,
            "side_disagreements": diff,
            "null_spread_lean": nsl,
            "null_total_lean": ntl,
        }
    )
)
