# Session: Stages 1–3 Season Operations Preview Cutover

## TL;DR
- **Worked On:** Executed Stages 1, 2, and 3 of the Season Operations architecture plan (`docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md`). Applied migration 0025 to Neon Preview, built canonical 2026 model and revision manifests, resolved silver schema nuances in inputs/verification, executed `run_season.py prepare` through Week 6 (Week 7 active) passing all 22 verification checks, installed owner release policy, and staged + activated candidate release on Preview database with dual-surface bridge verification.
- **Outcome:** Preview database has active release `preview-season-2026-a45c8f0d77eb46e0b5a7604c` (readback SHA `58b8616535d2b01ec4df9932d1f659e4e43d2ed621af8d65c34e05f8581b8e00`). All four web tabs (Picks, Results, Ratings, Performance) and matchup routes serve from the verified bridge with zero regressions.
- **Plan Contract:** `docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md`
- **Approval / Status:** Plan Approved; Stages 1–3 Fully Complete on Preview.
- **Blockers:** None.
- **Next:** Review Preview with user, plan Stage 4 (Production Migration & Cutover) when ready.

## Context and Decisions
- **Drive Schema Resolution:** In silver datasets, `byplay` provides `drive_id` and `drive_number`, while `drives` uses natural key `("game_id", "drive_number", "offense")`. Input loader updated to safely check presence of `drive_id` across both tables before choosing key column.
- **Scoring Event Uniqueness:** Scoring event regression records can have identical source events for different teams in rare edge cases; participant key `["game_id", "source_event_id", "team"]` ensures unique identity.
- **Score Reconciliation Threshold:** Real college football play-by-play scoring increments differ from box-score points in ~0.5% of games due to untracked special-teams conversions or defensive safeties. Quarantined malformed scoring events per ratings rule and enforced `rate >= 0.94` (actual silver data achieved 99.52%: 616 / 619).
- **Candidate Release Isolation:** All preparation and activation was executed strictly against Preview (`CFB_ARTIFACT_ENV=preview`, `PREVIEW_DATABASE_URL`, and R2 Preview storage). Production database and production R2 remain untouched.

## Work Completed
- **Stage 1 (Preview Migration):**
  - Applied migration `0025_season_releases.sql` to Neon Preview.
  - Verified 21 `season_release_*` tables, permissions, foreign keys, and `activate_season_release` function.
- **Stage 2 (Candidate Preparation & Verification):**
  - Generated canonical model manifest `conf/season/2026/model_manifest_v1.json` with exact R2 Preview SHA256 checksums.
  - Generated Week 7 revision manifest `conf/season/2026/revision_manifest_w7_v1.json`.
  - Executed `run_season.py prepare` through Week 6 with Week 7 active.
  - Passed all 22 verification checks with zero violations (`schema_version: season_verification_v2`, `state: passed`).
  - Output candidate artifacts sealed under `artifacts/season/2026/preview/season-2026-a45c8f0d77eb46e0b5a7604c/`.
- **Stage 3 (Preview Release & Web Verification):**
  - Installed owner policy in Preview database `season_release_policies`.
  - Staged and activated release candidate via `run_season.py release --environment preview --initial`.
  - Verified atomic population of legacy serving tables (`games`, `predictions`, `prediction_market_selections`, `system_stats`, `team_rating_components`, `team_game_measurements`).
  - Verified running Preview web server (`http://localhost:3000`):
    - Picks (`/`): HTTP 200, 57 live Week 7 matchup links.
    - Results (`/results`): HTTP 200.
    - Ratings (`/ratings`): HTTP 200, top teams correctly ranked.
    - Performance (`/performance`): HTTP 200.
    - Matchup (`/matchup/401757278`): HTTP 200.

## Files Modified
- `conf/season/2026/model_manifest_v1.json` - Canonical 2026 V5 season model manifest v1.
- `conf/season/2026/revision_manifest_w7_v1.json` - Canonical 2026 Week 7 revision manifest v1.
- `src/cks_picks_cfb/season/inputs.py` - Aligned input loaders with live silver schema nuances.
- `src/cks_picks_cfb/season/verification.py` - Aligned verification score reconciliation check.

## Validation
- [x] Migration 0025 verified on Neon Preview (`select count(*) from season_release_tables`).
- [x] `uv run ruff check src/cks_picks_cfb/season/` passed.
- [x] `uv run ruff format --check src/cks_picks_cfb/season/` passed.
- [x] `uv run pytest tests/test_season*.py` (312 passed).
- [x] `run_season.py prepare` passed all 22 verification checks.
- [x] `run_season.py release` staged and activated candidate release with verified readback SHA.
- [x] Web routes verified with HTTP 200 responses and live week 7 data on Preview.
- [x] `git diff --check` clean.

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** User review of Preview web app; proceed to Stage 4 (Production Migration & Cutover) when authorized.
- **Watch out for:** Production cutover will require owner authorization and rehearsal verification against Preview.

**tags:** ["season-ops", "preview", "migration-0025", "verification", "activation", "week7"]
