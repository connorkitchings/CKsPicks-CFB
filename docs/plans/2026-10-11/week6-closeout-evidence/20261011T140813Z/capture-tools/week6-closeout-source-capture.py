import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import dotenv_values

config = {**dotenv_values('.env'), **os.environ}
assert config.get('CFB_STORAGE_BACKEND') == 'r2'
root = Path('docs/plans/2026-10-11/week6-closeout-evidence')
root.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
destination = root / stamp
destination.mkdir(exist_ok=False)
records = {}
for entity in ('games', 'lines'):
    url = f'https://api.collegefootballdata.com/{entity}?year=2026&week=6&seasonType=regular&classification=fbs'
    request = Request(url, headers={'Authorization': 'Bearer ' + config['CFBD_API_KEY']})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        received = datetime.now(timezone.utc)
        status = response.status
    path = destination / f'cfbd-{entity}.json'
    with path.open('xb') as handle:
        handle.write(raw)
    records[entity] = {
        'url': url, 'http_status': status, 'observed_at': received.isoformat(),
        'path': path.name, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
    }
games = json.loads((destination / 'cfbd-games.json').read_bytes())
lines = json.loads((destination / 'cfbd-lines.json').read_bytes())
ids = {int(game['id']) for game in games}
assert len(ids) == len(games) == 58
assert all(g.get('completed') is True and g.get('homePoints') is not None and g.get('awayPoints') is not None for g in games)
normalized = sorted([
    {key: game.get(key) for key in ('id', 'season', 'week', 'startDate', 'completed', 'homeTeam', 'awayTeam', 'homePoints', 'awayPoints')}
    for game in games
], key=lambda row: row['id'])
normalized_bytes = json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()
(destination / 'normalized-finals.json').write_bytes(normalized_bytes)
coverage = {}
for target, field in (('spread', 'spread'), ('total', 'overUnder')):
    eligible = {int(game['id']) for game in lines if any(line.get(field) is not None for line in game.get('lines', []))}
    coverage[target] = {'present': sorted(ids & eligible), 'missing': sorted(ids - eligible), 'unexpected': sorted(eligible - ids)}
observed_at = datetime.fromisoformat(records['games']['observed_at'])
summary = {
    'schema_version': 'week6_closeout_source_observation_v1',
    'records': records, 'games': len(games), 'completed': len(normalized),
    'latest_kickoff': max(g['startDate'] for g in games),
    'normalized_finals_sha256': hashlib.sha256(normalized_bytes).hexdigest(),
    'fresh_cfbd_line_coverage': coverage,
    'line_use': 'post-kickoff diagnostic only; no pregame admission or grading authority',
    'stability_status': 'baseline observation only; not stable for 24 hours',
    'earliest_recheck_without_earlier_evidence': (observed_at + timedelta(hours=24)).isoformat(),
}
(destination / 'observation.json').write_text(json.dumps(summary, indent=2) + '\n')
checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()}
(destination / 'checksums.json').write_text(json.dumps(checksums, indent=2) + '\n')
print(json.dumps({'evidence_directory': str(destination), 'observed_at': records['games']['observed_at'], 'games': len(games), 'completed': len(normalized), 'next_recheck': summary['earliest_recheck_without_earlier_evidence'], 'fresh_lines': {t: {'present': len(c['present']), 'missing': c['missing'], 'unexpected': c['unexpected']} for t,c in coverage.items()}}, indent=2))
