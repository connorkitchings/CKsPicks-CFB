# Web read performance

- **Status:** Draft
- **Created:** 2026-10-29
- **Approval source:** Owner accepted the web read performance track in the 2026-10-29 review of the [data architecture blueprint](../../planning/data_architecture_blueprint.md). Implementation requires approval or authorization of this exact path.
- **Implementation log:** `session_logs/YYYY-MM-DD/NN-web-read-performance.md` (create in the implementation session)
- **Commit policy:** Separate plan commit; owner controls staging, commits, pushes and releases.

## Goal

Make the display pages fast on Vercel without changing what they show. This is a web-side track that runs in parallel with [Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md). The read-shaped projections it eventually depends on belong to the shared-facts work in the blueprint (item 4 in its sequence) and need an additive projection set, which this contract does not authorize.

## Findings

Static findings were re-verified against `dev` (`ec86d877`) on 2026-10-29; the timings below are earlier local measurements and are not re-run.

- **Production TTFB has never been measured.** Local warm TTFB through the release-keyed data cache is 9–99 ms.
- **ISR does nothing on most pages.** `revalidate = 300` is exported by `app/(games)/page.tsx` (`/`), `app/ratings/page.tsx`, `app/stats/page.tsx` and `app/matchup/[gameId]/page.tsx`, but each awaits `searchParams`, which makes the route dynamic. `/` reads real parameters (`week`, publication mode), as do `/ratings` and `/stats`. `/matchup/[gameId]` reads it only for the `?now=` UI-test override. `app/teams/[team]/page.tsx` already avoids this by reading `searchParams` only when `isUiTestMode()`, and is the pattern to copy. `/model` is `force-dynamic` by design, so ISR does not apply to it. This has been known since the [2026-10-21 plan](../2026-10-21/01-site-reorganization-and-performance.md).
- **The matchup page is the slowest route:** 1,356 ms cold and 99 ms warm locally. `getMatchupData` (`lib/matchup.ts`) is not in the release data cache (React `cache` only) and fetches the whole week's slate through `getGamesForWeek` or `getMarketGamesForWeek` to find one game. The count of 4 dependent query stages comes from the earlier measurement session; re-count it when implementing.
- **The data cache starts empty after every deploy** because the deployment id is part of the cache key (`release-cache.ts`, `deploymentId`).
- **Correlated subqueries run per row** for grades and market selections. `getV5PerformanceDetail` runs 4 per row across the season, and its cache entry grows toward Vercel's roughly 2 MB per-entry limit.
- **Some results are rebuilt in JavaScript on each cache miss:** season W-L-P from raw grades, team records as of each kickoff, and lines and leans re-derived from snapshots.

Relevant files: `web/src/lib/{season-release,release-cache,matchup,queries,v5}.ts`.

## Ordered changes

1. **Measure first.** Record production (or Preview) TTFB for `/`, `/ratings`, `/stats`, `/matchup` and `/model`, cold and warm, in the implementation log. Later changes are judged against this baseline; if it shows no problem, stop and amend.
2. **Matchup loader.** Put `getMatchupData` in the release data cache and load only the requested game instead of the whole week's slate. Reduce the dependent query stages where independent queries can run together. Output must be identical for existing games.
3. **ISR decision.** Start with `/matchup/[gameId]`: read `searchParams` only under `isUiTestMode()`, as `teams/[team]` does, which should make its `revalidate` effective. For `/`, `/ratings` and `/stats`, which use real parameters, either restructure so static/ISR applies (for example, move the parameter to a path segment or a client-side filter) or remove the ineffective `revalidate` export and document that the page is dynamic. Do not change URLs without an explicit redirect plan.
4. **Cache key.** Evaluate a cache key that does not include the deployment id, so the cache survives deploys. Correctness depends on the release id remaining in the key; stale-data risk must be analysed and tested before adopting.
5. **`/model` entry size.** Measure the cached `getV5PerformanceDetail` entry and add a check or alert threshold well under the roughly 2 MB limit. Reducing it via read-shaped projections is deferred to the shared-facts work.

## Constraints and validation

No schema, migration, Python pipeline, release or model change. Existing displayed values stay byte-identical: add tests (or snapshot comparisons) of loader output before and after. Use the project's Make targets for web checks. Required checks: focused unit tests, `make check` and `make web-e2e` before any web release. Measurements are made against Preview or Production only with the owner's authorization for that operation.

## Handoff

**Stop gates:** measurements show no meaningful production latency problem; a change would alter displayed values; the cache-key change risks serving data from the wrong release. State expected/actual and propose the smallest amendment.

**Operation boundary:** this contract authorizes no deploy, release activation or production load testing.
