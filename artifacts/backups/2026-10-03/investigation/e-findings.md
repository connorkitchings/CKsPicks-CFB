# E findings: venue gaps (read-only, 2026-10-03)

## Scope (wider than the two known games)
- Preview `game_venues` for 2026: 271 rows, every 2026 game has a row. **11 games (4.1%) have NULL city and/or state,
  across 8 venues**, so it is venue-level, not game-level:
  | venue (id) | games | city | state | missing |
  |---|---|---|---|---|
  | Fargodome (3714) | 401864577 (wk0), 401864515 (wk5) | null | null | city, state, country, timezone |
  | Hornet Stadium (3757) | 401866429 (wk4), 401864507 (wk3) | null | null | all |
  | Ryan Field (11823) | 401858476 (wk5) | null | null | all |
  | Elliott T. Bowers Stadium (3647) | 401862707 (wk2) | null | null | all |
  | TQL Stadium (7173) | 401856797 (wk3) | null | null | all |
  | Wembley Stadium (2455), neutral | 401856812 (wk3) | null | null | all |
  | Lambeau Field (3798), neutral | 401858438 (wk1) | null | null | all |
  | Nissan Stadium (3810), neutral | 401856661 (wk1) | null | null | all |
  | Aviva Stadium (3504), neutral | 401856766 (wk0) | Dublin | null | state only (legitimately none, Ireland) |
- The two games in the earlier audit (Northwestern at Penn State 401858476, North Dakota State v Wyoming 401864515) are 2 of the 11.

## Root cause
- `scripts/pipeline/publish_game_venues.py` joins Silver `games` (venue_id) to the latest validated Silver `venues` dataset.
- Silver `venues` comes from per-year CFBD venue captures (parameters: `year`, `classification: fbs`, expected ids); the
  catalog holds 106 venue captures and the latest year is **2025**; there is no 2026 venue capture. Venues that were not an
  FBS home venue in 2025 (Fargodome, Hornet Stadium: new FBS programs; Ryan Field: new stadium; TQL, Bowers; the neutral-site
  venues) therefore have no city/state to join. Only Aviva Stadium (a 2025 venue) has its city.
- It is not a provider gap: a read-only call to CFBD `/venues` (852 venues) returns city/state for all 9 ids:
  Wembley London (GB), Aviva Dublin (IE), Bowers Huntsville TX, Fargodome Fargo ND, Hornet Sacramento CA,
  Lambeau "Greenbay" WI (CFBD's spelling), Nissan Nashville TN, TQL Cincinnati OH, Ryan Evanston IL.
  Wembley and Aviva carry no state in CFBD, correctly (international).

## Backfill path (for the single production batch)
1. Fresh 2026 venue capture (the existing captures cannot supply these rows): e.g. `make fetch-source` for venues, year 2026.
2. Rebuild/validate Silver `venues`; run `publish_game_venues.py --season 2026 --environment preview --dry-run`, review, write, then production.
3. After it: all 11 rows get a city; Wembley and Aviva keep a null state by design (the UI must render city-only for them);
   "Greenbay" is a provider spelling (decide: accept or add a display override).
- Prevention (proposal, belongs with D9): fail the publish dry run when any scheduled game's venue lacks city, and run a venue
  capture whenever the schedule gains a venue id not in the current Silver `venues`.
