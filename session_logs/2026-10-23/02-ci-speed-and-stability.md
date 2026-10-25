# Session: CI speed and stability cleanup

## TL;DR

- **Worked On:** Phases 1, 2 and 3 of the CI speed and stability contract; all merged to `dev`.
- **Outcome:** `general` uses `--dist worksteal`, drops `fetch-depth: 0`, and single-threads BLAS. Playwright runs against a fixture production build in CI with an explicit hydration marker. Possession-rating tests share tournament setup (PR #8). Audits already exit 0, so no change.
- **Plan Contract:** [`docs/plans/2026-10-23/02-ci-speed-and-stability.md`](../../docs/plans/2026-10-23/02-ci-speed-and-stability.md)
- **Approval / Status:** Owner-approved plan; contract Implemented.
- **Blockers:** None
- **Next:** Phase 4 backlog as separate contracts; consider sharding Playwright only if `web` becomes the bottleneck.

**tags:** ["ci", "playwright", "pytest"]

## Context and Decisions

- The worktree tool branched from `main`, so the branch was reset to local `dev` (`de47d608`) before any work.
- Phase 2 ran after Phase 1 left `general` at 5m19s. Both branches were fast-forwarded into `dev` with `git push origin HEAD:dev` and then deleted (PR #8 carried the Phase 2 CI run).
- `networkidle` stays in `logos.spec.ts`, `charts-visual.spec.ts`, `charts-export-theme.spec.ts` and the broken-image check in `charts.spec.ts`, since those wait on image loads.

## Work Completed

- `.github/workflows/ci.yml`: worksteal, no deep fetch, BLAS thread caps, separate fixture build step before browser tests.
- `web/`: `HydrationMarker`, `gotoHydrated`, production `next start` under `CI`, specs migrated.
- Possession-rating tests: module- and class-scoped shared setup; assertions unchanged.

## Files Modified

- `.github/workflows/ci.yml`, `web/playwright.config.ts`, `web/src/app/layout.tsx`, `web/src/components/HydrationMarker.tsx`, `web/e2e/helpers.ts` and seven e2e specs.
- `tests/test_possession_rating_verification.py`, `tests/ratings/test_possession_rating_materializer.py` — shared setup fixtures.

## Validation

- [x] Local worksteal run of the `general` suite: 2084 passed, 4 skipped (3 of 3 runs passed).
- [x] `CI=1 npm --prefix web run test:ui`: 211 passed, 10 skipped.
- [x] Flake gate `--repeat-each=20 --retries=0` on `matchup` and `mobile-scatter`: 680 passed.
- [x] Web lint, typecheck, `test:publication` (324 passed).
- [x] Phase 2 files: 32 passed before and after; serial 42s to 22s.
- [x] CI timings, `general` / `web`: baseline run `39854431096` 5m54s / 4m03s; Phase 1 on `dev` (run `39990215575`) 5m19s / 2m34s; with Phase 2 (PR #8 run `39993143753`) 3m20s / 2m39s. The `Python tests` coverage gate passed.
- [ ] CI run on `dev` after the Phase 2 fast-forward (`32ad7a42`) not checked.

## Amendments and Blockers

- None

## Handoff Notes

- **Resume at:** Session complete.
- **Watch out for:** the shared tournament run keeps frames (`retain_frames=True`), unverified against the previous no-frames runs for two tests. The `OMP/OPENBLAS/MKL` caps must be reverted if bit-exact SHA tests or timing regress.
