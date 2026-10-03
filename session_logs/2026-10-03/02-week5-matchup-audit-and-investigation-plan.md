# Session: Week 5 matchup data audit and investigation plan

## TL;DR
- **Worked On:** Read-only audit of all 56 Week 5 matchups (Preview, compared with production); amended the unified rollout plan with the findings; wrote the detailed investigation plan.
- **Outcome:** Three new data issues logged (V5 `ppp` quarantine casualties, two NULL-venue games, drive-metric overtime divergence); unified plan Amendment 2 (Task 1.2 flip criterion, Tasks 1.5/1.6, venue backfill in the batch); new contract `docs/plans/2026-10-03/02-week5-data-issue-investigation.md` (Approved, read-only).
- **Plan Contract:** `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` (Amendment 2) + `docs/plans/2026-10-03/02-week5-data-issue-investigation.md`
- **Approval / Status:** User approved the audit-driven plan changes in-session 2026-10-03.
- **Blockers:** `CFB_R2_*` credentials are not loaded in the shell — required before Phase A (Bronze capture reads).
- **Next:** Run investigation Phases A–F (read-only), then present the D1–D6 recommendation packet.

## Context and Decisions
- Audit method: inline psycopg queries against `PREVIEW_DATABASE_URL` (read-only) covering `games`, `game_venues`, `team_season_stats`, `team_possession_stats`, `team_game_measurements`, `v5_rating_snapshots`.
- Key discovery: the score-stream quarantine is not Silver-only — 129 `missing/unresolved_scoring_attribution` team-measurements for Week 5 teams mean V5 `ppp` loses real points (Kent State offense `ppp=0.00` despite 29 points; Air Force/Army one-game samples). This makes "keep quarantine" a costly D1 option and gave the unified plan its D4 flip criterion (>0.05 ppp move or >5 rank places ⇒ rebuild now).
- Kent State W3 anomaly (3 points in neither offense nor non-offense buckets) is likely garbage-time classification (lost 59–3); identity check is Phase B2.
- Confirmed NOT bugs: 12 games with null leans (no line at freeze, matches status.md); legacy rating-name spellings resolve; all teams present in both stats tables; Preview↔production diffs confined to the punt-leak fix metrics + missing production `ppa_per_play`.

## Work Completed
- Full-slate Week 5 audit (missing/null/zero values, extremes, game counts, venues, ratings alignment, Preview-vs-production diff, prediction nulls).
- Unified plan: Current State audit findings; Task 1.2 expanded with flip criterion; Tasks 1.5 (venues) and 1.6 (drive-metric harmonization) added; scope items 4/9 and DoD updated; Amendment 2 recorded; D1/D3/D4 assumptions revised.
- New investigation contract with Phases A–F, acceptance criteria and stop conditions.
- `known_issues.md`: issue 1 gained the Week 5 audit update; new issues 4 (venue NULLs) and 5 (drive-metric divergence).
- `docs/plans/index.md`: investigation plan row added; unified plan row annotated with Amendment 2.

## Files Modified
- `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` - Amendment 2, new tasks, revised decisions
- `docs/plans/2026-10-03/02-week5-data-issue-investigation.md` - new contract
- `docs/data/known_issues.md` - issue 1 update, issues 4 and 5 added
- `docs/plans/index.md` - new row

## Validation
- [x] `uv run mkdocs build --quiet` — clean
- [x] `git diff --check` — clean
- [x] No lake/DB writes performed (read-only queries only)

## Amendments and Blockers
- None beyond the recorded Amendment 2.

## Handoff Notes
- **Resume at:** Investigation Phase A1 (raw-vs-Silver score diff for the six named games) — needs `CFB_R2_*` credentials loaded.
- **Watch out for:** CFBD rate limits (prefer Bronze captures); investigation plan authorizes no writes; D4 flip criterion must be evaluated before the Phase 2 decision meeting.

**tags:** ["data-quality", "planning", "docs", "matchup"]
