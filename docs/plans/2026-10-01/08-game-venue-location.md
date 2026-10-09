# Game Venue Location (City, State) on Picks and Results

- **Status:** Implemented (venue data live in Production, 271 games; city/state UI released; recorded in `docs/status.md`)
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User approved the plan in-session on 2026-10-01 ("game venue", "UI now, data at home").
- **Implementation log:** `session_logs/2026-10-01/13-prototype-cards-location.md` (code and tests). The data steps below are run by the user with Neon/R2 credentials.
- **Preview run (2026-10-02):** migration 0019 applied and 271 venue rows published to Preview (260 with city and state, 10 venues not in Silver, shown without a location). Production (user-run 2026-10-02; the data is in the page payload, but the city/state UI is only in the closed prototype cards until they are ported): 0019 applied and 271 rows published, 271 with a city and 269 with a state (production's venue Silver version is newer, so all 10 Preview misses resolved).
- **Commit policy:** Code is on `dev`. Run the data steps on Preview first, then production. Merge `dev` into `main` when the Preview check passes.

## Goal
Show each game's city and state next to the time on the Picks and Results cards, using the actual game venue so neutral-site and bowl games are correct.

## Evidence
- Neon `games` has no venue, city, state or neutral-site columns (`contracts/schema.sql`).
- CFBD games carry `venueId`, a venue name and `neutralSite` but not city/state; city, state, country code and timezone are on CFBD venue records (verified from the installed `cfbd` client models). The pipeline already ingests both into Silver (`games`, `venues` with contract `venues_v1`).
- `games` is overwritten by every publish run and runs are immutable once frozen, so venue facts are stored separately.

## What was built (on `dev`)
- Migration `contracts/migrations/0019_game_venues.sql`, `contracts/schema.sql`, `contracts/schema.ts` (+ identical `web/src/lib/schema.ts`): table `game_venues(game_id PK, venue_id, venue_name, city, state, country_code, timezone, neutral_site, source, updated_at)`; `SELECT` for `cks_web`, `SELECT/INSERT/UPDATE` for `cks_pipeline`. Additive; no existing table is modified.
- `src/cks_picks_cfb/data/game_venues.py`: pure `build_game_venue_rows(games, venues, game_ids)` and the upsert SQL.
- `scripts/pipeline/publish_game_venues.py`: thin CLI; `--dry-run` prints the Silver column names, a coverage report and sample rows and writes nothing.
- Web: guarded `LEFT`-style lookup (`hasGameVenuesTable`, `withVenues` in `web/src/lib/queries.ts`). If the table or a row is missing, no location is shown; nothing fails. The prototype cards show `City, ST`, plus a "Neutral site" note.
- Tests: transform unit tests; migration test (applied from an empty database, upsert round-trip, re-apply is a no-op; verified against a disposable PostgreSQL); web unit and e2e tests.

## Runbook (user, with credentials)
1. **Confirm the Silver columns.** Run the dry run on Preview and read the printed column lists. Expected: Silver `games` has a venue id (`venue_id`) and optionally `neutral_site`; Silver `venues` has `venue_id`, `name`, `city`, `state`. If a name differs the script exits with the column list; adjust the candidate-name tuples at the top of `game_venues.py`.
   ```bash
   PYTHONPATH=src:. uv run python scripts/pipeline/publish_game_venues.py \
       --season 2026 --environment preview --dry-run
   ```
   Review the report: expect `with_city_and_state` close to `rows` for FBS games; investigate `missing_venue_id`, `venue_not_found` and `games_absent_from_silver`.
2. **Apply the migration to Preview** (owner login): `uv run python scripts/pipeline/migrate_db.py --database-env PREVIEW_DATABASE_URL`.
3. **Publish to Preview** (same command without `--dry-run`), then open `/test-picks` against Preview and check cities.
4. **Production:** apply `0019` to the production branch, then run the script through `scripts/ops/with_production_pipeline_env.sh` with `--environment production`. The web app tolerates the table being absent, so deploy order does not matter.
5. Re-run the script once per season and after any schedule change; it is idempotent.

## Definition of Done
- [x] Migration, schema sync, transform, script and tests exist and pass (`contracts/validation.py`, ruff, pytest incl. migration test on PostgreSQL, web lint/typecheck/unit/e2e).
- [x] Cards show `City, ST` and the neutral-site note, show nothing when unknown, and never truncate the pick.
- [ ] Silver column names confirmed with the dry run (Preview).
- [ ] `0019` applied and venues published on Preview; cities checked on the Picks and Results prototypes.
- [ ] Same on production.

## Risks and rollback
- **Silver column names differ:** the script stops with the column list before writing anything.
- **Coverage gaps (missing venue ids):** rows are written with nulls; the cards show nothing for those games.
- **Rollback:** `DROP TABLE game_venues` (the web app falls back to no location); revert the commits.
- **Kickoff time zone:** times stay in Eastern. The venue `timezone` is stored, so showing kickoff in local venue time is a possible follow-up.
