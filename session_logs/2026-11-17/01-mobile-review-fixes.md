# Mobile review fixes (all 18 findings)

Fixes for the 18 findings in `session_logs/2026-11-16/05-mobile-site-review.md`, approved by the owner. Seven commits on `worktree-teams-resume-padding` (five fixes, then two follow-ups), after the decision log commit `8a879d6f`. Not pushed.

## Commits and findings

| Commit | Findings | Change |
|---|---|---|
| `7728eace` | 1, 11, 14, 16, 18 | `/teams?group=resume` falls back to the SOR sort (`resolveGroupSort`), so the rank is `#1`, not the raw rating. Phone ratings are compact expandable rows. `signedFixed` removes "-0.00". The next-game market line wraps between parts only. The résumé plot has top padding and no `#0` tick (`yTickFilter`); table links are 44px tall. |
| `1c5b392b` | 3, 5, 6, 17 | Rating trend, team game log and season trend measure their container, so labels render at 12px or more. The game log drops "Wk" on phones. The 52.4% label moves to the left end of the break-even line. Method contents is a closed "Contents" disclosure below `lg` and the open sticky column at `lg`. New `use-measured-width.ts` hook. |
| `695a0bd7` | 7, 13 | Scatter x ticks thin until their labels fit; `shortXLabel` for Finishing drives. `shortTabLabel` for the chart picker below 360px; the summary line takes its own row below 360px. |
| `7446bcf3` | 9, 10 | Loss rows shaded with a key on the phone game log. Net success repeats the tick labels at the bottom, narrows the label column below 340px and puts the score on a second line. |
| `66ce7294` | 2, 4, 8, 12, 15 | Filters button only when the sheet has controls. Layout toggle and compact list rows on phones. Kickoff, spread and result header fit at 320px. New `not-found.tsx` (with `ThemeReapply`, so the `dark` class holds). Duplicate "Final: X–Y" chip removed. `run_web_local.sh` defaults to predictions mode. |
| `d76be811` | follow-up | Model error scatter measures its container, so labels render at 12px on phones (shorter axis titles on phones). |
| next commit | follow-up | At 320px the team search no longer clips its placeholder beside the Layout toggle (empty-field right padding and toggle padding shrink below 360px). |

Also adjusted by the orchestrator after the first full browser run: `--slate-bar-h` 105px to 108px (the Layout toggle made the phone bar 3px taller), the spread-cell height bound (36px, one line plus padding), `charts-navigation.spec.ts` (picker option is "Explosiveness" below 360px) and `awaiting-result.spec.ts` (asserts "Final").

## Verification

- `make check`: passed.
- `make web-e2e`: 537 passed, 10 skipped (baseline 502 passed, 10 skipped); the only failure is the expected `test.fail()` market-board test.
- `PORT=3112 make web-local ENV=production`: `/api/health` reports `mode: predictions`.
- Sweep of 14 pages at 390 light, 390 dark and 320 light on Production data: no horizontal scroll anywhere; every SVG label was 12px or more except the model-page error scatter, fixed afterwards. Dark 404s have `html.dark`, the site header and the title "Page not found". Captures were viewed for Ratings résumé, phone Games list, the dark 404 and Finishing drives at 320.
- `git diff --check`: clean.

## Resolved after review

- **Model error scatter:** fixed in `d76be811`.
- **Matchup gate (finding 15):** with the runner in predictions mode, Production matchups open normally (hero, market and model lines, model lean, "What stands out") at 320px. The earlier gate came from the local server's market-mode fallback. A final game's forecast card, charts and export were not reviewed.
- **Layout toggle:** kept in the toolbar; the 320px search placeholder fits.

Latest suite: `make web-e2e` 537 passed, 10 skipped, plus the expected market-board failure; `make check` passes.

## Open items for the owner

1. **404 app bar title** reads "Team" on `/teams/Not_A_Team` (derived from the path); cosmetic.
2. **Dev server and `.next`:** running `make web-e2e` then a dev server on the same `web/.next` made the browser reload in a loop; deleting `web/.next` fixed it. Not a code bug.
3. **Integration:** unpushed; fast-forward and worktree removal once the owner's remaining work is done.
