import json, os, sys, hashlib
import psycopg
env = sys.argv[1]
url = os.environ["DATABASE_URL"] if env == "production" else os.environ["PREVIEW_DATABASE_URL"]
out = {"environment": env}
with psycopg.connect(url, options="-c default_transaction_read_only=on") as conn:
    cur = conn.cursor()
    def q(s, p=None):
        cur.execute(s, p); return cur.fetchall()
    cols = [r[0] for r in q("SELECT column_name FROM information_schema.columns WHERE table_name='schema_migrations' ORDER BY ordinal_position")]
    out["schema_migrations_columns"] = cols
    rows = q(f"SELECT {', '.join(cols[:2])} FROM schema_migrations ORDER BY 1")
    out["migrations"] = [[str(c)[:40] for c in r] for r in rows]
    out["migration_count"] = len(rows)
    out["game_venues"] = q("SELECT count(*), count(*) FILTER (WHERE city IS NOT NULL AND city<>'') FROM game_venues")[0]
    tcols = [r[0] for r in q("SELECT column_name FROM information_schema.columns WHERE table_name='team_season_stats' ORDER BY ordinal_position")]
    out["team_season_stats_columns"] = tcols
    wk = "as_of_week" if "as_of_week" in tcols else ("week" if "week" in tcols else None)
    if wk:
        out["team_season_stats_by_week"] = [list(r) for r in q(f"SELECT {wk}, count(*) FROM team_season_stats GROUP BY 1 ORDER BY 1")]
    out["games_w5_vs_lines"] = q("SELECT count(*), count(home_team_spread_line), count(total_line) FROM games WHERE season=2026 AND week=5")[0]
print(json.dumps(out, indent=1, default=str))
