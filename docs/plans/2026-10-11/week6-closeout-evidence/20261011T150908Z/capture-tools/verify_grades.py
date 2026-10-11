import gzip, hashlib, json, os, collections
from pathlib import Path
import psycopg
from dotenv import load_dotenv
load_dotenv('.env')
env = os.environ['CFB_ARTIFACT_ENV']
url = os.environ['PREVIEW_DATABASE_URL' if env == 'preview' else 'DATABASE_URL']
base = Path('artifacts/backups/week6-closeout-20261011') / env
def load(n): return json.loads(gzip.decompress((base / f'{n}.json.gz').read_bytes()))
pre = {n: load(n) for n in ('game_results','prediction_grades','prediction_market_selections','system_stats','site_week_selections_and_runs')}
Q = {
 'game_results': "SELECT row_to_json(t) FROM (SELECT gr.* FROM game_results gr JOIN games g USING(game_id) WHERE g.season=2026 ORDER BY gr.game_id) t",
 'prediction_grades': "SELECT row_to_json(t) FROM (SELECT pg.* FROM prediction_grades pg JOIN games g USING(game_id) WHERE g.season=2026 ORDER BY pg.run_id, pg.game_id, pg.target) t",
 'prediction_market_selections': "SELECT row_to_json(t) FROM (SELECT s.* FROM prediction_market_selections s JOIN games g USING(game_id) WHERE g.season=2026 ORDER BY s.run_id, s.game_id, s.target) t",
 'system_stats': "SELECT row_to_json(t) FROM (SELECT * FROM system_stats WHERE season=2026) t",
 'site_week_selections_and_runs': "SELECT row_to_json(t) FROM (SELECT sws.*, pr.state, pr.evidence_class, pr.frozen_at FROM site_week_selections sws JOIN prediction_runs pr USING(run_id) WHERE sws.season=2026 ORDER BY sws.week) t",
}
rt = lambda r: json.loads(json.dumps(r, default=str))
with psycopg.connect(url) as c:
    c.execute('BEGIN READ ONLY')
    post = {n: [rt(r[0]) for r in c.execute(q).fetchall()] for n, q in Q.items()}
    wk = {r[0]: r[1] for r in c.execute("SELECT game_id, week FROM games WHERE season=2026")}
    runrow = c.execute("SELECT run_id,state,evidence_class,frozen_at FROM prediction_runs pr JOIN site_week_selections s USING(run_id) WHERE s.season=2026 AND s.week=6").fetchone()
    c.rollback()
print('env', env, 'week6 run', runrow)
key = lambda r: (r['run_id'], r['game_id'], r['target'])
for n in ('prediction_market_selections','system_stats','site_week_selections_and_runs'):
    strip=lambda L:[{k:v for k,v in r.items() if k!='updated_at'} for r in L]
    print(n, 'IDENTICAL to pre-write' if post[n] == pre[n] else ('identical except updated_at' if strip(post[n])==strip(pre[n]) else 'CHANGED'), (post[n] if n=='system_stats' else ''))
pre_g = {key(r): r for r in pre['prediction_grades']}; post_g = {key(r): r for r in post['prediction_grades']}
print('grades: pre', len(pre_g), 'post', len(post_g), 'all pre rows unchanged:', all(post_g.get(k) == v for k, v in pre_g.items()))
new = [post_g[k] for k in post_g if k not in pre_g]
print('new grade rows', len(new), 'weeks', collections.Counter(wk[r['game_id']] for r in new), 'runs', set(r['run_id'] for r in new))
pre_r = {r['game_id']: r for r in pre['game_results']}; post_r = {r['game_id']: r for r in post['game_results']}
newres = [post_r[g] for g in post_r if g not in pre_r]
print('game_results: pre', len(pre_r), 'post', len(post_r), 'pre unchanged:', all(post_r[g] == v for g, v in pre_r.items()), 'new', len(newres), 'new weeks', collections.Counter(wk[r['game_id']] for r in newres))
sel = {key(r): r for r in post['prediction_market_selections']}
bad = []; tally = collections.Counter()
for g in new:
    s = sel[key(g)]; r = post_r[g['game_id']]
    margin = r['home_points'] - r['away_points']; total = r['home_points'] + r['away_points']
    if g['target'] == 'spread':
        v = margin + s['point']; res = 'push' if v == 0 else ('win' if (v > 0) == (s['side'] == 'home') else 'loss')
    else:
        v = total - s['point']; res = 'push' if v == 0 else ('win' if (v > 0) == (s['side'] == 'over') else 'loss')
    if str(g['result']).lower() != res or g['side'] != s['side'] or g['market_quote_id'] != s['quote_id'] or g['grading_version'] != s['policy_version']: bad.append((key(g), g['result'], res, g['side'], s['side'], g['grading_version'], s['policy_version']))
    tally[(g['target'], res)] += 1
print('independent recompute mismatches:', len(bad), bad[:3]); print('labels', collections.Counter(g['grading_version'] for g in new))
print('week6 record (spread W-L-P, total W-L-P):', [tally[('spread', x)] for x in ('win','loss','push')], [tally[('total', x)] for x in ('win','loss','push')])
