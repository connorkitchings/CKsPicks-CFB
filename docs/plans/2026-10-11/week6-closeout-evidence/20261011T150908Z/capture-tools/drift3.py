import json
from pathlib import Path
import pandas as pd
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
st = get_storage(environment='preview')
run='artifacts/preview/pipeline-runs/w6-closeout-ingest-20261011-r2'
pins={p['dataset']:p for p in json.loads(Path('conf/rebuild/silver_2026_parents_w5_v1.json').read_text())['parents']}
def ds(ref): return read_dataset(st, DatasetRef(**{k:ref[k] for k in ('dataset','version_id','schema_version','content_sha','uri')}))
o_new=ds(json.loads(st.read_bytes(f'{run}/game_outcomes_ref.json'))); o_old=ds(json.loads(Path('conf/rebuild/silver_2026_parents_w5_v1.json').read_text())['game_outcomes'])
print(o_new.columns.tolist())
k='game_id'
cfbd={r['id']:(r['homePoints'],r['awayPoints']) for r in json.loads(Path('docs/plans/2026-10-11/week6-closeout-evidence/20261011T150908Z/normalized-finals.json').read_bytes())}
n=o_new.set_index(k)
miss=[g for g in cfbd if g not in n.index]
bad=[g for g,(h,a) in cfbd.items() if g in n.index and (n.loc[g,'home_points'],n.loc[g,'away_points'])!=(h,a)]
print('week6 finals in outcomes:',len(cfbd)-len(miss),'/58 missing',miss,'score mismatches vs CFBD',bad)
common=o_old[k].isin(o_new[k]); print('old outcomes rows',len(o_old),'in new',int(common.sum()))
a=o_old.set_index(k).sort_index(); b=n.loc[a.index].sort_index()
cols=[c for c in a.columns if not c.startswith('__') and c in b.columns]
print('weeks0-5 outcome business cols identical:', all(((a[c]==b[c])|(a[c].isna()&b[c].isna())).all() for c in cols))
p=ds(json.loads(st.read_bytes(f'{run}/plays_ref.json')))
w6=p[p.week==6]; dup=w6.duplicated(['game_id','play_id']).sum()
print('week6 plays',len(w6),'games',w6.game_id.nunique(),'duplicate (game_id,play_id):',int(dup))
done=a[a['completed'].fillna(False).astype(bool)]
print('old completed rows',len(done))
for c in cols:
    ne=~((done[c]==b.loc[done.index,c])|(done[c].isna()&b.loc[done.index,c].isna()))
    print(' ',c,'differs on previously-completed rows:',int(ne.sum()))
chg=a.index[~((a['completed']==b['completed'])|(a['completed'].isna()&b['completed'].isna()))]
print('rows whose completed flag changed:',len(chg), sorted(chg.tolist())[:3], '(expected = the 58 Week 6 games)' )
print('changed ids are exactly the Week 6 games:', set(chg)==set(cfbd))
print('changed subset of week6:', set(chg)<=set(cfbd), 'week6 ids not changed:', sorted(set(cfbd)-set(chg)))
g=ds(json.loads(st.read_bytes(f'{run}/games_ref.json'))).set_index('game_id')
for gid in sorted(set(cfbd)-set(chg)):
    print(gid, 'old completed/points', a.loc[gid,['completed','home_points','away_points']].tolist(), 'new', b.loc[gid,['completed','home_points','away_points']].tolist(), 'week', g.loc[gid,'week'], g.loc[gid,'start_date'] if 'start_date' in g.columns else '')
extra=[i for i in done.index if g.loc[i,'week']>5]; print('old completed rows with week>5:', extra)
