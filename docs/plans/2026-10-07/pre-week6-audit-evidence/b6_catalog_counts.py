import json, os, psycopg
url=os.environ["PREVIEW_DATABASE_URL"]
with psycopg.connect(url, options="-c default_transaction_read_only=on") as c:
    cur=c.cursor()
    cur.execute("SELECT dataset, count(*), sum(row_count)::bigint FROM catalog.dataset_versions WHERE dataset LIKE 'reconstruction%' GROUP BY 1 ORDER BY 1")
    rows=[list(r) for r in cur.fetchall()]
    cur.execute("SELECT count(*) FROM catalog.dataset_versions")
    total=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM catalog.dataset_dependencies d JOIN catalog.dataset_versions v ON v.version_id=d.child_version_id WHERE v.dataset LIKE 'reconstruction%'")
    edges=cur.fetchone()[0]
print(json.dumps({"reconstruction_datasets":rows,"catalog_total_versions":total,"reconstruction_dependency_edges":edges}))
