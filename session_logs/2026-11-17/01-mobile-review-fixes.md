# Mobile review fixes (all 18 findings)

Fixes for the 18 findings in `session_logs/2026-11-16/05-mobile-site-review.md`, approved by the owner. Five commits on `worktree-teams-resume-padding`, after the decision log commit `8a879d6f`. Not pushed.

## Commits and findings

| Commit | Findings | Change |
|---|---|---|
| `7728eace` | 1, 11, 14, 16, 18 | `/teams?group=resume` falls back to the SOR sort (`resolveGroupSort`), so the rank is `#1`, not the raw rating. Phone ratings are compact expandable rows. `signedFixed` removes "-0.00". The next-game market line wraps between parts only. The résumé plot has top padding and no `#0` tick (`yTickFilter`); table links are 44px tall. |
| `1c5b392b` | 3, 5, 6, 17 | Rating trend, team game log and season trend measure their container, so labels render at 12px or more. The game log drops "Wk" on phones. The 52.4% label moves to the left end of the break-even line. Method contents is a closed "Contents" disclosure below `lg` and the open sticky column at `lg`. New `use-measured-width.ts` hook. |
| `695a0bd7` | 7, 13 | Scatter x ticks thin until their labels fit; `shortXLabel` for Finishing drives. `shortTabLabel` for the chart picker below 360px; the summary line takes its own row below 360px. |
| `7446bcf3` | 9, 10 | Loss rows shaded with a key on the phone game log. Net success repeats the tick labels at the bottom, narrows the label column below 340px and puts the score on a second line. |
| `66ce7294` | 2, 4, 8, 12, 15 | Filters button only when the sheet has controls. Layout toggle and compact list rows on phones. Kickoff, spread and result header fit at 320px. New `not-found.tsx` (with `ThemeReapply`, so the `dark` class holds). Duplicate "Final: X–Y" chip removed. `run_web_local.sh` defaults to predictions mode. |

Also adjusted by the orchestrator after the first full browser run: `--slate-bar-h` 105px to 108px (the Layout toggle made the phone bar 3px taller), the spread-cell height bound (36px, one line plus padding), `charts-navigation.spec.ts` (picker option is "Explosiveness" below 360px) and `awaiting-result.spec.ts` (asserts "Final").

## Verification

- `make check`: passed.
- `make web-e2e`: 534 passed, 10 skipped; the only failure is the expected `test.fail()` market-board test. Baseline was 502 passed, 10 skipped.
- `PORT=3112 make web-local ENV=production`: `/api/health` reports `mode: predictions`.
- Sweep of 14 pages at 390 light, 390 dark and 320 light on Production data: no horizontal scroll anywhere; every SVG label is 12px or more except the model-page error scatter (below). Dark 404s have `html.dark`, the site header and the title "Page not found". Captures were viewed for Ratings résumé, phone Games list, the dark 404 and Finishing drives at 320.
- `git diff --check`: clean.

## Open items for the owner

1. **Model page error scatter** (`web/src/components/model/ErrorExplorer.tsx`): fixed 320 viewBox with `text-[10px]`, so labels render at 10.4px (390) and 8.2px (320). Not one of the 18 findings; needs the same measured-width treatment.
2. **Matchup gate (finding 15):** not re-reviewed beyond the chip. The "provenance unavailable" gate came from the local server running in market mode; the runner now defaults to predictions. Whether Production Week 11 and 12 matchups should open is a data and release question.
3. **404 app bar title** reads "Team" on `/teams/Not_A_Team` (derived from the path); cosmetic.
4. **Dev server and `.next`:** running `make web-e2e` then a dev server on the same `web/.next` made the browser reload in a loop; deleting `web/.next` fixed it. Not a code bug.
