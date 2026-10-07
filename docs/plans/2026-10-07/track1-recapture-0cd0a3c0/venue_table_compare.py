"""Read-only: compare Production game_venues now with the 12:56Z capture's before and proposed rows."""

import json
import os

import psycopg

cap = json.load(open("docs/plans/2026-10-07/track1-evidence/production-capture.json"))
BUSINESS = [
    "venue_id",
    "venue_name",
    "city",
    "state",
    "country_code",
    "timezone",
    "neutral_site",
]
with psycopg.connect(
    os.environ["DATABASE_URL"], options="-c default_transaction_read_only=on"
) as c:
    cur = c.cursor()
    cur.execute(
        f"SELECT game_id, {', '.join(BUSINESS)} FROM game_venues ORDER BY game_id"
    )
    now = {int(r[0]): dict(zip(BUSINESS, r[1:])) for r in cur.fetchall()}


def norm(rows):
    return {int(r["game_id"]): {k: r.get(k) for k in BUSINESS} for r in rows}


before, proposed = norm(cap["game_venues"]["rows"]), norm(cap["proposed_rows"])
print(
    json.dumps(
        {
            "rows_now": len(now),
            "now_equals_captured_before": now == before,
            "now_equals_proposed": now == proposed,
            "captured_before_equals_proposed": before == proposed,
            "game_ids_only_now": sorted(set(now) - set(before))[:5],
            "differing_rows_now_vs_proposed": sum(
                1 for g in now if now.get(g) != proposed.get(g)
            ),
        },
        indent=1,
    )
)
