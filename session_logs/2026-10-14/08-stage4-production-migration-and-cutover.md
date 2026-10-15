# Session: Stage 4 - Production Migration, Release Activation & Operational Runbook

## TL;DR
- **Worked On:** Completed Stage 4 of the season operations plan: applied Migration 0025 to Neon Production (`DATABASE_URL`), rehearsed Preview activation with the clean git commit, installed the owner release policy in Production, and activated the 2026 season release `production-season-2026-d0272a48d3a0252fd4196db3` in Production. Created the consolidated weekly operational runbook and updated the live status scoreboard.
- **Outcome:** Production database now has atomic release projections enabled with all 21 `season_release_*` tables populated. The full 2026 reconstructed season is live in both Preview and Production (`166-157-6` spread, `163-164-1` total across 657 graded bets; Week 7 active picks slate).
- **Plan Contract:** `docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md`
- **Approval / Status:** Owner explicitly directed: "Let's rpoceed to these 3". Plan is now Complete.
- **Blockers:** None.
- **Next:** Fast-forward merge `dev` into `main` and push to trigger Vercel production deployment.

## Context and Decisions
- Migration 0025 introduces the `season_releases` and `season_release_*` fixed table schema. Web app queries resolve through the active release context, ensuring 100% atomic cutover across all views without table locking or dynamic table names.
- Production activation verified against the Preview rehearsal proof using restricted roles: `cks_prod_pipeline` for production writes and `cks_preview_pipeline` for the read-only preview proof.
- Consolidated recurring weekly operations into `docs/ops/weekly_runbook.md` as the sole operational authority.

## Work Completed
1. **Production Database Migration:**
   - Ran `scripts/pipeline/migrate_db.py --database-env DATABASE_URL` applying migration `0025_season_releases.sql` to Neon Production.
   - Verified creation of `season_releases`, `season_release_policies`, and all 21 projection tables.
2. **Preview Rehearsal:**
   - Executed `run_season.py release --environment preview` to activate `preview-season-2026-d0272a48d3a0252fd4196db3` with clean commit SHA `42a158b8`.
   - Verified readback SHA `e667c99c230ea9c1b467f82dc1d859993482a73444ede68b2b7fecfe77b8adb0`.
3. **Owner Policy & Production Activation:**
   - Installed owner release policy in `season_release_policies` for `production` season 2026.
   - Executed `run_season.py release --environment production --initial` connecting as `cks_prod_pipeline` with preview proof.
   - Release `production-season-2026-d0272a48d3a0252fd4196db3` activated cleanly with identical readback SHA.
4. **Documentation & Runbook:**
   - Authored `docs/ops/weekly_runbook.md` with step-by-step instructions for data ingest, candidate preparation, preview rehearsal, production activation, and rollback.
   - Updated `docs/status.md` with live release ID, active week 7 state, and the 657-bet scoreboard.

## Validation
- [x] Migration 0025 applied to Neon Production (`DATABASE_URL`).
- [x] Release activated in Production (`SELECT release_id, status FROM season_releases` -> `active`).
- [x] All 21 `season_release_*` tables verified populated in Production.
- [x] `docs/status.md` and `docs/ops/weekly_runbook.md` created/updated.
- [x] `npm --prefix web run typecheck` and `test:publication` verified passing.

## Handoff Notes
- **Resume at:** Merge `dev` into `main` and push:
  `git checkout main && git merge dev --ff-only && git push origin main && git checkout dev`
- **Watch out for:** Verify Vercel deployment completes successfully on `https://c-ks-picks-cfb.vercel.app`.

**tags:** ["production-cutover", "migration-0025", "season-release", "weekly-runbook", "status"]
