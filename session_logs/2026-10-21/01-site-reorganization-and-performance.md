# 2026-10-21 — Site reorganization, design consistency and performance (Phases 1-4 on dev)

Implements [Site reorganization, design consistency and performance](../../docs/plans/2026-10-21/01-site-reorganization-and-performance.md) and the [Stats publication log](../../docs/plans/2026-10-21/02-stats-publication-implementation-log.md). Commits `a57bb603` through `f7a80399` on `dev` (pushed), followed by independent-review fixes.

## Outcome

- **Phase 1, performance:** release-keyed caching of release-scoped reads, a cached release pointer, query consolidation and smaller page payloads. Local warm median timings, cache off to on: `/` 637 to 9 ms, `/ratings` 782 to 12 ms, `/results` 518 to 10 ms, `/performance` 384 to 10 ms, `/matchup/<id>` 1356 to 99 ms. A warm `/` runs 0 queries; 1 query after the pointer expires. Vercel was not measured.
- **Phase 2, design system:** shared `Card`, `Notice` and `PageShell` primitives replace per-page markup.
- **Phase 3, organization:** four tabs (Games, Ratings, Stats, Model); old URLs redirect with 307; team links to `/teams/[team]`; the Games routes live in the `app/(games)` route group so unknown routes get real 404s past the root `loading.tsx`; `matchup/[gameId]` and `teams/[team]` have their own layouts.
- **Phase 4, Stats publication:** weekly runbook section and edge-state tests; Stats stays gated by `CFB_CHARTS_ENABLED`.
- **Rank color scale:** one continuous green-to-red scale over ranks 1-138, lowest rank greenest, including SOS; shared `RankChip`; the `test:publication` script typo was fixed.
- **CI fixes:** Postgres test harness uses one query, the manifest path was corrected, the share tooltip overflow was fixed.

## Decisions

- Owner: the first tab is named Games (not Matchups).
- Review fixes after the pushed work: the Model method page now states the retrospective benchmark fallback; the week record block on Games appears only when at least one pick has a recorded grade (previously any final score, which could show 0-0-0); status and plan docs updated.

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
- Review fixes (uncommitted): `web/src/app/model/method/page.tsx`, `web/src/lib/slate.ts` (`hasGradedPick`), `web/src/components/slate/SlateView.tsx`, `web/src/lib/slate.test.ts`, `docs/status.md`, the plan, `docs/plans/index.md`, this log.

## Validation

- `lint`, `typecheck` and `test:publication` for the review fixes: see the final report of that work.
- Local route timings above came from the measurement script against a local database.

## Not verified

- Vercel cache behavior and production timings.
- The bundle-size claim for `charts.ts`.
- Teams with legacy names against the real database.
- The older-browser disclosure.
- The real-data Stats review and Preview acceptance.

## Open follow-ups

- The share card still uses the old rank tiers.
- The `#` column color follows sort position.
- The tab bar shifts width between pages.
- 307 to 308 and the canonical domain.
- The Model copy "52.4%" is sourced from `docs/modeling/betting_policy.md`.
- A cold matchup page shows no skeleton.
