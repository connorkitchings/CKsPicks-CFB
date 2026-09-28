# Session: Ratings history live verification and contract closure

## TL;DR
- **Worked On:** Verified the deployed week tabs on production and closed the ratings-history contract as Implemented.
- **Outcome:** All six tabs live and correct (138 teams each; Indiana overall pre 1.20 / W0 1.20 / W1 1.67 / W2 2.02 / W3 2.03 / W4 1.88; ranks 1/1/2/1/1/3). Default view unchanged (Post-Week 4). Retired `?period=post-0` resolves to the Post-Week 0 tab. CI green on the deploy commit. Contract status → Implemented.
- **Plan Contract:** `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` (Implemented 2026-09-28).
- **Approval / Status:** Docs-only changes pending user commit. No production writes in this session.
- **Blockers:** None.
- **Next:** Commit closure docs → CI → Week 5 freeze gate remains the open operational item.

## Context and Decisions
- Post-deploy timeline initially showed date labels (old bundle serving) then week labels after Vercel finished — expected rollout lag, not a defect.
- An early row-count regex suggested Post-Week 2 had 137 teams; team-link set comparison proved 138/138/138 with zero set difference — measurement artifact in the check, not the page.
- Post-Week 0 Indiana (1.20) equals its preseason prior: correct — Indiana was idle Week 0, so the tab honestly shows its prior via fallback lineage.
- Added a 2-sentence history note to `v5_status.md` (additive only); docs-authority suite still 17/17.

## Work Completed
- Live readback of all six tabs + default view + retired-param resolution.
- Contract DoD checked with recorded values; status Implemented; index updated.
- `v5_status.md` history note.

## Files Modified
- `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` — Implemented status, checked DoD
- `docs/plans/index.md` — lifecycle entry
- `docs/modeling/v5_status.md` — history note (additive)
- `session_logs/2026-09-27/21-ratings-history-live-verification.md` — this record

## Validation
- [x] Live: 6 tabs × 138 teams; per-tab Indiana values/ranks; default = Post-Week 4 #3; retired param resolves
- [x] CI green on deploy commit `9a77ee1` (4m35s)
- [x] Docs-authority 17/17 after status edit; mkdocs build; `git diff --check`

## Amendments and Blockers
None.

## Handoff Notes
- **Resume at:** Commit the four files; then the Week 5 freeze gate (final capture + freeze before 2026-10-02T00:00Z) is the remaining operational work.
- **Watch out for:** Future weekly projections appear as date-labeled entries until given week labels — a one-line `WEEK_GENERATIONS` addition per week, no migration needed.

**tags:** ["v5", "ratings", "history", "verification", "contract-closure"]
