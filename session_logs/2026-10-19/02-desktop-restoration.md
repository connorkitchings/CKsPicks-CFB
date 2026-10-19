# 2026-10-19 — Desktop restoration (A) and Charts cleanup (B)

Branch `connorkitchings/desktop-restoration`, worktree off `origin/dev` (`b971da1f`, which does not contain the unpublished SOS/SOR commit `6b3f07a1`). Nothing is committed; the owner commits at the boundaries below.

## Commit boundaries (file groups, all under `web/`)

**A1: segmented primitive, Charts migration, touch targets**
- `src/components/ui/SegmentedControl.tsx` (+ `SegmentedControl.test.ts`, `package.json` script entry), deleted `src/components/charts/segmented-styles.ts`
- Charts views migrated to it: `ChartFrame`, `EfficiencyView`, `GameLogView`, `PossessionView`, `RatingTrajectoryView`, `src/app/charts/page.tsx`
- `fill` callers: `RatingsView`, `PerformanceDashboard`, `UnitMatchups`, `TopLeans`
- `sm:` sizing: `SearchField`, `SlateToolbar`, `MatchupLinks`, `ThemeToggle`, `SeasonSelector`, `ui/Disclosure`, Ratings timeline pills
- "Grid"/"List" labels: `SlateToolbar`, `e2e/mobile-slate.spec.ts`, `e2e/publication.spec.ts`

**A2: desktop-visible disclosures, hero, WeekNav**
- New `ui/ResponsiveDisclosure.tsx`; used by `TopLeans`, `ResultHighlights`, `PredictionGameCard`, `PerformanceDashboard`
- `slate/ModelRecord.tsx`, `matchup/MatchupHero.tsx`, `WeekNav.tsx`, "Pick target" `sm:w-fit`
- Specs: `performance.spec.ts`, `matchup.spec.ts`, `mobile-slate.spec.ts`, `publication.spec.ts`

**A3: heading scale and desktop spec**
- `PageHeading` on `charts/page.tsx`, `methodology/page.tsx`, `teams/[team]/page.tsx`
- New `e2e/desktop-layout.spec.ts` (8 tests at 1280px)
- `SegmentedControl` md group padding `p-0.5` → `p-px` (group measured 42px, limit 40px)

**B: Charts cleanup** (separate commit, after A1)
- Deleted: `TrajectoryView`, `ScheduleAdjustmentView`, `ScheduleAdjustmentChart`, `chart-schedule.test.ts`, `charts-schedule.spec.ts`, `charts-trajectory.spec.ts`
- Trimmed: `lib/charts.ts`, `lib/chart-config.ts`, `chart-queries.ts` (`getTeamAdjustedEpaAll`), `ChartsView`, `TrajectoryPanel`, `chart-config.test.ts`, `chart-trajectory.test.ts`, `test/fixtures/charts.ts`, `charts-visual.spec.ts`, `charts.spec.ts`, `package.json`

## Deviations from the plan

1. **`ChartTable`, the "Show as table" toggle, `TrajectoryChart` and `chart-trajectory-layout.ts` were NOT deleted.** `TrajectoryPanel` (kept for rating-trajectory) uses all four. Owner decision: drop them only if rating-trajectory leaves the Ratings-tab plan.
2. **`ModelRecord` does not use `ResponsiveDisclosure`.** That version pushed the first results card 25px down and failed the 390x844 safe-area test; the heading and phone "Season context" summary share one row instead. Desktop is `md:grid-cols-2` as planned.
3. **`ResponsiveDisclosure` renders children twice** (phone `<details>`, desktop inline). Tests filter by `visible`.
4. **Filled segmented buttons wrap between words on phones** (`whitespace-normal`, no mid-word breaks); nowrap from `sm:`.
5. **`SegmentedControl` style helpers live in the component file** and `"use client"` was removed (server-rendered Charts page needs them).
6. **Matchup offense selector is `lg:hidden`**, so the desktop spec checks it is hidden at 1280px and measures it at 768px.
7. **Segment height check** is `<= max(line-height + padding, min-height)` and `<= 40px`, since `min-h-9` makes a plain line-height bound impossible.
8. **WEEK_GENERATIONS (Post-Week 5-7) not added.** The Neon `SELECT DISTINCT cutoff_utc` check was not run, so the three entries remain unverified. A1 commit body should not claim them.
9. **WebKit:** `playwright.config.ts` defines only chromium; no WebKit suite exists to run.
10. The plan's `git branch sos-sor-draft` / `git reset --hard origin/dev` steps are the owner's; this branch was cut from `origin/dev` directly, so it is unaffected either way.

## Verification (final tree)

- `lint`, `typecheck`: clean. `test:publication`: 236 pass, 1 skipped. `test:ui`: 132 pass, 9 skipped (not investigated). `test:charts-gate`: 12 pass.
- Charts specs with `CFB_CHARTS_ENABLED=1` (the dev server in `playwright.config.ts` already sets it): pass; `charts-ratings` stays skipped. Production builds with charts enabled and disabled both succeed.
- 48 screenshots (6 pages x 390/768/1280/1440 x light/dark) in the session scratchpad `shots/`; 1280px Picks, Performance and Matchup inspected: "Grid | List" on one line, Best Bets and Season record visible, three-column matchup hero, no horizontal overflow.

## Review follow-ups (after the first report)

- **Commit strategy:** the A1/A2/A3 stages share files (`SegmentedControl.tsx`, `PerformanceDashboard.tsx`, `WeekNav.tsx`), so the boundaries above are a file map, not a commit plan. Recommended: one commit for A, one for B.
- **Plan correction:** the plan called `ChartTable` and the "Show as table" toggle dead code. They are live on the rating-trajectory chart through `TrajectoryPanel`.
- **WebKit:** the plan's "WebKit core suites" cannot run (Chromium-only config). Plan error, not an implementation gap. Adding a WebKit project is a separate task; Safari layout bugs are unchecked until then.
- **Skips:** a `--reporter=list` run shows 12 skips: `charts-ratings.spec.ts` (8, rating-trajectory is `ready:false`), `charts-visual.spec.ts` (1, env-gated), `logos.spec.ts` (3). The diff against `HEAD` removes skip markers only from the deleted schedule/trajectory suites and adds none. (The earlier "9" came from a different invocation; counts differ by 3, the logos tests.)
- **Screenshots reviewed:** Picks 390 light and 768 dark, Results 390 and 1280 light, Ratings 1280 dark, Charts 1280 light, plus the earlier 1280 Picks/Performance/Matchup. Phone shows Best Bets and Game details collapsed; 768+ shows them open; Results at 1280 shows week and season records side by side; Charts corner captions are not covered by logos in the fixture.
- **Bug found in review:** at 390px the Results record heading's "this slate · small sample" note overlapped the "Season context" summary. Fixed with `pr-32 md:pr-0` on the heading; verification recorded below.

## Owner edits made in the worktree after the first report

These were made by the owner, not the implementation agents, and are not in the plan.

- **Data commit (own commit, before A):** `web/src/lib/rating-periods.ts` gains three `WEEK_GENERATIONS` entries: Post-Week 5 (`2026-10-05T00:00:00.000Z`, 271 games), Post-Week 6 (`2026-10-11T15:00:00.000Z`, 329) and Post-Week 7 (`2026-10-18T14:00:00.000Z`, 388). The cutoffs were confirmed by the read-only Neon `SELECT DISTINCT cutoff_utc`; the game counts come from retained docs. The map is temporary and is deleted by `docs/plans/2026-10-19/02-sos-sor-release-projection.md`. This supersedes deviation 8 above.
- **Game cards (`PredictionGameCard.tsx`):** venue sits beside the time; the "Game details" disclosure and the edge footnote are removed; the line source and cover margin are a muted line inside each bet box. The owner found the details cluttered and redundant. This makes the `ResponsiveDisclosure` use on card details (A2) moot.
- **Matchup:** smaller forecast text on phones, repeated logos hidden below `lg`, and the unit toggle labels are now team names.
- Specs updated for these: `publication.spec.ts`, `mobile-slate.spec.ts`.
- `web/.env` and `web/.env.local` were copied into the worktree from the main checkout (gitignored) for real-Preview-data viewing.
- Verification after these edits: lint and typecheck clean; `publication`, `mobile-slate`, `matchup` and `desktop-layout` Playwright specs 63 passed.
- Follow-up needing its own plan: collapsible stat sections on the matchup page.

## Fixes found during final review

- **Doubled logos on desktop matchup:** `TeamLogo` renders light and dark images, so `className="hidden lg:block"` on both re-showed the dark copy in light mode. Visibility moved to a wrapping `div` in `UnitMatchupTable.tsx` (a `div`, since `matchup.spec.ts` treats the header's first `span` as the role label). Regression test added to `desktop-layout.spec.ts`.
- **Open "Season context" on phones:** the season tiles sat above unlabeled week tiles. A "Week N" label now shows above the week tiles only while the disclosure is open (`max-md:group-has-[details[open]]/record:block`), the repeated "This slate is a small sample" sentence is removed, and the open content has `pt-2`. The closed card height is unchanged. Test added to `mobile-slate.spec.ts`.
- **Commit shape:** A and B interlock (`TrajectoryView` imported the Charts segmented control that A removes), so A and B ship as one web commit; the data commit and the docs commit are separate.

## Open items

- Pre-existing hydration warning from `TeamHighlightCombobox` (`caret-color`).
- Workstream C (SOS/SOR release projection contract at `docs/plans/2026-10-19/02-sos-sor-release-projection.md`) not started.
