import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

root = Path('docs/plans/2026-10-11/week6-closeout-evidence/20261011T140813Z')
checks = []
for label,path in [('health','/api/health?season=2026&week=6'),('results','/results?season=2026&week=6'),('performance','/performance'),('ratings','/ratings'),('matchup','/matchup/401862797')]:
    url = 'https://c-ks-picks-cfb.vercel.app' + path
    try:
        with urlopen(Request(url,headers={'User-Agent':'CKsPicks closeout read-only verification'}),timeout=30) as response:
            raw,status = response.read(),response.status
    except HTTPError as error:
        raw,status = error.read(),error.code
    observed = datetime.now(timezone.utc).isoformat()
    filename = f'live-{label}.json' if label == 'health' else f'live-{label}.html.gz'
    output = raw if label == 'health' else gzip.compress(raw,mtime=0)
    with (root/filename).open('xb') as handle:
        handle.write(output)
    check = {'label':label,'url':url,'status':status,'observed_at':observed,'path':filename,'response_sha256':hashlib.sha256(raw).hexdigest(),'file_sha256':hashlib.sha256(output).hexdigest()}
    if label == 'health':
        check['response'] = json.loads(raw)
    else:
        html = raw.decode('utf-8',errors='replace')
        check['has_display_only_notice_phrase'] = 'not part of the prospective record' in html.lower()
        check['has_prospective_phrase'] = 'prospective' in html.lower()
        check['has_unified_record_phrase'] = 'unified' in html.lower()
    checks.append(check)
result = {'checks':checks,'deployed_revision':'not exposed by these responses; not independently verified','claim_limit':'HTTP/health evidence only; no visual/layout or completed grades verification'}
(root/'live-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'statuses':{c['label']:c['status'] for c in checks},'health':checks[0].get('response'),'deployed_revision':result['deployed_revision']},indent=2))
