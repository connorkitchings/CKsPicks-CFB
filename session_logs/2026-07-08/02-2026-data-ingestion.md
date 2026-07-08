# Session: 2026 Preseason Data Ingestion

## TL;DR
- **Worked On:** Ingest all available 2026 data into R2; fix storage-entity-name bugs blocking ingestion
- **Completed:** Fixed 5 latent `read_index` bugs from the July 6 storage-unification refactor; verified 2026 games/teams/venues already in R2; backfilled recruiting for 2024 + 2025
- **Blockers:** CFBD API has NOT yet published 2026 rosters / coaches / recruiting data — pipeline is ready, data availability is the only remaining gate
- **Next:** Re-run ingestion in August (fall camp) when CFBD flips the year over; refresh games for new start times closer to Week 1

---

## What Was Done

### Phase 1: Bug fixes (storage entity-name unification)
The July 6 refactor renamed entity names to `raw/...` prefix but missed several `read_index()` call sites. Verified directly: `read_index("teams", ...)` → 0 rows; `read_index("raw/teams", ...)` → 138 rows.

Files fixed:
- `src/cks_picks_cfb/data/rosters.py:38` — `"teams"` → `"raw/teams"`
- `src/cks_picks_cfb/data/coaches.py:44` — `"teams"` → `"raw/teams"`
- `src/cks_picks_cfb/features/external.py:35` — `"external_ratings"` → `"raw/external_ratings"`
- `src/cks_picks_cfb/features/external.py:134` — `"recruiting"` → `"raw/recruiting"`
- `src/cks_picks_cfb/features/external.py:196` — `"rankings"` → `"raw/rankings"`
- `tests/test_external_features.py` — updated 3 `_MockStorage` fixture keys to use `raw/` prefix (matching the production entity-name convention; the file's own comment on line 34 already documented this intent)

**Untouched (verified NOT bugs):**
- `scripts/pipeline/score_weekly_bets.py:20`, `src/cks_picks_cfb/analysis/unadjusted.py:61,103` — these use the legacy `utils/local_storage.py:LocalStorage` shim with `data_type="raw"`, which prepends the tier prefix internally
- `research/validation/`, `research/debug/`, `research/ratings/` — exploration scripts, may have stale paths (noted in prior session log), out of production path
- `tests/test_storage_entity_api.py` — symmetric write/read with bare entity names (testing low-level storage, not the tier convention)

### Phase 2: Attempted 2026 ingestion
Ran `make ingest-season YEAR=2026 ENTITIES=rosters,coaches,recruiting`. The bug fix worked — ingester correctly found 138 FBS teams (no more `RuntimeError`). But CFBD returned 0 records for all three.

Verified via direct API calls (year=2024 / 2025 / 2026 comparison):
| Endpoint | 2024 | 2025 | 2026 |
|---|---|---|---|
| Rosters | 22,843 | 30,072 | **0** |
| Coaches | 152 | 136 | **0** |
| Recruiting | 194 | 232 | **0** |

**Conclusion:** CFBD treats 2025 as the "current" season until 2026 kicks off. Not a code issue.

### Phase 3: Recruiting backfill (2024 + 2025)
Discovered `raw/recruiting` in R2 had a gap — only 2023 was present. Ingested:
- `raw/recruiting/year=2024`: 194 rankings (Georgia #1, 317.05 pts)
- `raw/recruiting/year=2025`: 232 rankings (Texas #1, 312.27 pts)

This is directly relevant to 2026 modeling: `merge_recruiting_composite` averages `n_years` of classes for team-talent features.

---

## Final 2026 R2 Inventory

| Entity | Status | Rows |
|---|---|---|
| `raw/teams/year=2026` | ✅ Ingested (July 6) | 138 |
| `raw/venues/year=2026` | ✅ Ingested (July 6) | 150 |
| `raw/games/year=2026` | ✅ Ingested (July 6) | 888 (weeks 1–13 + 1 wk-15 Army–Navy; 442 have start times, 446 TBD; week 14 conf-champ currently empty) |
| `raw/rosters/year=2026` | ⏳ Pending CFBD | — |
| `raw/coaches/year=2026` | ⏳ Pending CFBD | — |
| `raw/recruiting/year=2026` | ⏳ Pending CFBD | — |
| `raw/rankings/year=2026` | ⏳ Pending preseason polls | — |
| `raw/betting_lines/year=2026` | ⏳ Pending sportsbooks (1–2 wks before kickoff) | — |
| `raw/plays/year=2026` | ⏳ Season starts Aug 29 | — |
| `raw/game_stats/year=2026` | ⏳ Season starts Aug 29 | — |
| `raw/external_ratings/year=2026` | ⏳ SP+/FPI/FEI preseason typically August | — |

---

## Testing
- [x] `uv run ruff format` + `uv run ruff check` — clean on all touched files
- [x] `uv run pytest -q` — **187 passed** (initially broke 15 external-feature tests by fixing the production entity name without updating the mock fixtures; fixed by aligning fixture keys with the documented `raw/entity/year=N` convention)

## Files Changed
- `src/cks_picks_cfb/data/rosters.py` (1-line fix)
- `src/cks_picks_cfb/data/coaches.py` (1-line fix)
- `src/cks_picks_cfb/features/external.py` (3-line fixes)
- `tests/test_external_features.py` (3 fixture-key updates)
- `raw/recruiting/year=2024/` (new in R2 — 194 rows)
- `raw/recruiting/year=2025/` (new in R2 — 232 rows)

## Notes for Next Session

**When to retry 2026 ingestion:**
- **Rosters + Coaches:** Mid-August (fall camp). CFBD flips the "current season" year over around this time.
- **Recruiting 2026:** Should appear once CFBD ingests the signed class — check weekly.
- **Rankings (AP/Coaches):** Preseason polls release late August.
- **Betting lines:** 1–2 weeks before Week 1 kickoff (mid-August).
- **External ratings (SP+/FPI/FEI):** Preseason editions typically drop in August.

**Re-run command when data is available:**
```bash
make ingest-season YEAR=2026 ENTITIES=rosters,coaches,recruiting,rankings
```

**Games refresh (per user decision, deferred):**
Current 2026 games snapshot is from July 6 (888 games, 442 with start times). Refresh closer to Week 1 to capture TV time assignments:
```bash
make ingest-season YEAR=2026 ENTITIES=games
```

**Watch out for:**
- Week 14 (conference championship weekend) currently has 0 games in CFBD — will populate as the regular season concludes and matchups are determined.
- `merge_recruiting_composite` feature will now work correctly for 2024+ modeling thanks to the backfill.
- The legacy `utils/local_storage.py:LocalStorage` shim (used by `score_weekly_bets.py`, `unadjusted.py`) uses different entity-name conventions than the unified backend — this is intentional backward-compat, not a bug.

**tags:** ["ingestion", "2026-season", "bugfix", "storage", "r2", "recruiting", "cfbd-api"]
