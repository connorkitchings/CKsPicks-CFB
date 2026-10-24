# Session: Mobile app-feel pass across Games, Ratings, Graphs and Model

## TL;DR

- **Worked On:** Committed the earlier Stats and Ratings mobile work, then implemented all four phases of the mobile app-feel contract plus owner-requested matchup polish and the Graphs rename.
- **Outcome:** Phones (below 640px) get a sticky app bar with a menu sheet, one pinned control row per page, summary lines, collapsed explanations and the first data item near the top of the screen. Desktop is unchanged.
- **Plan Contract:** [`docs/plans/2026-10-23/03-mobile-app-feel.md`](../../docs/plans/2026-10-23/03-mobile-app-feel.md) (also amends [Contract A](../../docs/plans/2026-10-21/03-mobile-charts-a-page.md))
- **Approval / Status:** Owner approved the plan and each phase in session. Contract is In Progress: real iPhone and Android acceptance has not been done.
- **Blockers:** None for code. Real-device checks need the owner.
- **Next:** Owner pushes `connorkitchings/mobile-app-feel` (or merges it into `dev`), checks it on production data and on real devices, then the contract moves to Implemented.

**tags:** ["web", "mobile", "ui", "playwright"]

## Context and Decisions

- Earlier Stats and Ratings work was committed first in three area commits (scatter fit, Stats header and sticky bar, Ratings header) plus a Contract A amendment, and pushed to `origin/dev` at `26c2b166`. Work then moved to branch `connorkitchings/mobile-app-feel` off `dev`.
- Phase A: shared `useSheet`/`BottomSheet`, `MobileStickyBar`, `useIsPhone` and `SummaryLine`.
- Phase B: `AppBar` with a menu sheet (season, theme, update time); `--app-bar-h`; `overscroll-behavior-y: none`; `theme-color` follows the theme toggle (light `#fafafa`, dark `#000`); week and season changes keep scroll position.
- Phase C: Games pinned week bar and Filters sheet, one-line record, Top leans and Biggest edges after the first day group; Model tabs pinned with Spread/Totals buttons as the single filter; Ratings and Graphs headings and descriptions collapsed; matchup compact hero.
- Phase D: press states, 44px targets, one phone page rhythm (`PHONE_PAGE_RHYTHM`), skeletons matching the compact tops, reduced motion.
- Owner decisions during the session: tab renamed to Graphs (route `/stats` unchanged); matchup back link merged into the app bar; five matchup polish items.
- Local review pitfall: running `make web-local` without `CFB_PUBLICATION_MODE=predictions` serves market mode, so matchups show no model data. Not a data bug.

## Work Completed

- Commits on `connorkitchings/mobile-app-feel` after `26c2b166`: shared foundations (`4b3df6a9`), app shell (`28efd57d`), Graphs rename (`4473375a`), matchup (`28f268ce`), Model (`ab0f2e50`), Ratings and Graphs (`4e0ba219`), Games (`a5bfaef9`), matchup bar merge and hero polish (`ad8505fe`), Phase D polish (`a3e79fd0`).
- Measured first data item tops at 390x844: Games first card 325px, Ratings first row 161px, Graphs chart card 189 to 241px, matchup forecast grid 262px (268px at 320x568).

## Files Modified

- `web/src/components/ui/` — `BottomSheet`, `MobileStickyBar`, `SummaryLine` (new); `ExportActions`.
- `web/src/lib/use-is-phone.ts`, `web/src/lib/page-width.ts`.
- `web/src/components/AppBar.tsx` (new), `Header.tsx`, `SiteNav.tsx`, `ThemeToggle.tsx`, `WeekNav.tsx`, `SeasonSelector.tsx`, `PerformanceDashboard.tsx`.
- `web/src/components/slate/*`, `components/ratings/*`, `components/charts/*`, `components/matchup/*`, `components/model/ModelTabs.tsx`.
- `web/src/app/` pages, `loading.tsx` skeletons, `layout.tsx`, `globals.css`.
- New specs: `web/e2e/mobile-app-bar.spec.ts`, `mobile-games.spec.ts`, `mobile-model.spec.ts`, `mobile-matchup.spec.ts`, `mobile-polish.spec.ts`; edited specs for ratings, charts, logos, publication and slate.
- Docs: `docs/plans/2026-10-21/03-mobile-charts-a-page.md`, `docs/plans/2026-10-23/03-mobile-app-feel.md`, `README.md`, `AGENTS.md`, `web/README.md`.

## Validation

- [x] `npm --prefix web run lint` and `typecheck` clean
- [x] `npm --prefix web run test:publication`: 324 pass, 1 skipped
- [x] Fresh fixture build, then `CI=1 npm --prefix web run test:ui`: 292 passed, 10 skipped by design, 0 failed (final Phase D code)
- [x] Flake gate `--repeat-each=20 --retries=0` on the new and changed mobile specs, no flakes
- [x] `make contracts-check` passes; `uv run mkdocs build --strict` passes
- [x] `git diff --check`
- [ ] Real iPhone and Android devices (notch, native picker, keyboard): not done
- [ ] CI per-job timings against run `39993143753` and browser job under about 3 minutes: needs a PR run
- [ ] Dark-theme review of Ratings, Graphs, Model and skeletons, and 320px screenshots: not reviewed

## Amendments and Blockers

- Amendments are recorded in the contract: Graphs rename, matchup back link merged into the app bar, local predictions-mode note. Contract A carries its own 2026-10-23 amendment.

## Handoff Notes

- **Resume at:** owner review on production data and real devices, then push and open the PR (for example `feat(web): add an app-like phone layout across all four tabs`), and compare CI timings.
- **Watch out for:** the Games first card has about 5px of slack against its 330px assertion; `scroll-padding-top` for the two-row Games bar was not tested with a real anchor jump; the owner's dev server on port 3000 shares `.next` with builds and needs a restart after them.
