# Session: V5 intended-update Preview batch rehearsal

## TL;DR
- **Worked On:** Continued Task 6 after the Week 5 serving code was committed at `b8bb099de1c84be067bf32055797b9954875947d`.
- **Outcome:** Published and independently verified the Week 5 package, froze it in Preview, atomically selected Weeks 0–5, tested full rollback and reactivation, and repaired a stale performance-page readback.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (Task 6 in progress).
- **Approval / Status:** User authorized implementation and Preview rehearsal. Production release still requires a separate exact packet decision.
- **Blockers:** September 27 market capture must be refreshed before a production Week 5 release; production packet and release decision remain open.
- **Next:** Re-read production state and fresh markets, build exact production and rollback packets, then present the release decision before any production successor authorization or selection.

## Context and Decisions
- Preview 0018 was already present; production 0018 remains the previously reviewed additive migration, with no successor production authorization or selection.
- Preview originals have no run-specific grades, so their rollback statistics are zero. Production originals have nonzero grades; their read-only baseline is spread 94–105–3 and total 87–78–0.
- Week 5 remains uncompleted and ungraded. The Preview freeze is a timing and workflow rehearsal; its September 27 quotes are not automatically final production market evidence.

## Work Completed
- Applied the signed Week 5 serving artifact SHA `104729ac…`, independent receipt `4edd933b…`, and standard pending packet `32918f91…` to Preview R2. Inserted run-specific Preview authorization and published all 56 predictions without selecting the run.
- Atomically selected replacement runs for Weeks 0–5, froze Week 5 before kickoff, rolled all six back, and reactivated them. The exact readbacks and counts are in `docs/plans/2026-09-29/v5-intended-update-preview-rehearsal.md`.
- Verified local Preview-backed ratings and predictions pages. Found the performance page serving a build-time original record; switched it to request-time rendering and counted completed games only. It now reads 215 games, 93–103–3 spread, and 82–77–0 total.

## Files Modified
- `web/src/app/performance/page.tsx` — request-time performance rendering.
- `web/src/lib/v5.ts` — completed-game count excludes unfinished Week 5.
- `docs/plans/2026-09-29/v5-intended-update-preview-rehearsal.md` — exact Preview evidence and remaining gates.
- `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — implementation log pointer.
- This session log.

## Validation
- [x] Preview select, rollback, and reactivation readbacks; Week 5 frozen with no grades.
- [x] 75 focused Python tests, 38 web publication tests, TypeScript, contracts validation, Ruff format/lint, and Next.js build.
- [x] Local Preview-backed ratings, predictions, and performance page readback.
- [x] Documentation build and `git diff --check`.
- [ ] Strict documentation build: 10 existing cross-directory link warnings.
- [ ] Fresh prospective market capture and exact production release packet.

## Amendments and Blockers
- The performance page was statically prerendered with an old database record and could display a mismatched season score after atomic selection. Dynamic rendering now follows the selected run set.
- Production is unchanged by this rehearsal, aside from the previously reviewed additive migration 0018.

## Handoff Notes
- **Resume at:** Fresh Week 5 market/schedule readback and production selection baseline. Rebuild and sign the prospective package if still before its freeze boundary; otherwise target the next unstarted slate.
- **Watch out for:** Do not use Preview's original run IDs or zero-score fixture as the production rollback packet. Do not score Week 5 until certified finals.

**tags:** ["v5", "ratings", "preview", "release", "rehearsal"]
