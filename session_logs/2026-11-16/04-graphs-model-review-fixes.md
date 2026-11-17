# Graphs and Model review fixes

Branch `worktree-teams-resume-padding` (based on `dev`, includes the résumé-padding commit `92d8ac9a`).

## Commits
- `dbd70274` fix(web): define PPA and tidy scatter labels on the Graphs page
- `114b00f1` fix(web): correct model method copy and align the record trend scales
- `381e6f2d` feat(web): add tables, an outlier break and a logo key to Graphs bar charts

## What changed
- **Scatter wording:** "Yards per success" toggle and axis labels; EPA replaced by PPA in the Downs chart with PPA defined in the Downs and Possession footnotes; Downs quadrant captions in sentence case.
- **Bar charts:** net success axis capped at 1.25 × the second-largest bar per side, with a break mark and true value on the outlier (`netSuccessCap` in `web/src/lib/charts.ts`); logo key under the net success summary; tables for Net success and Game log; Game log loss legend and opaque halo on inside-bar labels; toolbar actions stay on the first row (`sm:min-w-0 sm:flex-1` on the controls, `sm:items-start` on `ChartFrame`'s controls row).
- **Model pages:** method copy fixes (WAA sentence, jargon, rounding), sticky "On this page" nav, shared y-domain and dashed 52.4% line on the record trend, value-based week ticks, `niceTicks` and a wider disagreement scatter; `ModelRecord.tsx` uses `BREAK_EVEN_PCT`.

## Verification
- `make check`: passed.
- `make web-e2e`: 502 passed, 10 skipped. The only ✘ is `mobile-scatter.spec.ts` "market board taps…", which is marked `test.fail()` and is expected.
- Four existing `netSuccessDomain` unit tests had their input data changed (assertions unchanged) because the old inputs now trigger the cap.
- Game log's FBS average column shows "offense / defense" in one cell.

## Owner integration (main checkout)
1. `git merge --ff-only worktree-teams-resume-padding`
2. `git worktree remove -f -f .claude/worktrees/teams-resume-padding`
3. `git branch -d worktree-teams-resume-padding`
