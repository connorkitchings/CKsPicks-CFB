import gzip, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from dotenv import load_dotenv
load_dotenv('.env')
env = os.environ['CFB_ARTIFACT_ENV']
url = os.environ['PREVIEW_DATABASE_URL' if env == 'preview' else 'DATABASE_URL']
out = Path('artifacts/backups/week6-closeout-20261011') / env
out.mkdir(parents=True, exist_ok=False)
Q = {
 'game_results': "SELECT row_to_json(t) FROM (SELECT gr.* FROM game_results gr JOIN games g USING(game_id) WHERE g.season=2026 ORDER BY gr.game_id) t",
 'prediction_grades': "SELECT row_to_json(t) FROM (SELECT pg.* FROM prediction_grades pg JOIN games g USING(game_id) WHERE g.season=2026 ORDER BY pg.run_id, pg.game_id, pg.target) t",
 'prediction_market_selections': "SELECT row_to_json(t) FROM (SELECT s.* FROM prediction_market_selections s JOIN games g USING(game_id) WHERE g.season=2026 ORDER BY s.run_id, s.game_id, s.target) t",
 'system_stats': "SELECT row_to_json(t) FROM (SELECT * FROM system_stats WHERE season=2026) t",
 'site_week_selections_and_runs': "SELECT row_to_json(t) FROM (SELECT sws.*, pr.state, pr.evidence_class, pr.frozen_at FROM site_week_selections sws JOIN prediction_runs pr USING(run_id) WHERE sws.season=2026 ORDER BY sws.week) t",
}
manifest = {'environment': env, 'captured_at': datetime.now(timezone.utc).isoformat(), 'files': {}}
with psycopg.connect(url, connect_timeout=20) as c:
    c.execute('BEGIN READ ONLY ISOLATION LEVEL REPEATABLE READ')
    who = c.execute('SELECT session_user, current_user, current_setting(\'transaction_read_only\')').fetchone()
    manifest['identity'] = list(who)
    for name, q in Q.items():
        rows = [r[0] for r in c.execute(q).fetchall()]
        raw = json.dumps(rows, sort_keys=True, default=str, separators=(',', ':')).encode()
        path = out / f'{name}.json.gz'
        with path.open('xb') as h:
            h.write(gzip.compress(raw, mtime=0))
        back = gzip.decompress(path.read_bytes())
        assert back == raw
        manifest['files'][name] = {'rows': len(rows), 'payload_sha256': hashlib.sha256(raw).hexdigest(), 'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    c.rollback()
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
