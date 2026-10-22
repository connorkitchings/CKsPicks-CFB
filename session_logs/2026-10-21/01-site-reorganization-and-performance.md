# 2026-10-21 — Site reorganization, design consistency and performance (Phases 1-4 on dev)

Implements [Site reorganization, design consistency and performance](../../docs/plans/2026-10-21/01-site-reorganization-and-performance.md) and the [Stats publication log](../../docs/plans/2026-10-21/02-stats-publication-implementation-log.md). Commits `a57bb603` through `d1c3ed04` on `dev` (pushed). Two independent reviews followed the first push; their findings are fixed in `69c7713b` and `d1c3ed04`.

## Outcome

- **Phase 1, performance:** release-keyed caching of release-scoped reads, a cached release pointer, query consolidation and smaller page payloads. Local warm median timings, cache off to on: `/` 637 to 9 ms, `/ratings` 782 to 12 ms, `/results` 518 to 10 ms, `/performance` 384 to 10 ms, `/matchup/<id>` 1356 to 99 ms. A warm `/` runs 0 queries; 1 query after the pointer expires. Vercel was not measured.
- **Phase 2, design system:** shared `Card`, `Notice` and `PageShell` primitives replace per-page markup.
- **Phase 3, organization:** four tabs (Games, Ratings, Stats, Model); old URLs redirect with 307; team links to `/teams/[team]`; the Games routes live in the `app/(games)` route group so unknown routes get real 404s past the root `loading.tsx`; `matchup/[gameId]` and `teams/[team]` have their own layouts.
- **Phase 4, Stats publication:** weekly runbook section and edge-state tests; Stats stays gated by `CFB_CHARTS_ENABLED`.
- **Rank color scale:** one continuous green-to-red scale over ranks 1-138, lowest rank greenest, including SOS; shared `RankChip`; the `test:publication` script typo was fixed.
- **CI fixes:** Postgres test harness uses one query, the manifest path was corrected, the share tooltip overflow was fixed.

## Decisions

- Owner: the first tab is named Games (not Matchups).
- First review: the Model method page now states the retrospective benchmark fallback; the week record block on Games appears only when at least one pick has a recorded grade (previously any final score, which could show 0-0-0); status and plan docs updated.
- First review, cache: `unstable_cache` revalidation is stale-while-revalidate, so a new release could stay hidden after the TTL. Cache keys now carry a time bucket (60 s for the release pointer, 3600 s for run-state loaders) so the first request after the TTL blocks on one query.
- Second review: each loader read the clock itself, so a request crossing a bucket boundary could store old data under the new bucket. One clock reading is now pinned per request (`request-clock.ts`), so staleness is bounded by one bucket.
- Team-page reads (`getTeamHistory`, `getTeamGames`) are release-cached with the 3600 s cap; callers must pass names resolved by `resolveTeam`.
- The measurement script defaults to `/`, `/ratings`, `/model`, `/model/method`, `/stats` and a discovered matchup; any non-200 fails the run. A reviewer ran it against a local production-mode server and confirmed this.

## Files changed, by commit

- `a57bb603` docs(plans): the plan contract.
- `75dd1140` perf(web): release-scoped cache, pointer, queries, bundle trimming.
- `5e7aa05c` fix(web): route measurement script times the full body.
- `bff11ecf` refactor(web): `Card`, `Notice`, `PageShell`, `ButtonLink`, loading and error pages, adoption across slate, ratings, matchup, charts.
- `fe346e24` feat(web): `SlateView`/`SlateList` merge of Picks and Results, `/model` and `/model/method`, `/stats`, `SiteNav`, redirects in `next.config.ts`, team links, loading skeletons, `AGENTS.md`, runbook and plan docs, e2e specs.
- `1562b071` docs(ops): Stats publication runbook, implementation log, edge-state tests.
- `07d12aec` fix(web): 404 for unknown game ids (`matchup-id.ts`, layout), method copy trimmed.
- `76d923b7` fix(ci): `tests/test_season_release_postgres.py`, `conf/repository/compatibility_v1.yaml`, share tooltip and `ExportActions` overflow.
- `f7a80399` feat(web): `rank-color.ts`, `RankChip.tsx`, `globals.css` scale, ratings and matchup tables.
- `69c7713b` fix(web): time buckets in cache keys and `releaseCached`, `season-release.ts` pointer key, `v5.ts` team caching, `measure-routes.mjs`, `model/method/page.tsx`, `slate.ts` (`hasGradedPick`), `SlateView.tsx`, `slate.test.ts`, `docs/status.md`, the plan, `docs/plans/index.md`, this log.
- `d1c3ed04` fix(web): `request-clock.ts` (new), `release-cache.ts`, `season-release.ts`, `release-cache.test.ts` (boundary-crossing tests).

## Validation

- On the final code (`d1c3ed04`), run by the implementing worker: `lint`, `typecheck`, `test:publication` (319 pass, 1 skipped), `build`, `test:ui` (188 passed, 10 skipped), `test:charts-gate` (21 passed), `git diff --check`. Earlier combined runs also passed `make contracts-check` and `mkdocs build --strict`.
- CI: run 39695504822 on `f7a80399` passed (the three earlier failures are resolved). The run on `d1c3ed04` was still in progress when this log was written.
- Local route timings above came from the measurement script against a local database.

## Blockers

- The plan stays `In Progress`: acceptance needs real-data and Preview evidence that fixtures cannot provide.

## Not verified

- Vercel cache behavior and production timings.
- The bundle-size claim for `charts.ts`.
- Teams with legacy names against the real database.
- The older-browser disclosure.
- The per-request clock pin inside a live Next request (tested with a stand-in memo, not React `cache()` itself); `/api/health` is the only route handler calling these loaders and gets a fresh reading per call.
- The real-data Stats review and Preview acceptance.

## Open follow-ups

- The share card still uses the old rank tiers.
- The `#` column color follows sort position.
- The tab bar shifts width between pages.
- 307 to 308 and the canonical domain.
- The Model copy "52.4%" is sourced from `docs/modeling/betting_policy.md`.
- A cold matchup page shows no skeleton.

## Next step

1. Check the CI result on `d1c3ed04`: `gh run list --branch dev --limit 1`.
2. Test on a Vercel Preview of `dev`, with `CFB_CHARTS_ENABLED=1` on Preview only: Games on an upcoming, a final and an in-progress week; every redirect; the nine legacy-name team pages; light and dark at 390px and 1280px.
3. Run `node web/scripts/measure-routes.mjs <preview-url> --runs 10` twice, and record the numbers and the Stats real-data review in the [Stats publication log](../../docs/plans/2026-10-21/02-stats-publication-implementation-log.md).
4. After acceptance: owner sets `CFB_CHARTS_ENABLED=1` on Production per the runbook; later switch redirects from 307 to 308 after confirming the canonical domain.
5. Remove the seven session worktrees and branches under `.claude/worktrees/` once nothing needs them.
