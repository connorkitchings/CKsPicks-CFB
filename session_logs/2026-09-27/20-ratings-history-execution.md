# Session: Ratings history execution — generations, projections, week tabs

## TL;DR
- **Worked On:** Executed the approved all-five ratings-history contract end to end: 3 input bundles, W0/W1/W2 repair→measurements→replay chains (all independently verified), W3/W4 compare-only reruns (both bit-identical — never projected), Preview + production projections (812 new rows each env), week-labeled tabs with priors fallback, tests, and all gates.
- **Outcome:** Production now holds 5 certified `current` generations (09-03, 09-08, 09-13, 09-22, 09-27). Pre-existing rows byte-untouched (verified by counts); active run, health, and default views unchanged. Web serves 6 week tabs (Preseason + Post-Week 0–4) with 138-team resolvability via priors backfill.
- **Plan Contract:** `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` (Amendment 2 approved; Tasks 1–4 implemented, DoD validation pending live readback + commit).
- **Approval / Status:** All R2/Neon writes were contract-authorized (Preview research + additive serving inserts). Web changes need user commit + CI/Vercel deploy, then live tab readback.
- **Blockers:** None.
- **Next:** Commit web files + this log → CI → Vercel deploy → live `/ratings` verification of all six tabs → mark contract Implemented.

## Context and Decisions
- W3/W4 repro digests matched certified manifests byte-for-byte (priors/rating_states/team_states all three SHAs each), proving pipeline determinism under current HEAD. Repro runs were NOT applied or projected, per the compare-only gate.
- New generations: W0 (8 games/16 teams/16 states), W1 (51/94/102), W2 (100/137/200). Priors counts (32/188/274) scale with participating teams as designed.
- Week-tab design preserves 7ba4582 no-drift semantics: exact-cutoff queries, no source pin on history; unknown future cutoffs keep date labels (zero code change for new data); retired `post-N` params resolve to the certified week generation.
- Early-tab partial coverage (16/94/137 teams) resolves via source-pinned preseason priors, restoring the original 09-26 "all 138 teams every period" behavior with honest fallback lineage.

## Work Completed
1. Bundles `season-2026-w{0,1,2}-inputs.json` (Preview R2, constructed from the pin table by construction).
2. Per cutoff: repair (verified v3, live state) → measurements (verified) → replay (verified, frozen candidate).
3. W3/W4 repro preflights + digest comparison (identical; not applied).
4. `project-v5-ratings` ×3 to Preview (48/290/474 rows) and ×3 to production (same); integrity re-verified (5 cutoffs, old 138/138 intact, active run published, `/api/health` ok).
5. `web/src/lib/v5.ts`: `WEEK_GENERATIONS` map, week labels, `postWeek` meta, `getPreseasonPriors` helper, frozen-branch backfill, retired-param resolution, shared `RATING_SELECT`.
6. `web/src/lib/ratings.test.ts`: new timeline/priors/param test. No `page.tsx` change needed (renders periods generically).

## Files Modified
- `web/src/lib/v5.ts`, `web/src/lib/ratings.test.ts` (uncommitted)
- `session_logs/2026-09-27/20-ratings-history-execution.md` (this record, untracked)

## Validation
- [x] Repair v3 verifiers: 8/51/100 games, live state, no producer imports
- [x] Measurements verifiers ×3 + replay verifiers ×3: all `verified`
- [x] W3/W4 digest equality (6/6 SHAs)
- [x] Preview + production 5-cutoff resolvability; old rows unchanged; health ok
- [x] `test:publication` 29 pass; `web:lint`, `typecheck`, `build` green; `contracts-check`; `git diff --check`
- [ ] Commit + CI + Vercel deploy
- [ ] Live `/ratings` readback: 6 tabs, per-tab spot values, 138-team lists

## Amendments and Blockers
None. No scope deviation; compare gate behaved as designed.

## Handoff Notes
- **Resume at:** Commit the two web files + this log; watch CI; verify live tabs after deploy; then flip the contract to Implemented.
- **Watch out for:** First live deploy of the new tabs — confirm Post-Week 0 shows 16 rated + 122 prior teams (not 16), and the default view is still Post-Week 4 unchanged.

**tags:** ["v5", "ratings", "history", "projection", "web", "execution"]
