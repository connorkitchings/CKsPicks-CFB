# Session: Dark-mode logo color repair

## TL;DR
- **Worked On:** Owner-reported Tennessee logo color loss across game cards/results and charts.
- **Outcome:** Investigation and localized shared-resolver repair in progress.
- **Plan Contract:** N/A (fast path: existing shared logo resolver and focused regressions).
- **Approval / Status:** Owner reported Tennessee must be orange; implementation authorized by the bug-fix request. Owner additionally selected preserving team colors where readable while retaining contrast variants when needed.
- **Blockers:** None for Tennessee.
- **Next:** Validate the local resolver change, audit related logos and show a corrected local preview.

## TODO
- [x] Trace cards, chart SVGs and matchup exports to shared `logoSrc`.
- [x] Inspect stored Tennessee variants and source manifest.
- [x] Implement localized resolver policy and meaningful regressions.
- [x] Audit other color-to-white substitutions and incorporate owner preference.
- [x] Validate and document handoff/commit scope.

## Context and Decisions
- Work stays in retained isolated `connorkitchings/charts-module` worktree; primary dev is at the completed chart commit and has its Preview server on port 3000.
- Preserve untracked integration log 09 and all ignored research/rehearsal artifacts.
- Tennessee's existing standard `2633.webp` is orange; its existing dark variant is white. Both are stored assets sourced from CFBD CDN according to `web/public/logos/v2/manifest.json`. Shared components select by theme; no runtime logo API call is involved.
- Reuse the existing standard asset through shared resolution; avoid changing immutable asset bytes or cache URLs.
- Implementation delegated to one worker; independent local asset audit delegated read-only.

## Work Completed
- Diagnosis confirmed visually from both stored Tennessee variants.
- Read-only audit confirmed all 552 stored files match the recorded manifest hashes; no resizing/re-encoding corruption or CSS color filter caused this.
- Nineteen teams have colorful standard marks and entirely white dark variants. Seven visibly colored standards have approximately 3:1 or greater foreground contrast against the existing dark surface: Tennessee 8.02, Sam Houston 6.44, Clemson 6.43, North Texas 4.81, Texas 4.23, Buffalo 3.06 and Utah 3.03. These are a local artwork-selection aid, not a new accessibility certification.
- Alabama (2.53), Duke (2.58), Temple (2.68), Indiana (2.22), Charlotte (2.09) and darker navy/green/maroon standards retain existing contrast variants. A blanket replacement would reduce their visibility.
- The owner chose “Preserve team colors where readable; keep contrast variants when needed.” Implementation scope expanded from Tennessee to the seven reviewed bright marks, still entirely within the shared display resolver.
- Implemented `PRIMARY_COLOR_LOGO_IDS` set in `web/src/lib/team-logos.ts` to select standard light asset in dark theme for the 7 high-contrast marks.
- Added unit tests in `web/src/lib/team-logos.test.ts` and comprehensive e2e checks in `web/e2e/logos.spec.ts`.
- Updated `web/README.md` to document the curated dark-surface color preservation policy.

## Files Modified
- `web/src/lib/team-logos.ts` — shared resolver preserves colors for the 7 audited bright marks in dark mode.
- `web/src/lib/team-logos.test.ts` — regression test covering color preservation for the 7 schools and contrast variants for darker marks.
- `web/e2e/logos.spec.ts` — Playwright assertions for dark-mode logo src across Picks, Results, Charts, and static PNG capture.
- `web/README.md` — documented the curated dark-surface logo policy.
- `session_logs/2026-10-16/10-dark-logo-color-repair.md` — this session log.

## Validation
- [x] Scoped unit tests: `npm run test:publication` (188 passed).
- [x] Playwright e2e tests: `npm run test:ui e2e/logos.spec.ts` (5 passed, including Tennessee orange dark check).
- [x] Playwright charts tests: `npm run test:ui e2e/charts.spec.ts` (23 passed, including PNG export and logo decoding).
- [x] Python test suite: 50 passed.
- [x] Typecheck: `tsc --noEmit` passed.
- [x] Linter: `eslint` passed with 0 errors (1 preexisting warning).
- [x] `git diff --check`: clean.

## Amendments and Blockers
- Owner approved preserving readable team colors; seven bright standard marks qualify for this localized curated resolver policy. Darker marks retain their existing contrast variants.

## Handoff Notes
- **Resume at:** Commit the allowlist on `connorkitchings/charts-module` and fast-forward to `dev`.
- **Watch out for:** Local Preview server on port 3000 will reflect the changes once `dev` is fast-forwarded.
- **Proposed commit:** `fix(web): preserve readable team colors in dark-mode logo resolver`

**tags:** ["web", "logos", "bugfix"]
