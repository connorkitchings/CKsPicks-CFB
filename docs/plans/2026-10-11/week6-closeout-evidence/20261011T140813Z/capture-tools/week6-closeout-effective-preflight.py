import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage

load_dotenv('.env')
environment = os.environ['CFB_ARTIFACT_ENV']
url = os.environ['PREVIEW_DATABASE_URL' if environment == 'preview' else 'DATABASE_URL']
base = Path('docs/plans/2026-10-11/week6-closeout-evidence/20261011T140813Z')
result = {'environment':environment,'captured_at':datetime.now(timezone.utc).isoformat()}
with psycopg.connect(url,connect_timeout=20) as connection:
    connection.execute('BEGIN READ ONLY')
    rows = connection.execute("SELECT name, has_table_privilege(current_user,name,'SELECT'),has_table_privilege(current_user,name,'INSERT'),has_table_privilege(current_user,name,'UPDATE'),has_table_privilege(current_user,name,'DELETE') FROM unnest(ARRAY['games','game_results','predictions','prediction_grades','prediction_market_selections','system_stats','site_week_selections','current_week']) AS name").fetchall()
    result['effective_grants'] = [dict(zip(('table','select','insert','update','delete'),row)) for row in rows]
    result['database_time'] = str(connection.execute('SELECT now()').fetchone()[0])
    connection.rollback()
storage = get_storage(environment='preview')
uri = 'artifacts/preview/pipeline-runs/stage1-w5-ingest-20261007-r2/game_outcomes_ref.json'
raw = storage.read_bytes(uri)
ref = json.loads(raw)
pin = json.loads(Path('conf/rebuild/silver_2026_parents_w5_v1.json').read_text())['game_outcomes']
assert all(ref[k] == pin[k] for k in ('dataset','version_id','schema_version','content_sha','uri'))
result['verified_week5_ref'] = {'uri':uri,'raw_sha256':hashlib.sha256(raw).hexdigest(),'dataset_ref':ref}
path = base / f'{environment}-effective-grants-and-ref.json'
with path.open('x') as handle:
    json.dump(result,handle,indent=2)
    handle.write('\n')
print(json.dumps(result,indent=2))
