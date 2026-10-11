import json
from pathlib import Path
import pandas as pd
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
st = get_storage(environment='preview')
run='artifacts/preview/pipeline-runs/w6-closeout-ingest-20261011-r2'
raw=json.loads(Path('conf/rebuild/silver_2026_parents_w5_v1.json').read_text()); pins={p['dataset']:p for p in raw['parents']}
def ds(ref): return read_dataset(st, DatasetRef(**{k:ref[k] for k in ('dataset','version_id','schema_version','content_sha','uri')}))
def diff(name, o, n, key):
    o=o.set_index(key).sort_index(); n=n.set_index(key).sort_index()
    print(name,'old',len(o),'new',len(n),'only-old',len(o.index.difference(n.index)),'only-new',len(n.index.difference(o.index)))
    both=o.index.intersection(n.index); o=o.loc[both]; n=n.loc[both]
    for c in o.columns:
        a,b=o[c],n[c]
        if pd.api.types.is_float_dtype(a) and pd.api.types.is_float_dtype(b):
            ne=~((a==b)|(a.isna()&b.isna())|((a-b).abs()<1e-9))
        else:
            ne=~((a==b)|(a.isna()&b.isna()))
        if ne.any(): print('  col',c,'differs in',int(ne.sum()),'rows; e.g.',[(i,a[i],b[i]) for i in list(a.index[ne])[:3]])
g_new=ds(json.loads(st.read_bytes(f'{run}/games_ref.json')))
g_old=ds(pins['games'])
print(g_old.columns.tolist()[:12])
diff('games<=w5',g_old[g_old.week<=5],g_new[g_new.week<=5],'game_id' if 'game_id' in g_old else 'id')
p_new=ds(json.loads(st.read_bytes(f'{run}/plays_ref.json'))); p_old=ds(pins['plays'])
print(p_old.columns.tolist()[:15])
key=[c for c in ('game_id','play_id','id') if c in p_old.columns]
print('play key',key)
diff('plays<=w5',p_old[p_old.week<=5],p_new[p_new.week<=5],key[:2] if 'play_id' in key else key[:1])
