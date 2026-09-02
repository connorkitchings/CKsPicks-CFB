# Session: 2026 Record & Weekly Context Redesign

## TL;DR

- **Worked On:** Selected-week record snapshots, top-level record presentation,
  responsive game comparison cards, and production deployment verification.
- **Outcome:** Implementation is complete, deployed, and verified on the
  public Week 1 view.
- **Plan Contract:** `docs/plans/2026-09-02/2026-record-weekly-context-redesign.md`
- **Approval / Status:** User explicitly authorized implementation and
  deployment on 2026-09-02. Contract is `Implemented`.
- **Blockers:** None.
- **Next:** Continue normal weekly web and publication operations.

## Context and Decisions

- The public season remains environment-controlled and defaults to 2026.
- Records are now read from the latest immutable `scored` run for every week
  through the selected view, rather than from current `system_stats`.
- The top summary uses W-L-P plus hit rate; it deliberately omits ROI and the
  -110 assumption.
- Weekly model context was removed because the historical artifacts do not
  contain immutable market lines and grades that could support a truthful
  historical W-L display.
- Desktop keeps all five comparison columns. Phone cards use Market, Model,
  and Bet, with any final result attached to the Bet column.
- Model-versus-market edge values are color-tiered by absolute magnitude:
  totals use red below 2, yellow through 7, and green above 7; spreads use
  red below 3, yellow through 8, and green above 8.

## Work Completed

- Added `getSystemStatsThroughWeek()` to choose the latest scored run per
  included week and total immutable grade results.
- Reworked the record banner for explicit selected-week cutoff/no-results
  states.
- Removed the weekly model-context panel after determining that its available
  historic values could not support the requested model W-L display.
- Added a phone-only comparison table and maintained desktop/market fail-closed
  behavior.
- Added light/dark semantic edge-color tokens without reusing win/loss result
  colors; edge direction remains encoded by the signed value.
- Updated fixture route/cutoff data and browser tests for the new UI.
- Added a keyboard skip link and `min-w-0` team-name containment.

## Files Modified

- `web/src/lib/queries.ts` — selected-week immutable record query.
- `web/src/app/page.tsx` — selected-week data path and skip link.
- `web/src/components/RecordBanner.tsx` — redesigned record presentation.
- `web/src/components/ModelAccuracyPanel.tsx` — removed weekly model context.
- `web/src/components/GameRow.tsx` — responsive comparison tables and edge tiers.
- `web/src/app/globals.css` — semantic light/dark edge-color tokens.
- `web/src/test/fixtures/publication.ts` and `web/e2e/publication.spec.ts` —
  updated UI fixtures and coverage.
- `docs/plans/2026-09-02/2026-record-weekly-context-redesign.md` — durable
  implementation contract.

## Validation

- [x] `npm run lint` (web)
- [x] `npm run typecheck` (web)
- [x] `npm run test:publication` (web) — 3 passed
- [x] `npm run test:ui` (web) — 4 passed at 375px, 420px, and desktop
- [x] `npm run build` (web)
- [x] `git diff --check`
- [x] Local desktop and 375px fixture visual inspection
- [x] Edge-color amendment: `npm run lint`, `npm run typecheck`,
  `npm run test:publication`, and `git diff --check` (web)
- [x] Confirmed the running local stylesheet emits all three explicit edge
  tiers after a localhost refresh.
- [x] Selected-week context amendment: `npm run lint`, `npm run typecheck`,
  `npm run test:publication`, Python syntax compilation, and `git diff --check`.
- [x] Confirmed the running local Week 1 HTML contains only the 2025/2024
  selected-week history table and its average-miss values.
- [x] Weekly-context removal: `npm run lint`, `npm run typecheck`,
  `npm run test:publication`, `git diff --check`, and localhost render check.
- [x] Production deployment `dpl_CaEcLCU4SYRGAy8PEXgstcYup5KS` — Ready.
- [x] Production Week 1 visual check — selected-week record is topmost,
  weekly context is absent, and the comparison table renders 43 games.

## Amendments and Blockers

- Amendment: removed the weekly model-context panel after confirming that the
  historic artifacts contain neither immutable market lines nor line-dependent
  model grades for a truthful W-L display.
- Amendment: replaced route-level model context with selected-week 2025/2024
  historical results at the user's request.
- Amendment: added magnitude-based model-versus-market edge colors. The
  Playwright suite was not rerun after this incremental change because the
  active local review server holds Next’s shared `.next` lock; stopping it was
  avoided so the user’s local review remains available.
- Production deployment is Ready at `https://c-ks-picks-cfb.vercel.app`; the
  live Week 1 page was visually verified after deployment.

## Handoff Notes

- **Resume at:** Continue normal weekly publishing operations; no remaining
  implementation work for this contract.
- **Watch out for:** `system_stats` remains a latest-season pipeline aggregate;
  the web snapshot must continue to use `prediction_runs` plus
  `prediction_grades` for historic views.

**tags:** ["web", "ui", "records", "publication"]
