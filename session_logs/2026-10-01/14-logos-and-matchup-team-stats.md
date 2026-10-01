# Session: Self-hosted logos, team-stats pipeline, matchup page gate

## TL;DR
- **Worked On:** Logo tooling and cleanup (contract 07); authentic team-stats pipeline and gated matchup page (contract 10).
- **Outcome:** Logos are self-hosted, id-keyed WebP (sm/lg, light/dark, 138 FBS teams, 4 MB) and sharp at 3x; the old 32 px set and its code paths are removed. `team_season_stats` (migration 0020), its publisher and the gated matchup read layer are on `dev`.
- **Plan Contracts:** `docs/plans/2026-10-01/07-high-quality-team-logos.md` (Implemented), `10-authentic-team-stats-pipeline.md` (Approved; Phase 5 data steps are the user's).
- **Blockers:** Team-stats dry run needs the user's credentials; Silver column names are unconfirmed.
- **Next:** User runs the team-stats dry run from the repo root; then matchup hero redesign, venue data steps, CI hardening, `dev` -> `main`.

## Logos
- User ran `npm run logos:build`; CFBD returns light and dark URLs on `cdn.collegefootballdata.com`. Manifest: 138 teams, no missing files, no dark fallbacks.
- Added alternate-spelling aliases in `team-logos.ts` (the old `TEAM_LOGO_MAP` values are legacy file names, not CFBD names, so they no longer apply). `TEAM_LOGO_MAP` stays in `contracts/teams.*` (still used by pipeline scripts and validated).
- Removed: `assets/logos`, `web/public/logos/*.png`, `logoFilename`/`logoUrl`, the legacy fallback in `TeamLogo`, `LOGOS_DIR`, the Nx input.
- Verified: 32/32 Playwright (sharpness and dark swap enabled), no external hosts requested, Pillow loads the large WebP.
- Mistake caught: the first screenshots were 404 pages (production server closes `/test-*` without `CFB_ENABLE_TEST_PAGE=1`); I sent them before looking, then retook and viewed them.
- Noticed, not changed: `scripts/pipeline/publish_review.py` looks for logos in `REPO_ROOT/"Logos"`, a directory that does not exist, so email inline logos were already not attaching.

## Team stats
See the contract. Long-format table, pre-game snapshot, FBS-only, garbage time excluded, ranks stored by the publisher; page closed in production unless `CFB_MATCHUP_ENABLED=1`.

## Noticed for the matchup redesign
At 390 px the hero's "Forecast & Lines" box overflows (labels sit outside the box, O/U text is clipped).
