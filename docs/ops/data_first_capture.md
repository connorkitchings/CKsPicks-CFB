# Data-First Pregame Capture

The data-first research program captures existing CFBD schedule, returning
production, recruiting, and coaching sources in Preview. Capture preserves the
provider response and authentic retrieval time; it does not admit a feature or
authorize production use.

## Manual rehearsal

Run the request plan first. It performs no provider calls or writes:

```bash
PYTHONPATH=src:. uv run python scripts/research/capture_data_first_phase2.py \
  --kind pregame --mode dry-run --run-id rehearsal-plan --season 2026 \
  --max-requests 7
```

After committing the implementation, execute one manual GitHub Actions
`Data-first pregame capture` workflow. Confirm its immutable manifest reports
seven captured requests, authentic timestamps before the relevant kickoff, no
empty or failed responses, and Preview-only catalog registrations.

The daily 12:00 UTC schedule stays disabled until that rehearsal passes. Enable
it by setting the repository variable
`CFB_DATA_FIRST_CAPTURE_SCHEDULE_ENABLED=true`. The workflow uses Preview R2
and Neon secrets, has a single-run concurrency lock, checks the CFBD remaining
call quota, and resumes from per-request result records.

## Historical repair capture

Historical capture consumes the corrected Phase 1 schedule denominator. Its
dry run removes exact requests already present in the Preview catalog and
counts the remaining provider requests by season, season type, and week:

```bash
PYTHONPATH=src:. uv run python scripts/research/capture_data_first_phase2.py \
  --kind historical --mode dry-run --run-id phase2-history-plan \
  --audit-prefix artifacts/research/data-first-football-v1/phase1/2026-09-06T0055Z-phase1-evidence-audit-v3 \
  --schedule-capture-id <registered-postseason-games-capture-id> \
  --max-requests <reviewed-bound>
```

Repeat `--schedule-capture-id` for each of the ten registered postseason games
captures. The command validates that every supplied observation is registered,
comes from CFBD `GamesApi.get_games` under `data_first_games`, is postseason,
and belongs to a permitted development season. It rejects 2020 and conflicting
`(season, game_id)` schedule identities. Supplying all ten captures currently
produces exactly 20 remaining requests: postseason plays and team-game stats
for each permitted season.

An apply run requires the exact committed code SHA. It fails before capture if
the plan exceeds the reviewed bound or the account has fewer remaining calls.
Empty and partial provider responses remain visible as gaps and prevent a
successful run state. Never include 2020 or manufacture historical availability
timestamps; historical retrievals are reconstructed evidence.
