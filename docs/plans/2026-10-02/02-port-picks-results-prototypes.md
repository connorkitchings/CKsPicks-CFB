# Port Picks/Results Prototypes to Production

- **Status:** Approved
- **Created:** 2026-10-02
- **Planner:** Sol
- **Approval source:** User approved the port framework and the five gap resolutions in planning session `session_logs/2026-10-02/04-port-picks-results-prototypes-planning.md`, with one implementation note (preserve `EdgeNote`/`edgeTone`; see Amendment 1).
- **Implementation log:** Pending (Terra)
- **Commit policy:** Separate plan commit (recommended — multi-session web change); user executes git operations manually.

## Goal

Replace the production Picks (`/`) and Results (`/results`) slate UI — `WeeklySlateView` + `GamesList` + `GameRow` market/model table cards — with the lean-sentence design proven in the gated `/test-picks` and `/test-results` prototypes, then delete the prototype routes and superseded components.

Success: city/state venues, sportsbook best lines, Top Leans, ModelRecord, result filters, and lean-sentence cards are visible on the production Picks/Results pages; no `/test-*` routes remain; no dual implementation is maintained; fail-closed market mode still renders with zero model output.

## Current State

- `web/src/components/picks-proto/` (18 components) + `web/src/lib/picks-proto.ts` (351 lines) serve the gated prototypes. `/test-picks` and `/test-results` 404 in production unless `CFB_ENABLE_TEST_PAGE=1`; unlinked from nav; `noindex`.
- Prototype coverage is the strongest in the repo: 280 lines of unit tests (`picks-proto.test.ts`, in `test:publication`) and 25+ Playwright checks (`prototypes.spec.ts`), including 360px phone-fit and no-truncation assertions.
- Production currently serves `WeeklySlateView` → `Header` + `SiteNav` + `V5PerformanceBanner` + `WeekNav` + `GamesList` → per-game `GameRow` (`MarketGameRow` in market mode) with a Market/Model/Model-Bet/Result table.
- Data is already live for the headline features: venue city/state (`game_venues`, 271 games, migration 0019) and sportsbook sources (`spreadSource`/`totalSource` from Neon selections) are returned by `getGamesForWeek`.
- Deliberate divergences to preserve: production removed `#N` rank badges from cards on 2026-10-01 (misleading unofficial ranks); `MatchupButton` is already on both production and prototype cards (gated by `CFB_MATCHUP_ENABLED`).
- Verified during planning: `overallRanks` (lib) is used only by the two `/test` pages (`matchup.ts` has its own local ranker), so it is deletable with them. `StatCard` (used by `RecordBanner`) and `BetTable` (used by the market card) survive. `loading.tsx` and a `ratings.test.ts` source-text assertion reference the old cards and need updates.

## Proposed Approach

Single unified contract porting `/` and `/results` together. No phased bridge adapters: the prototype's shared core (`PicksSlate`/`ResultsSlate`, cards, `ModelRecord`, slate lib) moves 1:1, the five known gaps are resolved as decided below, and the old stack is deleted in the same contract. Web-only, display-layer change; no data, model, ops, or Week 5 frozen-state impact.

## Scope

### Included

- Promote `picks-proto/` to `web/src/components/slate/` with renames (below) and rank-badge removal.
- Integrate the new `SlateView` shell + `ModelRecord` + `TopLeans`/`ResultHighlights` into `app/page.tsx` and `app/results/page.tsx` (keeping ISR `revalidate = 300`).
- Fail-closed market-mode card path in the new slates.
- Test migration (`publication.spec.ts` rewrite, `prototypes.spec.ts` folded in and deleted, `ratings.test.ts` assertion moved, `logos.spec.ts` verified).
- Deletion of prototype routes, gate, and superseded components; `SiteNav` `/test` special-case removal.
- Docs updates (route table, flags, status paragraph).

### Excluded

- `CFB_MATCHUP_ENABLED=1` flip (separate approval).
- Adopting `ProtoHeader` globally; /performance, /ratings, /teams, /methodology untouched.
- Any pipeline, Neon, R2, or run-state changes.

## Affected Components and Contracts

- `web/src/components/slate/` (new): `SlateView.tsx`, `PicksSlate.tsx`, `ResultsSlate.tsx`, `SlateGameCard.tsx`, `SlateGameRow.tsx`, `ResultGameCard.tsx`, `ResultGameRow.tsx`, `MarketGameCard.tsx`, `ModelRecord.tsx`, `TopLeans.tsx`, `TeamPair.tsx`, `GameWhen.tsx`, `LeanPill.tsx`, `LeanMarker.tsx`, `ResultBadge.tsx`, `ResultLeanRow.tsx`, `ResultHighlights.tsx`, `format.ts`, status row.
- `web/src/lib/slate.ts` (renamed from `picks-proto.ts`), `web/src/lib/slate.test.ts`, `web/package.json` `test:publication` list.
- `web/src/test/fixtures/slate.ts` (renamed from `picks-prototype.ts`), extended with `weeks`/`scoredWeeks` for `CFB_UI_TEST_MODE=1`.
- `web/src/app/page.tsx`, `web/src/app/results/page.tsx`, `web/src/app/loading.tsx`, `web/src/components/SiteNav.tsx`.
- Deleted: `web/src/app/test-picks/`, `web/src/app/test-results/`, `web/src/lib/proto-gate.ts`, `web/src/components/picks-proto/`, `WeeklySlateView.tsx`, `GamesList.tsx`, `GameRow.tsx`, `V5PerformanceBanner.tsx`, `BetComparisonTable.tsx` (after Amendment 1 extraction; verify unreferenced).
- Docs: `web/README.md`, `AGENTS.md`, `.codex/QUICKSTART.md`, `docs/status.md`.

## Implementation Tasks

### Task 1 — Promote and normalize slate components

**Files:**

- `web/src/components/slate/*` (moved from `picks-proto/`, renames above)
- `web/src/lib/slate.ts`, `web/src/lib/slate.test.ts`, `web/package.json`

**Changes:**

- Rename components per the list; keep `ModelRecord`, `TopLeans`, `TeamPair`, `GameWhen`, `LeanPill`, `LeanMarker`, `ResultBadge`, `ResultLeanRow`, `ResultHighlights`, `format.ts` names. Move `MarketGameRow` from `GameRow.tsx` to `slate/MarketGameCard.tsx` with DOM unchanged.
- Delete `ranks` props from `TeamPair`/`TeamLine`, cards, rows, slates, and pages — no `#N` on slate cards.
- Delete `overallRanks` from the slate lib and drop the pages' `getCurrentRatings` query (`matchup.ts` ranking is independent).
- New page-local status row (run-state label + "Retrospective replay" chip, ported from `ProtoHeader`'s second row); global `Header` + `SiteNav` unchanged; `WeekNav` unchanged.

**Acceptance criteria:**

- `slate/` builds standalone; `test:publication` list updated and passing; no `picks-proto` imports remain outside the deleted pages.

**Validation:**

- `cd web && npm run lint && npm run typecheck && npm run test:publication`

### Task 2 — Integrate `/` and `/results`

**Files:**

- `web/src/components/slate/SlateView.tsx` (new server shell)
- `web/src/app/page.tsx`, `web/src/app/results/page.tsx`, `web/src/app/loading.tsx`
- `web/src/test/fixtures/slate.ts`

**Changes:**

- `SlateView` composes: `Header` + status row, `WeekNav`, dbError/empty/retrospective-repair notes (ported from `WeeklySlateView`), `ModelRecord` (Results adds the `weekRecord` week block), `TopLeans` (Picks only) / `ResultHighlights` (Results only), `PicksSlate`/`ResultsSlate`, `Footer`.
- Both pages keep `revalidate = 300`. 2-column grid, `max-w-6xl`, grid/list toggle, leans-only + edge sorts (Picks), result filters + biggest-hit/miss sorts (Results), anchor `id="game-<id>"` for Top Leans links.
- Market fail-closed: any game with `publicationMode === "market"` renders `MarketGameCard`; lean controls hidden when the slate has no predictions games (mirror current `predictionsVisible` logic). Existing `retrospectiveRepair` page logic retained.
- Test mode: predictions mode serves the slate fixtures; market mode keeps `uiFixture`.
- `MatchupButton` retained on all cards (no flag change).

**Acceptance criteria:**

- `/?mode=predictions` shows lean-sentence cards with venues, best lines, Top Leans, ModelRecord; `/results?mode=predictions` shows week + season records, Highlights, filters; both `?mode=market` variants render market-only cards with no model numbers; `loading.tsx` mirrors the new sections.

**Validation:**

- `CFB_UI_TEST_MODE=1 npm run build`; real-data visual check via `make web-local` on `/` and `/results` (light/dark, 390px phone).

### Task 3 — Test migration, deprecation, docs

**Files:**

- `web/e2e/publication.spec.ts`, `web/e2e/prototypes.spec.ts` (fold in, delete), `web/src/lib/ratings.test.ts`, `web/e2e/logos.spec.ts` (verify)
- Deletions listed in Affected Components
- `web/src/components/SiteNav.tsx`, `web/README.md`, `AGENTS.md`, `.codex/QUICKSTART.md`, `docs/status.md`, `docs/plans/index.md`

**Changes:**

- Rewrite `publication.spec.ts` predictions assertions to the lean-sentence DOM; merge `prototypes.spec.ts` checks onto `/` and `/results`; move the `ratings.test.ts` GameRow source-text assertion to `TeamPair`; verify logo checks pass on the new cards.
- Delete prototype routes, gate, old stack, and (after Amendment 1) `BetComparisonTable.tsx`; remove the `SiteNav` `/test` special case.
- Update docs: drop `/test-picks` + `/test-results` from `web/README.md` route table; remove `CFB_ENABLE_TEST_PAGE` references in `AGENTS.md` and `.codex/QUICKSTART.md`; rewrite the `docs/status.md` release-state paragraph (city/state + sportsbook now visible on production cards).

**Acceptance criteria:**

- Zero references to `picks-proto`, `test-picks`, `test-results`, `proto-gate`, `CFB_ENABLE_TEST_PAGE`, `WeeklySlateView`, `GamesList`, `V5PerformanceBanner` (outside history) in code, tests, and the updated docs; full Playwright suite green.

**Validation:**

- `cd web && npm run lint && npm run typecheck && npm run test:publication`; full Playwright run; `make contracts-check`; `git diff --check`.

## Testing Strategy

- Unit: `slate.test.ts` (lean math, sorts, records, filters, `edgeTone` after extraction, no invented books for missing sources).
- E2E (fixture mode): lean-sentence rendering, bank of edge cases from `prototypes.spec.ts` (record/bars, top leans, filters, sorts, grid/list, venue variants, 360/390px fit, no-truncation, trademark footer), market-mode fail-closed on both pages, week redirects.
- E2E (real data via `make web-local`): `/` and `/results` screenshots, light + dark, phone width.
- Regression: `logos.spec.ts`, `matchup.spec.ts` unchanged and green; `make contracts-check`.

## Risks and Edge Cases

- Mixed-mode slates (market-mode games inside a predictions slate) must render the market card, never vanish (the prototype filtered them out — guarded here by the per-game branch).
- Non-V5 (rollback) runs yield empty performance → no `ModelRecord`, same as today's banner gating.
- Long team names/locations must wrap or truncate-titled, never clip (keep `data-pick` e2e checks).
- Another session is active on `dev`; coordinate so no concurrent edits land in `web/src/app/page.tsx`, `web/src/app/results/page.tsx`, or the slate components during Terra's run. Worktree was clean at planning time.
- No season/week/publication values in this contract are instructions to run pipeline steps; `AS_OF` choreography is out of scope.

## Definition of Done

- [ ] Tasks 1–3 and all acceptance criteria complete (including Amendment 1).
- [ ] Web lint, typecheck, `test:publication`, fixture-mode build, full Playwright suite, `make contracts-check`, `git diff --check` all pass; real-data screenshots reviewed.
- [ ] Prototype routes, gate, and old stack deleted; `docs/status.md` updated; contract status set to `Implemented`.
- [ ] Session log written; commit message proposed (user executes git).

## Amendments

### Amendment 1 — Preserve `EdgeNote`/`edgeTone` before deleting `BetComparisonTable.tsx`

**Reason:** User implementation note at approval: `edgeTone`/`EdgeNote` exist only in `BetComparisonTable.tsx` and would be lost in the Phase 3 deletion.

**Original approach:** Delete `BetComparisonTable.tsx` once `GameRow.tsx` is gone.

**Revised approach:** Before deleting it, extract `edgeTone`/`EdgeNote` into `components/slate/` — share the edge-threshold tone logic with the lean-sentence edge display where adopted, and keep the pure `edgeTone` function under unit test regardless.

**Impact:** One extra move in Task 3; no change to scope or acceptance criteria.
