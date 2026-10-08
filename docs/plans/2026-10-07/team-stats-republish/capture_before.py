"""Read-only: confirm the pinned Silver inputs and dump team_season_stats (the rollback source)."""

import gzip
import hashlib
import json
import os
import sys

import psycopg

PINS = {
    "games": "31a337df6cf49f1578457ec6",
    "byplay": "443019a9a7b6a2454a4af4ac",
    "drives": "862815e2974a7fd6226841c1",
    "teams": "590e986596436aa001ff77b7",
    "game_outcomes": "d9a37cf473c63d2acc9f29cc",
}
env, out_prefix = sys.argv[1], sys.argv[2]
url = os.environ["DATABASE_URL" if env == "production" else "PREVIEW_DATABASE_URL"]

with psycopg.connect(url, options="-c default_transaction_read_only=on") as conn:
    cur = conn.cursor()
    cur.execute("SELECT current_user, current_setting('transaction_read_only')")
    identity = list(cur.fetchone())
    pinned = {}
    for dataset, version in PINS.items():
        cur.execute(
            "SELECT version_id, state, tier, content_sha, as_of, partitions "
            "FROM catalog.dataset_versions WHERE dataset = %s AND version_id = %s",
            (dataset, version),
        )
        rows = cur.fetchall()
        pinned[dataset] = [
            {
                "version_id": r[0],
                "state": r[1],
                "tier": r[2],
                "content_sha": r[3],
                "as_of": str(r[4]),
                "partitions": r[5],
            }
            for r in rows
        ]
    cur.execute(
        "SELECT season, as_of_week, team, role, metric, value::float8, n, games, rank, "
        "cohort_size, source_versions::text, updated_at::text "
        "FROM team_season_stats ORDER BY season, as_of_week, team, role, metric"
    )
    cols = [d.name for d in cur.description]
    rows = [list(r) for r in cur.fetchall()]

payload = {"environment": env, "columns": cols, "rows": rows}
raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
digest = hashlib.sha256(raw).hexdigest()
with gzip.open(f"{out_prefix}.json.gz", "wb", compresslevel=9) as handle:
    handle.write(raw)
summary = {
    "environment": env,
    "identity": identity,
    "row_count": len(rows),
    "payload_sha256": digest,
    "pinned_inputs": pinned,
    "all_pins_validated_exactly_once": all(
        len(v) == 1 and v[0]["state"] == "validated" and v[0]["tier"] == "silver"
        for v in pinned.values()
    ),
}
print(json.dumps(summary, indent=1))
