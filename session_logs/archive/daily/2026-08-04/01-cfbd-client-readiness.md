# Session: CFBD Client Upgrade and Publish Readiness

## TL;DR

- **Worked On:** Applied the first two actions from the 2026 CFBD provider audit.
- **Completed:** Upgraded the official client to `cfbd` 5.16.0, added synthetic
  client-contract tests, and gated pregame publishing on complete sportsbook
  coverage.
- **Blockers:** CFBD still has no sportsbook line for 48 of 99 Week 1 games;
  aggregated team recruiting remains incompatible with the latest published
  client.
- **Next:** Recheck lines before publishing Week 1; recheck rosters, talent,
  and returning production later in August before any preseason snapshot.

## Changes Made

- `pyproject.toml`, `uv.lock`: Pinned CFBD to 5.16.x, the latest published
  client validated against the live REST catalog.
- `src/cks_picks_cfb/data/base.py`: Empty provider responses now raise an
  explicit availability error and do not write an empty partition.
- `src/cks_picks_cfb/data/betting_lines.py`: Added an optional complete-slate
  coverage gate that fails before a line-partition write.
- `scripts/data/ingest_week.py`, `scripts/data/ingest_season.py`, `Makefile`:
  Added clear availability/coverage outcomes and enforce complete coverage in
  `make publish-week`.
- `tests/test_cfbd_client_contracts.py`, `tests/test_cfbd_readiness.py`:
  Added client-shape and readiness-gate coverage.

## Testing

- [x] Live CFBD verification: player recruiting and live plays parse with 5.16.0.
- [x] Live CFBD verification: aggregated recruiting remains blocked by client
  validation; no production code uses it.
- [x] Live coverage gate: blocks Week 1 before R2 writes with 48 uncovered games.
- [x] `uv run pytest -q` — 207 passed.
- [x] `uv run ruff format --check . && uv run ruff check .`.
- [x] `uv run mkdocs build`.

## Notes for Next Session

Do not run `make publish-week YEAR=2026 WEEK=1` until CFBD has a sportsbook
line for every scheduled FBS game. The command now exits before prediction or
Neon publication when coverage is incomplete.

**tags:** ["cfbd", "ingestion", "readiness", "2026-season"]
