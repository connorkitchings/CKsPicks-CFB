import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.game_finals import fetch_existing, plan_finals

load_dotenv('.env')
environment = os.environ['CFB_ARTIFACT_ENV']
url = os.environ['PREVIEW_DATABASE_URL' if environment == 'preview' else 'DATABASE_URL']
evidence = Path('docs/plans/2026-10-11/week6-closeout-evidence/20261011T150908Z')
output = evidence / f'{environment}-preflight-r2.json'
assert not output.exists()
assert os.environ.get('CFB_STORAGE_BACKEND') == 'r2'
source = json.loads((evidence / 'cfbd-games.json').read_bytes())
source_ids = {int(row['id']) for row in source}
pin = json.loads(Path('conf/rebuild/silver_2026_parents_w5_v1.json').read_text())['game_outcomes']
storage = get_storage(environment='preview')
outcomes = read_dataset(storage, DatasetRef(**{k:pin[k] for k in ('dataset','version_id','schema_version','content_sha','uri')}))
report = {'environment':environment, 'captured_at':datetime.now(timezone.utc).isoformat(), 'source_observation_sha256':hashlib.sha256((evidence / 'observation.json').read_bytes()).hexdigest()}
queries = {
    'identity': 'SELECT session_user,current_user,current_database(),current_setting(\'transaction_read_only\') AS read_only,current_setting(\'transaction_isolation\') AS isolation',
    'current_week': 'SELECT season,week,active_run_id FROM current_week',
    'selections': 'SELECT sws.week,sws.run_id,pr.state,pr.evidence_class,pr.frozen_at FROM site_week_selections sws JOIN prediction_runs pr USING(run_id) WHERE sws.season=2026 ORDER BY sws.week',
    'schedule': 'SELECT game_id,week,home_team,away_team,start_date AS kickoff FROM games WHERE season=2026 AND week=6 ORDER BY game_id',
    'grades': 'SELECT sws.week,pg.target,pg.result,count(*) FROM site_week_selections sws JOIN prediction_grades pg USING(run_id) WHERE sws.season=2026 GROUP BY sws.week,pg.target,pg.result ORDER BY 1,2,3',
    'prospective_records': 'SELECT season,week,run_id,freeze_receipt_uri,freeze_receipt_sha256,frozen_at,first_kickoff_utc,decision_ref FROM prospective_week_records WHERE season=2026 ORDER BY week',
    'migrations': 'SELECT version,name,checksum FROM schema_migrations ORDER BY version',
    'leases': 'SELECT pipeline_run_id,command,season,week,state,lease_owner,lease_expires_at FROM ops.pipeline_runs WHERE lease_expires_at > NOW() ORDER BY started_at',
    'bundle_approvals': 'SELECT approval_id,first_live_week FROM v5_model_bundle_approvals ORDER BY approval_id',
    'grants': "SELECT table_name,privilege_type FROM information_schema.role_table_grants WHERE grantee=current_user AND table_schema='public' AND table_name IN ('games','game_results','predictions','prediction_grades','prediction_market_selections','system_stats','site_week_selections','current_week') ORDER BY 1,2",
    'games_captures': "SELECT capture_id,captured_at,entity,uri,row_count,content_sha,object_sha,state FROM catalog.source_captures WHERE entity='games' AND captured_at >= '2026-10-10T00:00:00Z' ORDER BY captured_at",
    'recent_outcomes': "SELECT version_id,as_of,uri,row_count,content_sha,state FROM catalog.dataset_versions WHERE dataset='game_outcomes' AND as_of >= '2026-10-10T00:00:00Z' ORDER BY as_of",
}
with psycopg.connect(url,connect_timeout=20) as connection:
    connection.execute('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    for name,query in queries.items():
        cursor = connection.execute(query)
        fields = [field.name for field in cursor.description]
        report[name] = [dict(zip(fields,row)) for row in cursor.fetchall()]
    with connection.cursor() as cursor:
        parity = plan_finals(outcomes,fetch_existing(cursor,season=2026,week=5),season=2026,week=5)
    report['week5_parity'] = {'pin':pin, **parity.summary()}
    report['week6_counts'] = connection.execute("SELECT (SELECT count(*) FROM predictions p JOIN site_week_selections sws USING(run_id) WHERE sws.season=2026 AND sws.week=6),(SELECT count(*) FROM prediction_grades pg JOIN site_week_selections sws USING(run_id) WHERE sws.season=2026 AND sws.week=6),(SELECT count(*) FROM game_results gr JOIN games g USING(game_id) WHERE g.season=2026 AND g.week=6)").fetchone()
    connection.rollback()
db_ids = {int(row['game_id']) for row in report['schedule']}
report['schedule_reconciliation'] = {'source_games':len(source_ids),'database_games':len(db_ids),'source_only':sorted(source_ids-db_ids),'database_only':sorted(db_ids-source_ids)}
report['schedule_field_differences'] = []
db_rows = {int(row['game_id']):row for row in report['schedule']}
for row in source:
    db = db_rows.get(int(row['id']))
    if not db:
        continue
    for source_key,db_key in [('homeTeam','home_team'),('awayTeam','away_team')]:
        if row[source_key] != db[db_key]:
            report['schedule_field_differences'].append({'game_id':row['id'],'field':db_key,'source':row[source_key],'database':db[db_key]})
    if datetime.fromisoformat(row['startDate'].replace('Z','+00:00')) != db['kickoff']:
        report['schedule_field_differences'].append({'game_id':row['id'],'field':'kickoff','source':row['startDate'],'database':str(db['kickoff'])})
report['preflight_status'] = 'blocked_schedule_drift' if report['schedule_field_differences'] else 'passed_read_only_checks'
expected_role = 'cks_preview_pipeline' if environment == 'preview' else 'cks_prod_pipeline'
identity = report['identity'][0]
assert identity['session_user'] == identity['current_user'] == expected_role
assert identity['read_only'] == 'on' and identity['isolation'] == 'repeatable read'
with output.open('x') as handle:
    json.dump(report,handle,indent=2,default=str)
    handle.write('\n')
print(json.dumps({'environment':environment,'captured_at':report['captured_at'],'identity':report['identity'],'week5_parity':parity.summary(),'week6_counts_predictions_grades_finals':report['week6_counts'],'schedule_reconciliation':report['schedule_reconciliation'],'schedule_field_differences':report['schedule_field_differences'],'earlier_games_captures':len(report['games_captures']),'recent_outcomes':len(report['recent_outcomes']),'active_leases':len(report['leases']),'evidence':str(output),'raw_sha256':hashlib.sha256(output.read_bytes()).hexdigest()},indent=2,default=str))
assert not parity.inserts and not parity.conflicts and not parity.missing_outcome and not parity.not_final
assert source_ids == db_ids and not report['schedule_field_differences']
