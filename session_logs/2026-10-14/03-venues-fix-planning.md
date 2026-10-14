# Session: Venue-catalog permanent-fix planning (Sol)

## TL;DR
- **Worked On:** Start-session onboarding plus investigation and planning for the venue ingestion bug (CFBD catalog filtered against the local games index, dropping FCS/neutral/renovated venues from Silver and blocking `publish_game_venues.py` on the city gate).
- **Outcome:** Approved plan contract persisted at `docs/plans/2026-10-14/02-venues-complete-catalog-fix.md`; no implementation files touched.
- **Plan Contract:** `docs/plans/2026-10-14/02-venues-complete-catalog-fix.md`
- **Approval / Status:** Owner approved with three decisions (all-seasons scope; Production republish now, owner-run; keep `--supplement` as emergency hatch). Contract lifecycle state: `Approved`.
- **Blockers:** None.
- **Next:** Owner opens a fresh Terra task to execute the contract.

## Context and Decisions
- Bug confirmed in code at `src/cks_picks_cfb/data/venues.py:53-76` exactly as reported: `fetch_data()` filters the full `venues_api.get_venues()` result against `get_fbs_venue_ids()` derived from the local `raw/games` index.
- Findings beyond the report: (a) dead `get_fbs_team_names()` stub (lines 31-33) is a removal candidate; (b) a second filter site in `history_source_capture.py::_planned_requests()` is an exact point-in-time capture contract — deliberately deferred, not in scope; (c) neither the repair-track nor the Week 7 bridge contract mentions venues, so no governance conflict; (d) `known_issues.md` issue 4 already prescribed this fix ("a fresh 2026 venue capture, then Silver venues") — the supplements were always documented as interim.
- Owner decisions: re-ingest all 11 seasons (2015-2019, 2021-2025, 2026); Production `game_venues` republish now, owner-run; keep `--supplement` mechanism as a documented emergency hatch.
- Promotion mechanism verified: `promote_silver_versions.py --datasets venues --pin venues=<version>` registers the Preview Silver version in the Production catalog (shared R2 bucket, hashes re-verified).

## Work Completed
- Start-session checklist: AGENTS.md, `docs/status.md`, QUICKSTART reviewed; branch `dev` clean (tip `5380f867`); `.env` fully configured (storage keys present, values not printed); recent session logs reviewed (venue evidence in `session_logs/2026-10-14/02-season-operations-implementation.md`).
- Investigated: `venues.py`, `publish_game_venues.py`, `game_venues.py`, base-ingester `run()`/`fetch_source_request` flow, Silver `normalize_venues`, `build_silver.py`, venue contract doc, known-issues issue 4, both supplement JSONs, travel-distance feature usage of raw venues, MMakefile `fetch-source`/`build-silver`/`promote-silver` paths.
- Persisted the approved contract (this session's only write, plus this log).

## Files Modified
- `docs/plans/2026-10-14/02-venues-complete-catalog-fix.md` - Approved plan contract (new).
- `session_logs/2026-10-14/03-venues-fix-planning.md` - This log (new).

## Validation
- [x] `git diff --check` equivalent: both files are new, syntax reviewed on write.
- [ ] No code validation in this session (persistence only, per instructions).

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Fresh Terra task with the exact contract path `docs/plans/2026-10-14/02-venues-complete-catalog-fix.md`.
- **Watch out for:** Terra must execute only the contract's four phases; Production steps (promote apply, Production republish) are owner-run through the restricted login. CFBD `get_venues` takes no year parameter — Phase 2 captures the same current catalog under each season partition.

**tags:** ["planning", "venues", "pipeline", "data-ingestion"]
