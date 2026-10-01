# High-Quality Team Logos: Self-Hosted, ID-Keyed, Theme-Aware

- **Status:** Approved
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User approved the approach in-session on 2026-10-01 ("I like your recommendation… I'll do it when I get home"). Confirm the open decisions below before executing.
- **Implementation log:** Pending Terra implementation (run on the user's machine; see "Why this runs locally").
- **Commit policy:** Land on `dev` in separate commits per phase (script + manifest, generated assets, web change, cleanup). Merge `dev` into `main` only after the visual check passes.

## Goal
Replace the pixelated logos with sharp ones at every display size, without depending on a third-party CDN at runtime, and make logo lookup robust.

## Evidence (verified 2026-10-01)
- All 338 files in `assets/logos/` and the committed copy `web/public/logos/` are **32×32 PNGs** (~497 KB total). Provenance is not recorded anywhere.
- Rendered sizes (CSS px): 16 (`LeanMarker`), 20 (list rows), 28 (cards, `TeamLine`, `GameRow`), 64–80 (`MatchupHero`). A 2x–3x phone screen needs 56–84 px (cards) and up to 240 px (hero). The images are rendered with `next/image` `unoptimized`, so nothing resizes them.
- Lookup is by school name through `logoUrl()` in `web/src/lib/teams.ts` with a 13-entry alias table (`TEAM_LOGO_MAP`, mirrored in `contracts/teams.py`).
- `web/scripts/sync-logos.mjs` (run by `predev`/`prebuild`) copies `assets/logos/` over `web/public/logos/`.
- The pipeline already stores CFBD team `logos` URLs (`src/cks_picks_cfb/data/teams.py:77`). CFBD team ids match ESPN ids, and ESPN serves 500×500 transparent PNGs at `https://a.espncdn.com/i/teamlogos/ncaa/500/<id>.png` with dark variants under `500-dark/` (from a web search and two public projects; **not verified from this container**, which blocks both the CFBD API and the ESPN CDN).
- Still referencing `assets/logos/`: `src/cks_picks_cfb/analysis/unadjusted.py` (via `LOGOS_DIR`, tested by `tests/test_unadjusted_analysis.py`) and the Nx input in `web/project.json`.

## Why this runs locally
The fetch needs network access to CFBD and the ESPN CDN, which the cloud session cannot reach. Everything except the download (resize, manifest, web changes, tests) can be developed anywhere.

## Decisions
1. **Source:** CFBD `GET /teams/fbs?year=2026` (needs `CFBD_API_KEY`) for `id`, `school`, `logos[]`. Fallback URL when `logos` is empty: `https://a.espncdn.com/i/teamlogos/ncaa/500/<id>.png`; the dark variant swaps `/500/` for `/500-dark/`.
2. **Scope:** FBS teams only (~137). Games shown are FBS-vs-FBS; any other team gets an initials-tile fallback. (The old set carried 338 teams, including FCS and below.)
3. **Self-host, do not hotlink.** No runtime dependency on ESPN's CDN or terms.
4. **Key by team id.** Files are `/logos/v2/<size>/<theme>/<id>.webp`; a generated name→id map replaces the alias table.
5. **Sizes:** `sm` = 96 px (covers 28 px at 3x), `lg` = 256 px (hero at 3x). WebP with alpha (quality ~90). Estimated total < 5 MB for `sm` + `lg` × light + dark.
6. **Theme-aware:** the dark variant is used in dark mode (some navy/black logos vanish on black).
7. **Originals are not kept.** A manifest records, per team, the source URL, retrieval date and the SHA-256 of each generated file, so every asset is re-fetchable and its provenance is recorded.
8. **Immutable caching:** `/logos/v2/*` is served with `Cache-Control: public, max-age=31536000, immutable` (bump `v2` to invalidate).
9. **Licensing:** logos belong to the schools/ESPN. Self-hosting for this display-only research site is a user decision; keep the "display only" footer. (Open: whether to add a trademark attribution line.)

## Open decisions for the user (answer before step 3)
- [ ] Add a trademark/attribution line to the footer? (default: no change)
- [ ] Keep `assets/logos/` (32 px) for `analysis/unadjusted.py`, or switch that code to the new assets? (default: keep, untouched)

## Steps

### Phase A: Fetch and generate (run on the user's machine, from `dev`)
1. Add `sharp` as an explicit `devDependency` in `web/package.json` (currently only transitive).
2. Add `web/scripts/build-team-logos.mjs`:
   - Reads `CFBD_API_KEY` (run as `node --env-file=../.env scripts/build-team-logos.mjs`).
   - `--dry-run`: prints the team count, the first three records and which teams lack `logos`; downloads nothing. **Run this first** to confirm the response shape.
   - For each team: download the light and dark 500 px PNGs (3 retries with backoff, 20 s timeout, polite delay), resize to 96 and 256 px with `sharp` (`fit: contain`, transparent background), write WebP, skip files that exist unless `--force`.
   - Write `web/public/logos/v2/manifest.json` (id, school, source URLs, retrieved date, per-file SHA-256) and `web/src/lib/team-logos.generated.ts` (`{ [school]: id }`, plus a `logoIds` set).
   - Exit non-zero and write `logo-report.json` if any team fails; never leave a half-written directory (stage, then swap).
3. Run it; review the report for failures and name mismatches.

### Phase B: Web changes
4. `web/src/lib/teams.ts`: `logoUrl(teamName, { size, theme })` and `hasLogo(teamName)` backed by the generated map; keep a small override table only for names that fail to match.
5. New `web/src/components/TeamLogo.tsx`: renders light and dark `<img>` pair using the existing `dark:` variant (`dark:hidden` / `hidden dark:block`), explicit `width`/`height`, `sm`/`lg` size choice, and an initials tile when `hasLogo` is false. Replace direct `Image`+`logoUrl` use in `GameRow.tsx`, `MatchupHero.tsx`, `UnitMatchupTable.tsx`, `picks-proto/TeamLine.tsx` and `picks-proto/LeanMarker.tsx`.
6. `web/next.config.ts`: add `headers()` for `/logos/v2/:path*` with the immutable cache header.
7. Stop syncing the old set: remove `predev`/`prebuild` `sync-logos.mjs` hooks and the script; remove `assets/logos` from `web/project.json` inputs. Do **not** delete `assets/logos/` (still used by `analysis/unadjusted.py`) or the old `web/public/logos/*.png` until Phase C passes.

### Phase C: Verify, then clean up
8. Tests: unit tests for `logoUrl`/`hasLogo` (known id, alias, unknown → fallback, size/theme paths); an e2e test on `/test-picks` asserting every visible logo has `naturalWidth >= 2 × clientWidth` (regression guard against pixelation) and that dark mode swaps to the dark file.
9. Visual check at 3x: Playwright `deviceScaleFactor: 3` screenshots of `/test-picks`, `/test-results` and `/matchup/<id>` in light and dark; compare against the old rendering.
10. Remove the old 32 px files from `web/public/logos/` (the new files live under `v2/`) and record the change. Keep `assets/logos/` until `analysis/unadjusted.py` is migrated or deleted.
11. Update `web/README.md` (how logos are built and refreshed once per season) and `docs/status.md`; add a session log.

## Definition of Done
- [ ] Dry run output recorded; build script completes with no failed teams (or each failure listed with its fallback).
- [ ] `manifest.json` exists with source URL and SHA-256 for every asset; total `web/public/logos/v2` size < 6 MB.
- [ ] Every team in the 2026 FBS schedule resolves to an id; unmatched names produce the initials tile, not a broken image.
- [ ] e2e resolution test passes; lint, typecheck, `test:publication`, build and the full Playwright suite pass.
- [ ] 3x light and dark screenshots show sharp logos at 16, 20, 28 and 64–80 px.
- [ ] No runtime request to `espncdn.com` (check the network panel).
- [ ] `docs/status.md` updated; contract marked Implemented.

## Risks and rollback
- **CFBD/ESPN response differs from what was assumed:** the dry run catches this before any download; adjust the parser, not the design.
- **A team has no logo or a 404:** initials-tile fallback; listed in the report.
- **Dark variants missing for some teams:** fall back to the light file for dark mode.
- **Repo growth:** bounded by the < 6 MB check; WebP keeps it small.
- **Rollback:** `git revert` the web-change commit; the old PNGs remain until Phase C step 10.

## Handoff to Terra
Run this at home in a fresh task on `dev`: `git checkout dev && git pull`, then use `.agent/skills/implement-plan/` with this exact path. Needs `CFBD_API_KEY` in `.env` and network access. Start with Phase A step 2's `--dry-run` and stop to review its output before downloading.
