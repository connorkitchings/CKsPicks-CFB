# Permanent Venue-Catalog Fix: Ingest the Complete CFBD Catalog in Raw + Silver

- **Status:** Implemented
- **Approval source:** Owner approved in-session on 2026-10-14, with three decisions: re-ingest all 11 seasons (2015-2019, 2021-2025, 2026); Production `game_venues` republish now, owner-run; keep `--supplement` as a documented emergency hatch.
- **Implementation session:** Terra execution completed 2026-10-14; implementation log at `session_logs/2026-10-14/04-venues-fix-implementation.md`.

## Implementation progress (2026-10-14, Terra)

- **Phase 1 done:** filter and dead stub removed; new regression test; full `tests/` suite 2869 passed, 30 skipped; lint clean.
- **Phase 2 done:** 11/11 seasons re-ingested unfiltered in Preview (852 records each); validated Silver versions `artifacts/preview/refs/venues-<y>-complete-v1.json`; 2026 version `c713b15888c8aaf66b7b0b93` holds all supplemented + issue-4 venue IDs.
- **Phase 3 done:** Preview dry run (388/388 city, gate clean, no supplement) and apply verified (0 value changes). Production version `c713b15888c8aaf66b7b0b93` promoted to target catalog; Production `game_venues` republish executed supplement-free with 0 value changes across all 388 rows vs pre-write export.
- **Phase 4 done:** `weekly_pipeline.md` and `known_issues.md` updated; docs build passes.
- **Plan lifecycle:** `Implemented`. All acceptance criteria satisfied.

## 1. Problem

`VenuesIngester.fetch_data()` (`src/cks_picks_cfb/data/venues.py:53-76`) fetches
the complete CFBD venue catalog (~800 venues) and then **discards every venue
not already present in the local `raw/games` index** at ingestion time. Any
venue CFBD knows but the local games index did not yet reference is dropped
from Silver:

- FCS and neutral-site venues (Week 7: Fargodome 3714, Hornet Stadium 3757,
  Elliott T. Bowers Stadium 3647).
- Renovated/relocated stadiums (Week 6: Northwestern's temporary Ryan Field
  11823).
- Capture-timing gaps: venues captured before the games index had full schedule
  details are permanently omitted.

Downstream, `scripts/pipeline/publish_game_venues.py` joins Silver `games`
(`venue_id`) against Silver `venues` (city, state, timezone) and enforces
`require_venue_cities` — every published game must have a non-null city. The
dropped venues join to NULL city, so the publish hard-aborts. Weeks 6 and 7
were unblocked mid-flight with the temporary `--supplement` mechanism
(`conf/venue_supplement_2026_w6_v1.json`,
`conf/venue_supplement_2026_w7_v1.json` patching missing IDs in-memory). This
contract is the permanent fix.

## 2. Goals

1. `VenuesIngester` ingests the entire CFBD venue catalog (~800 rows, <100 KB
   Parquet) with no games-index filtering.
2. New unfiltered Raw captures and validated Silver versions for all 11 seasons
   (2015-2019, 2021-2025, 2026) in Preview.
3. Prove the supplement-free path in Preview (dry run + apply with an expected
   zero-value-change diff), promote the 2026 Silver venues version to the
   Production catalog, and republish Production `game_venues` owner-run with a
   pinned version and no supplement.
4. Deprecate (not remove) the `--supplement` mechanism in docs.

## 3. Non-goals

- No change to `fetch_source_request()`'s exact-`expected_venue_ids` behavior.
- No change to `history_source_capture.py::_planned_requests()` venue planning
  (exact point-in-time capture contract for the successor/rebuild lineage;
  considered and deliberately deferred).
- No change to `docs/status.md` (no week-state or selected-run change).
- No model, rating, feature, or cutover behavior change. Venues are not a V5
  model input (forecast venue fields are hard-coded; see
  `docs/data/known_issues.md`). This work is additive-only and cannot disturb
  the in-flight repair track or cutover.

## 4. Phase 1 — Code fix (`src/cks_picks_cfb/data/venues.py`)

- Delete `get_fbs_venue_ids()` (lines 35-51) and the filtering logic in
  `fetch_data()` (lines 65-75). `fetch_data()` returns every venue from
  `venues_api.get_venues()`.
- Delete the dead deprecated stub `get_fbs_team_names()` (lines 31-33).
- Add a test in `tests/test_ingestion_hardening.py`: monkeypatched
  `VenuesApi` returning N venues with an empty games index must yield all N
  from `fetch_data()` (pre-fix returns 0). The existing exact-ids
  `fetch_source_request` test is unaffected.
- Validation: `uv run pytest -q`, `uv run ruff format . && uv run ruff check .`,
  focused ingestion-hardening tests, `git diff --check`.

## 5. Phase 2 — Re-ingest Raw + rebuild Silver, all 11 seasons (Preview, additive)

For each season in 2015-2019, 2021-2025, 2026:

1. `make fetch-source YEAR=<y> ENTITY=venues ENV=preview` — new registered
   Bronze capture. Note: CFBD `get_venues` takes no year parameter, so each
   season's capture is the same current ~800-row catalog stored under its
   season partition, matching the existing one-version-per-capture-year
   architecture.
2. `make build-silver YEAR=<y> DATASET=venues CAPTURE_ID=<new-id>
   AS_OF=<one shared freeze timestamp> ENV=preview
   OUTPUT_REF_URI=artifacts/preview/refs/venues-<y>-complete-v1.json` — new
   validated Silver version.
3. Verify per season: row count ~=800; readback hash stable on identical
   rebuild. For 2026 additionally assert presence of the four supplemented IDs
   (11823 Ryan Field temporary, 3714 Fargodome, 3757 Hornet Stadium, 3647
   Elliott T. Bowers) plus the previously missing set from known-issues issue 4
   (Wembley, Aviva, Lambeau, Nissan Stadium, TQL Stadium).

All objects are new, immutable, and additive; nothing existing is mutated and
all consumers pin by `version_id`. Side benefit: the dual-written compatibility
projection `raw/venues/year=<y>` becomes complete, which also completes legacy
travel-distance features — no model rebuild is triggered.

## 6. Phase 3 — Publish proof and Production republish (owner-run)

1. **Preview dry run:** `publish_game_venues.py --season 2026 --environment
   preview --venues-version <new-2026-version> --games-version <current pinned>
   --dry-run --require-city` — no `--supplement`. Expect `venue_not_found: 0`
   and a clean city gate.
2. **Preview apply:** pre-write export of `game_venues`, idempotent apply,
   readback diff vs export — expect zero value changes (supplement values came
   from CFBD, so Silver now agrees by construction).
3. **Promote:** `promote_silver_versions.py --season 2026 --datasets venues
   --pin venues=<new-version>` — dry run, then owner-run apply to register the
   2026 version in the Production catalog (shared R2 bucket: nothing copied,
   hashes re-verified).
4. **Production republish (owner-run, per current gates):** same pinned publish
   through the restricted production login, pre-write export, readback diff —
   expect zero value changes; no supplement used. Weeks 6-7 rows stay
   byte-identical; the supplement path is proven unnecessary.

## 7. Phase 4 — Deprecate supplements (docs only; mechanism retained)

- `docs/ops/weekly_pipeline.md` section "Game venues": document the
  complete-catalog 2026 version and pin guidance; mark `--supplement`
  deprecated for routine use, retained as an emergency same-day hatch.
- `docs/data/known_issues.md` issue 4: addendum recording the root cause (the
  `VenuesIngester` filter) and this permanent fix.
- Keep `apply_venue_supplement`, the `--supplement` flag, its tests, and both
  `conf/venue_supplement_2026_w{6,7}_v1.json` files as historical/emergency
  artifacts.

## 8. Acceptance criteria

- [ ] `fetch_data()` returns the full CFBD catalog with an empty games index;
    new test passes; full suite and lint pass.
- [ ] 11 new Preview Bronze captures and 11 new validated Silver venues
    versions; 2026 version contains all supplemented and issue-4 venue IDs.
- [ ] Preview dry run without `--supplement`: `venue_not_found: 0`, city gate
    clean; Preview apply diff is zero value changes.
- [ ] 2026 version promoted to the Production catalog; owner-run Production
    republish without supplement shows a zero-value-change diff.
- [ ] Docs updated (`weekly_pipeline.md`, `known_issues.md`); session log
    written; user executes git operations.
