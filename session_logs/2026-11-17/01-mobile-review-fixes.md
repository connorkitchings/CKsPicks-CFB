# Session: Mobile review fixes (all 18 findings)

## TL;DR

- **Worked On:** The 18 findings in [`05-mobile-site-review.md`](../2026-11-16/05-mobile-site-review.md), plus two follow-ups found while verifying (Model error scatter labels, 320px search placeholder).
- **Outcome:** All 18 findings fixed in five commits, two follow-up commits, and the decision log; merged into local `dev`.
- **Plan Contract:** N/A (fast path; the approved plan lived in the session)
- **Approval / Status:** Owner approved all 18 findings and the three design choices below. Not pushed.
- **Blockers:** None
- **Next:** Owner says when `dev` is ready; then the AGENTS.md "Pushing `dev`" routine.

**tags:** ["web", "mobile", "charts", "e2e"]

## Context and Decisions

- The review server ran `scripts/ops/run_web_local.sh` without `CFB_PUBLICATION_MODE`, so the app fell back to market mode. That caused the empty Filters sheet (2), part of the market-card findings (8) and the matchup "provenance unavailable" gate (15). The runner now defaults to `predictions`; the real bugs were fixed anyway.
- Owner decisions: Ratings phone list is compact rows that expand (11); Games gets a phone List layout with the toggle in the toolbar, cards stay default (12); Method contents is a closed "Contents" disclosure below `lg` and the open sticky column at `lg` (17).
- Phone SVG labels measure their container (new `web/src/lib/use-measured-width.ts`) so the viewBox equals the CSS width and labels render at 12px or more.
- `tabLabel` in the chart registry is unchanged (a test pins it); `shortTabLabel` and `shortXLabel` are additive.
- The Layout toggle stays in the toolbar; at 320px the search field's empty padding and the toggle's padding shrink so the placeholder fits.

## Work Completed

| Commit | Findings | Change |
|---|---|---|
| `8a879d6f` | decisions | Review log decisions set to approved. |
| `7728eace` | 1, 11, 14, 16, 18 | `/teams?group=resume` falls back to the SOR sort (`resolveGroupSort`), so the rank is `#1`, not the raw rating. Phone ratings are compact expandable rows. `signedFixed` removes "-0.00". The next-game market line wraps between parts only. The résumé plot has top padding and no `#0` tick (`yTickFilter`); table links are 44px tall. |
| `1c5b392b` | 3, 5, 6, 17 | Rating trend, team game log and season trend measure their container. The game log drops "Wk" on phones. The 52.4% label moves to the left end of the break-even line. Method contents collapse below `lg`. |
| `695a0bd7` | 7, 13 | Scatter x ticks thin until labels fit; `shortXLabel` for Finishing drives. `shortTabLabel` for the chart picker below 360px; the summary line takes its own row below 360px. |
| `7446bcf3` | 9, 10 | Loss rows shaded with a key on the phone game log. Net success repeats tick labels at the bottom, narrows the label column below 340px and puts the score on a second line. |
| `66ce7294` | 2, 4, 8, 12, 15 | Filters button only when the sheet has controls. Phone Layout toggle and compact list rows. Kickoff, spread and result header fit at 320px. New `not-found.tsx` (with `ThemeReapply`). Duplicate "Final: X–Y" chip removed. Runner defaults to predictions mode. |
| `d76be811` | follow-up | Model error scatter measures its container; 12px labels on phones, shorter axis titles on phones. |
| `0e8f8ca9` | follow-up | 320px search placeholder fits beside the Layout toggle. |

Orchestrator adjustments after the first full browser run: `--slate-bar-h` 105px to 108px (the toggle made the phone bar 3px taller), spread-cell height bound 36px, `charts-navigation.spec.ts` (picker option "Explosiveness" below 360px), `awaiting-result.spec.ts` (asserts "Final").

## Files Modified

- `web/src/components/ratings/*`, `web/src/components/teams/*`, `web/src/lib/{sos-rank,team-games,number-format}.ts` (+ tests) — Ratings hub and team hero.
- `web/src/components/ratings/RatingTimeline.tsx`, `teams/GameLogChart.tsx`, `model/RecordTrendChart.tsx`, `model/ErrorExplorer.tsx`, `web/src/lib/use-measured-width.ts` — measured-width charts.
- `web/src/app/model/method/page.tsx`, `web/src/app/globals.css` — Method contents disclosure.
- `web/src/components/charts/*`, `web/src/app/stats/page.tsx`, `web/src/lib/chart-config.ts` (+ test) — Graphs scatter ticks, toolbar, bar charts.
- `web/src/components/slate/*`, `BetTable.tsx`, `ui/SearchField.tsx`, `matchup/MatchupHero.tsx`, `web/src/lib/time-et.ts` (+ test) — Games cards, phone list, search.
- `web/src/app/not-found.tsx`, `web/src/components/ThemeReapply.tsx` — site 404.
- `scripts/ops/run_web_local.sh` — predictions-mode default.
- `web/e2e/*` (teams, teams-hub, touch-targets, model, mobile-model, mobile-scatter, mobile-chart-picker, charts-navigation, mobile-bars, mobile-games, mobile-slate, publication, matchup, awaiting-result) — new and updated specs.
- `session_logs/2026-11-16/05-mobile-site-review.md` — each finding marked fixed in its commit.

## Validation

- [x] `make check` passes.
- [x] `make web-e2e`: 537 passed, 10 skipped (baseline 502 passed, 10 skipped); the only failure is the expected `test.fail()` market-board test.
- [x] `PORT=3112 make web-local ENV=production`: `/api/health` reports `mode: predictions`.
- [x] Sweep of 14 pages at 390 light, 390 dark and 320 light on Production data: no horizontal scroll; every SVG label 12px or more (the error scatter, then below 12px, was fixed afterwards). Dark 404s have `html.dark`, the site header and "Page not found".
- [x] Production matchups open in predictions mode at 320px (hero, market and model lines, model lean).
- [x] `git diff --check`

## Amendments and Blockers

- None. Not reviewed visually: a final game's forecast card, charts and export; the compact ratings list, team-page, Method and Net success captures were covered by the automated probes only.

## Handoff Notes

- **Resume at:** Session complete. Push `dev` only when the owner says so (AGENTS.md "Pushing `dev`").
- **Watch out for:** The 404 app bar reads "Team" on `/teams/Not_A_Team` (cosmetic). Running `make web-e2e` and a dev server on the same `web/.next` makes the browser reload in a loop; delete `web/.next` first.
