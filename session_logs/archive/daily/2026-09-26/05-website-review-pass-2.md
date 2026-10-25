# Session: Website review pass 2 (betting-format extraction, breadcrumbs, BetTable guard)

## TL;DR
- **Worked On:** 4 review items: pure-logic extraction + unit tests, unwired-component breadcrumbs, BetTable length guard; item 4 (StatCard props unused) rebutted — both props are live on `/performance`
- **Outcome:** All implemented and verified; one test expectation corrected during verification (away-favorite lines stay negative per market convention)
- **Plan Contract:** N/A (fast path)
- **Approval / Status:** Done, awaiting user commit
- **Blockers:** None
- **Next:** User commits (note: worktree also still holds the prior Tier 1–3 batch if uncommitted — single commit covers both)

## Work Completed
- `web/src/lib/betting-format.ts` (new) — signedSpread, SpreadView, market/modelSpreadView, spreadLabel, spreadEdge, totalEdge, spreadBetLabel, totalBetLabel exported from GameRow verbatim
- `web/src/lib/betting-format.test.ts` (new) — 12 node:test cases on sign-flipping math (home-favorite vs away-flip, PK/null paths, model-minus-market edge, bet-label line handling); wired into `test:publication` script in `web/package.json`
- `GameRow.tsx` — imports from lib; fixed missing `signedSpread` import caught by typecheck
- `RecordBanner.tsx`, `HistoricalModelContext.tsx` — "reserved, do not delete as dead code" breadcrumbs (confirmed unwired: no route imports either)
- `BetTable.tsx` — dev-only throw on `bodyCellClassName[]`/cells length mismatch + JSDoc caller contract

## Validation
- [x] `npm run lint`, `typecheck` clean
- [x] `test:publication` 24/24 (12 existing + 12 new)
- [x] `npm run build` clean; Playwright 8/8 vs production build in fixture mode (`next start` :3100, other session's dev lock avoided)
- [x] `git diff --check` clean; e2e `.last-run.json` debris restored

## Handoff Notes
- **Watch out for:** `test:publication` script now names 3 files explicitly — future `src/lib/*.test.ts` additions must extend it (or switch to a glob)

**Suggested commit message:** `refactor(web): extract betting-format lib with unit tests; guard BetTable columns`

**tags:** ["web", "frontend", "refactor", "tests"]
