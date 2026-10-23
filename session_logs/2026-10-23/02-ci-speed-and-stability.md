# Session: CI speed and stability cleanup

## TL;DR

- **Worked On:** Phases 1 and 3 of the CI speed and stability contract; Phase 2 deliberately deferred.
- **Outcome:** `general` uses `--dist worksteal`, drops `fetch-depth: 0`, and single-threads BLAS. Playwright runs against a fixture production build in CI with an explicit hydration marker. Audits already exit 0, so no change.
- **Plan Contract:** [`docs/plans/2026-10-23/02-ci-speed-and-stability.md`](../../docs/plans/2026-10-23/02-ci-speed-and-stability.md)
- **Approval / Status:** Owner-approved plan; contract In Progress until the PR's CI timings are compared.
- **Blockers:** None
- **Next:** Owner pushes the branch and opens a PR to `dev`; compare `gh run view <id> --json jobs` against baseline run `39854431096`. Do Phase 2 only if `general` stays above about 3 minutes.

**tags:** ["ci", "playwright", "pytest"]

## Context and Decisions

- Branch `worktree-connorkitchings-ci-speed-stability` was reset to local `dev` (`de47d608`) because the worktree tool branched from `main`. Rename the branch to `connorkitchings/ci-speed-stability` before pushing if desired.
- Phase 2 is gated on CI measurement, so it was not implemented.
- `networkidle` stays in `logos.spec.ts`, `charts-visual.spec.ts`, `charts-export-theme.spec.ts` and the broken-image check in `charts.spec.ts`, since those wait on image loads.

## Work Completed

- `.github/workflows/ci.yml`: worksteal, no deep fetch, BLAS thread caps, separate fixture build step before browser tests.
- `web/`: `HydrationMarker`, `gotoHydrated`, production `next start` under `CI`, specs migrated.

## Files Modified

- `.github/workflows/ci.yml`, `web/playwright.config.ts`, `web/src/app/layout.tsx`, `web/src/components/HydrationMarker.tsx`, `web/e2e/helpers.ts` and seven e2e specs.

## Validation

- [x] Local worksteal run of the `general` suite: 2084 passed, 4 skipped (3 of 3 runs passed).
- [x] `CI=1 npm --prefix web run test:ui`: 211 passed, 10 skipped.
- [x] Flake gate `--repeat-each=20 --retries=0` on `matchup` and `mobile-scatter`: 680 passed.
- [x] Web lint, typecheck, `test:publication` (324 passed).
- [ ] CI timing comparison (needs a pushed branch).

## Amendments and Blockers

- None

## Handoff Notes

- **Resume at:** CI timing comparison.
- **Watch out for:** the `OMP/OPENBLAS/MKL` caps must be reverted if bit-exact SHA tests or timing regress in CI.
