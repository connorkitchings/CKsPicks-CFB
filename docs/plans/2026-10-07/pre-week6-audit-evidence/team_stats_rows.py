import json, os, sys
import psycopg
env=sys.argv[1]
url=os.environ["DATABASE_URL"] if env=="production" else os.environ["PREVIEW_DATABASE_URL"]
with psycopg.connect(url, options="-c default_transaction_read_only=on") as c:
    cur=c.cursor()
    cur.execute("SELECT as_of_week, team, role, metric, value::float8, n, games, rank FROM team_season_stats ORDER BY 1,2,3,4")
    rows=[[str(x) if i<4 else x for i,x in enumerate(r)] for r in cur.fetchall()]
json.dump(rows, open(sys.argv[2],"w"))
print(env, len(rows))
