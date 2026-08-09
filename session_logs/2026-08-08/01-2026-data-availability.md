# Session: 2026 Data Availability Check and Ingestion

## TL;DR

- **Worked On:** Verified 2026 CFBD data availability via live API probes and R2 state; ingested newly-available sources; refreshed the provider-audit availability matrix.
- **Completed:** Ingested 2026 rosters (15,171 FBS players) and the preseason Coaches Poll rankings (25 records) to R2. Updated `docs/cfbd/2026_provider_audit.md` and `docs/cfbd/quickstart.md` to reflect the 2026-08-08 availability state.
- **Blockers:** Talent still returns empty (0 teams) and gates the immutable 2026 preseason snapshot. Week 1 betting lines cover only 51 of 99 scheduled FBS games, which blocks `make publish-week YEAR=2026 WEEK=1`.
- **Next:** Recheck CFBD talent later in August, then capture the complete 2026 preseason snapshot via `scripts/data/ingest_preseason.py --year 2026 --as-of <date>`. Recheck Week 1 line coverage before publishing.

## Changes Made

- **R2 `raw/rosters/year=2026`:** Ingested 15,171 players via `RostersIngester` (source became available since the 2026-08-04 audit).
- **R2 `raw/rankings/year=2026`:** Ingested 25 records (preseason Coaches Poll) via `RankingsIngester`.
- **`docs/cfbd/2026_provider_audit.md`:** Contract-probe table split rosters/returning production/talent; integration map `get_roster` now records the 8/8 ingestion; data-availability calendar updated to "observed 2026-08-04, updated 2026-08-08" with per-source states.
- **`docs/cfbd/quickstart.md`:** Replaced the stale "rosters, talent, and returning-production feeds were empty" note with the 8/8 state.

## Live 2026 availability observed (2026-08-08)

| Source | State |
| --- | --- |
| Schedule | 888 games (W1=99), 0 completed; runs Aug 29 - Dec 12 |
| Teams / coaches / venues | 138 FBS / 138 / 844 |
| Recruiting team rankings | 221 teams |
| Rankings | 1 preseason week (Coaches Poll) |
| Rosters | 15,171 players (new since 8/4) |
| Returning production | 136 teams (new since 8/4) |
| Talent | Empty (0); gates the preseason snapshot |
| Week 1 betting lines | 51/99 games with a provider line |
| Plays / game stats | 0 (expected; no games played) |

## Testing

- [x] `uv run ruff check .` — passed
- [x] `uv run pytest -q` — 207 passed (12 pre-existing sklearn numerical warnings in `test_preseason.py`)
- [x] `uv run mkdocs build` — passed (2 pre-existing broken relative links in `docs/deployment/`, unchanged)

## Notes for Next Session

- **Resume at:** capture the 2026 preseason snapshot once CFBD publishes talent (`ingest_preseason.py --year 2026 --as-of <date>`); all five sources must be nonempty for inference.
- **Remember:** the preseason snapshot is immutable per `year/as_of`; never rerun the same combination. Only `talent` is still missing for a complete snapshot.
- **Watch out for:** `make publish-week` now fails its betting-line coverage gate until all 99 Week 1 FBS games have a provider line (currently 51). Returning production (136 teams) is available but was intentionally not snapshotted alone because a mixed-`as_of` snapshot can never pass `snapshot_is_complete`.
- **Worktree:** this session's edits were folded into the broader uncommitted CFBD/preseason worktree and split into coherent commits per the 2026-08-05 closeout.

**tags:** ["cfbd", "ingestion", "preseason", "readiness", "2026-season", "docs"]
