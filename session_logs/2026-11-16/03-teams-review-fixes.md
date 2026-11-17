# Teams page follow-up

## Summary

- The Strength vs résumé plot on `/teams?view=resume` now uses the shared `ScatterChart`, so it shows team logos with hover, keyboard focus and highlight. Its x-axis now fits the data (`domainFor(extent, 0.08)` over all teams, so filtering never moves a team). Rank #1 is at the top.
- The sizing logic in `ScatterView` moved into an exported `useScatterViewport()` hook, which both the Graphs scatter and the résumé plot use.
- The "Rankings" tab is now "Ratings". The URL value `rankings` is unchanged.
- Wins above average now reads "Wins above avg" in the hub table, phone cards, footnote and team header. "SOS left" is now "SOS remaining".
- The team page's model footer now reads "Model ATS (W–L)" and "Model O/U", so it no longer looks like it contradicts the schedule footer's "ATS (W–L)".
- The schedule Result column has extra left padding, so the total and result badge are separated.

## Files Modified

- `web/src/components/ratings/TeamsHub.tsx`, `web/src/components/charts/ScatterView.tsx`, `web/e2e/teams-hub.spec.ts`
- `web/src/components/teams/{TeamHero,ModelOnTeam,TeamSchedule}.tsx`, `web/e2e/teams.spec.ts`

## Validation

- [x] `make check`
- [x] `make web-e2e` (495 passed, 10 skipped)
- [x] `git diff --check`
- [ ] Visual check on real data (not run this session: logos, #1 at top, `conf=sec` stability, 390px phone fit, "SOS remaining" fit, `pl-4` override of the shared cell padding)

## Handoff Notes

- **Resume at:** Owner integration from the main checkout: `git merge --ff-only worktree-session-log-next-upgrade`, then `git worktree remove -f -f .claude/worktrees/session-log-next-upgrade`, then `git branch -d worktree-session-log-next-upgrade`.
- **Watch out for:** On phones, the résumé plot now sizes to its container, like the other scatters, instead of a fixed-width SVG.
