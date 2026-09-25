# Session: Simplify V5 site navigation and weekly scoreboard

## TL;DR

- **Worked On:** Simplified the V5 prediction interface following the production replay release.
- **Outcome:** Removed public run-state/evidence labels and replay callouts, replaced the replay/MAE cards with a Spread and Total W–L–P scoreboard plus push-excluded win rates, and reduced public navigation to Predictions.
- **Plan Contract:** N/A (localized web-interface change).
- **Approval / Status:** User directed the interface changes in-session.
- **Blockers:** None.
- **Next:** Review the deployed site after the normal publication workflow.

## Context and Decisions

- `published` and `replay` remain internal run metadata for the serving and audit boundary. They no longer appear in the public forecast header.
- The home-page record reflects completed selected V5 weeks before the week in view. It is named `2026 so far`, so Week 0 shows 0–0–0 and Week 4 shows Weeks 0–3 results. It shows separate Spread and Total records and excludes pushes from win rate.
- The header shows only the season; the week selector owns week context and no longer has a position counter. Performance, Method, and Ratings remain direct routes but are not public navigation items.

## Work Completed

- Removed header badges and the retrospective replay callout from the prediction page.
- Replaced the V5 performance banner with a 2026 season-record scoreboard.
- Reworked the Performance page to use the same spread/total record presentation and removed MAE and coverage from public presentation.
- Replaced replay/live terminology in Method with the model's fixed-through-2025 training boundary and pregame-input description.
- Updated navigation and browser tests for the two-item navigation and season scoreboard.
- Removed Ratings from public navigation after the user deferred that page's design work.
- Changed the record query to exclude the selected week and shortened the market-line note.

## Files Modified

- `web/src/components/Header.tsx` — removed public run-state and evidence-class badges.
- `web/src/components/SiteNav.tsx` — changed Forecasts to Predictions and then hid Ratings from public navigation.
- `web/src/components/V5PerformanceBanner.tsx` — added the per-week season scoreboard.
- `web/src/app/page.tsx` — removed the replay callout and unused metadata plumbing.
- `web/src/lib/v5.ts` — scopes the record to selections before the displayed week.
- `web/src/components/WeekNav.tsx` — removed the week-position counter.
- `web/src/app/performance/page.tsx` — replaced MAE and coverage cards with records and win rates.
- `web/src/app/methodology/page.tsx` — simplified results context.
- `web/e2e/publication.spec.ts` — aligned browser coverage with the new UI.

## Validation

- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run test:publication` — 11 passed.
- [x] `npm run test:ui` — 7 passed.
- [x] `npm run build`
- [x] Local browser verification with `CFB_UI_TEST_MODE=1`: Predictions/Ratings navigation, no public run-state/evidence badges, and the spread/total record card render correctly.
- [x] Local browser verification with the real configured site: Week 0 renders 0–0–0, Week 4 includes 157 prior games, and the main navigation exposes only Predictions.
- [x] `npm run lint` and `npm run typecheck` after the final navigation and selector edits.

## Amendments and Blockers

None.

## Handoff Notes

- **Resume at:** Inspect the deployed Prediction page after its standard publish path runs, then implement the approved best-quote line-selection contract in a fresh task.
- **Watch out for:** Keep evidence class and run state in the serving/audit path even though they are no longer public UI labels.

**Suggested commit message:** `Simplify V5 site navigation and weekly scoreboard`

**tags:** ["web", "v5", "ui", "scoreboard"]
