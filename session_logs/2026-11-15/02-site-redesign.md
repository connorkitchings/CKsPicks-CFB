# Session: Site redesign implementation checkpoint

## TL;DR

- **Worked On:** Approved Stage 1 site redesign and analytical usability.
- **Outcome:** Approved contract saved and committed; implementation started but is incomplete.
- **Plan Contract:** [Site redesign and analytical usability](../../docs/plans/2026-11-15/site-redesign-and-analytical-usability.md)
- **Approval / Status:** Owner instructed “Please implement the plan.” Contract remains In Progress.
- **Blockers:** All three implementation workers stopped with an account usage-limit error. No completed worker report or implementation validation exists.
- **Next:** Resume workers in the existing isolated worktree, inspect their partial changes, finish the six contract packages, then perform review and all acceptance checks before local integration.

**tags:** ["web", "design", "implementation", "checkpoint"]

## Context and decisions

- Baseline local dev was `5dec23f9`; work is isolated in `.worktrees/site-redesign`, branch `codex/site-redesign`.
- Approved contract is committed as `359512b4`. Other sessions' work on local dev was not changed.
- Stage 1 uses existing serving data; new data projections, forecast ranges, model changes, deployment and pushes remain excluded.
- Worktree dependencies were installed with `make web-install`; repository hooks configured with `make hooks`.

## Work completed and partial files

- Saved the full approved implementation contract before code edits.
- Foundation worker partially edited global styles, AppBar, Header, SiteNav and page widths, and added an untracked TeamSearch component.
- Teams worker partially edited `web/src/lib/v5.ts` and added an untracked `web/src/lib/team-analysis.ts`.
- These changes are uncommitted and not reviewed. Do not assume their interfaces or behavior are complete.
- No Games/Matchup implementation changes were present at the checkpoint. Model assessment has not yet been assigned for implementation.

## Validation

- `make web-install`: passed.
- `make hooks`: passed after sandbox escalation for Git configuration.
- `git status` and `git diff --stat`: inspected to preserve the incomplete state.
- No application validation, full checks, browser inspection or Preview read verification has completed.

## Amendments and blockers

### Continuation checkpoint

#### Shared design slice completed

- Local commits `ecb7adbf` and `7e3d260f`: editorial desktop header, Teams navigation, phone team finder, canonical alias/accent/abbreviation matching, shared layout widths and scoped CSS preserving the narrative reading column.
- Verification: 9 focused shared/header browser tests, 17 wordmark browser tests, 6 search/width unit tests and the updated navigation assertion passed. TypeScript passed. ESLint has no errors; two unused fixture-argument warnings remain in the later Graphs slice.
- Inspected 320px dark and 640px light screenshots. Escape first dismisses search results, then dismisses the phone menu and restores focus. Fixture server stopped after testing.
- Next sequential slice: complete Games/matchups and their tests. Teams redirect is already partially implemented; its behavioral verification belongs with the Teams slice.

- The owner approved the step-by-step continuation plan and explicitly instructed implementation. Work now proceeds one bounded slice at a time, starting with shared design/navigation.
- The worktree still has only the planning commit; partial implementation across 49 tracked files and new components is preserved uncommitted. Model implementation and new regression tests were absent at the audited checkpoint.
- Verified before this continuation: Python 2,546 passed / 12 skipped; Ruff, contract validation and quality registry passed. TypeScript passed at that checkpoint; ESLint had two unused-variable warnings. Web unit suite: 472 passed / 10 failed / 1 skipped. Browser tests, production build, full integrated checks and real Preview read verification remain outstanding.
- Ten failing unit expectations concern chart defaults/labels/empty-state identifiers, team-link restrictions, page widths and old Ratings navigation/page assumptions. Each must be reviewed against intentional behavior, not deleted wholesale.
- Browser observation to reproduce: rapid changes to both Teams comparison selectors appeared to erase the first selection. Resume tests must cover this. Strength-versus-résumé also currently derives horizontal extent from filtered rows and phone rank labels use overall regardless of selected metric; both require correction.
- Local dev advanced independently through model-research documentation commits (observed `db223f23` at continuation). Do not overwrite or stage that work. Final integration must preserve it.
- No push, release, migration, data operation or deployment has been performed.

No scope amendments. Work paused because the delegated workers hit the usage limit; no deployment or local-dev merge occurred.

### Step 3 (Games and matchups) completed

- Resumed in the same worktree after confirming it was idle (no file changes in the prior 5 minutes, no Codex process referencing it).
- Fixes folded in: matchup statistics, evidence and sharing gate on `lineageStatus === "ready"` only, while forecast-derived facts still require predictions mode; `getSeasonReleaseContext` failure no longer blanks the slate; the pick'em/home-margin sign normalization now lives in `marketComparisonPoints` with a unit test; "Show all games" pushes history so Back returns to the filtered state; removed constant `clsx` wrappers, a stray import and blank line, and the unused `edgeTone` helper with its test.
- Verification: typecheck passed; lint shows no errors (remaining warnings are the two `stats/page.tsx` unused-argument warnings, Step 5); `test:publication` 480 passed / 7 failed (the known Teams and Graphs expectations) / 1 skipped; `e2e/games-redesign.spec.ts` 5 of 5 passed against the fixture server.

### Preview read verification of the new database reads (read-only)

Ran through `psql` with `default_transaction_read_only=on`; the connection string was never printed. Active 2026 release is in week 11 (activated 2026-11-09); the earlier release is superseded.

- Selected market quotes (`season_release_prediction_market_selections` joined to `season_release_market_quotes`, active release): 1,257 selections, 1,257 with `captured_at`, 0 null (0%). The legacy unscoped tables show the same: 2,426 of 2,426.
- Rating snapshots (active release, `current` class): 1,518 rows, 11 cutoffs, 138 teams per cutoff, exactly 1 source manifest, so exact-source history is unambiguous. The legacy unscoped table holds up to 4 generations per cutoff (8 sources overall), which is why `getRatingAnalysisHistory` must filter on the selected source and never join by week alone.
- Evidence: for the latest cutoff, all 138 snapshots have rating components (276 component rows, one offense and one defense each), so `getTeamRatingEvidence` resolves for the active snapshot.
- `/stats` `nextMatchups`: it reads only the release's active week. Week 11 (67 games, last kickoff 2026-11-15) has no upcoming games now, so the map is empty and chart links to the next matchup disappear until the next release activates week 12 (66 games, 2026-11-18 to 2026-11-22). Flagged as a behavior limit, not changed.
- Not exercised: the application code paths themselves against Preview (SQL equivalents only).

### Step 4 (Teams) completed

- Added `lib/url-state.ts` (`searchParamsUrl`, `replaceSearchParams`), which edits a copy of the live `window.location.search`. `TeamsHub.change` now uses it, so two quick selector changes both persist (browser-tested with simultaneous selections).
- Strength-vs-résumé x-scale now spans all teams in the period, so conference/search filters no longer move points. The phone rank label follows the selected sort. Schedule opponent names link only when `resolveTeam` succeeds; the separate "Opponent profile" row is gone and the matchup row link is now a stretched overlay so no link nests inside another.
- Fixed a hydration mismatch: `RatingTimeline` rendered a `<title>` with an array of children; it is now one template string.
- Tests: new `lib/team-analysis.test.ts` (tied ranks, ambiguous/gap/other-source weekly movement, future and other-source exclusion), registered in `test:publication`. Replaced the two stale ratings-page source assertions with checks on the `/ratings` redirect and `TeamsHub`. Replaced the obsolete `e2e/ratings.spec.ts` (it drove the retired `/ratings` UI) with `e2e/teams-hub.spec.ts` (redirect keeps query parameters, simultaneous selections, phone rank label, scale stability, schedule links); updated `e2e/teams.spec.ts` for the intentional "All teams"/"Back to teams" links and the new trend chart name.
- Verification: `test:publication` 486 passed / 5 failed (the Graphs failures, Step 5) / 1 skipped; `teams.spec.ts` and `teams-hub.spec.ts` 23 of 23 passed.
- Left in place: the unused `RatingsView.tsx` (plus its filter sheet) and the three source-text tests that still read it; removing that dead code is a separate cleanup.

## Handoff notes

- **Resume at:** existing worktree and approved contract; do not recreate or discard partial changes.
- Foundation worker owns shell, team search, charts and graph pages. Teams worker owns `/teams`, `/ratings` redirect, team profiles, rating/history helpers and `v5.ts`. Games/Matchup worker owns slate/matchup pages and selected-quote interfaces. All workers must stage only their owned files.
- Teams worker owns the permanent `/ratings` redirect preserving query parameters, not `next.config.ts`.
- Shared compare URL is `/teams?view=compare&team=<canonical>&compare=<canonical>&season=N`, with exact period where available.
- Register new meaningful tests in `web/package.json` and complete Model package after a worker is available.
- Required final gates remain `make check`, `make web-e2e`, `git diff --check`, real Preview read verification and representative visual/accessibility inspection.
- Keep contract In Progress until all acceptance criteria pass. Do not push, deploy or merge the unfinished changes into dev.
