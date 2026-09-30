# Session: Refreshed V5 intended-update Preview release rehearsal

## TL;DR
- **Worked On:** Published the committed refreshed Week 5 p2 artifact chain, authorized/published it in Preview, and rehearsed the final six-week candidate set.
- **Outcome:** Preview atomically selects repaired scored Weeks 0–4 and refreshed frozen Week 5 p2. Full rollback and reactivation passed; site readback shows the new ratings, predictions, and completed-week scores together.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (Task 6 in progress).
- **Approval / Status:** User authorized implementation and Preview rehearsal. No successor production authorization, artifact publication, or selection.
- **Blockers:** Prepare production R2 graph and exact release/rollback packets; repeat fresh market check at decision and final freeze.
- **Next:** Build the exact production packet and present it for the separate release decision before any production successor write.

## Context and Decisions
- Clean committed code `446c8805dc474b0628c667549142be04c1fb6b87` generated the p2 forecast. The fresh Silver capture was pinned at `2026-09-29T20:28:55Z` with serving cutoff `20:29:00Z`, before Week 5's `2026-10-02T00:00:00Z` first kickoff.
- The first p2 Preview authorization attempt used a new decision reference and failed before insertion because the existing model approval carries the earlier Preview decision reference. Reusing the exact existing approved model decision reference succeeded; the run-specific authorization remains distinct.
- Production readback: migration 0018 present, zero successor production authorizations, original Week 0–5 runs selected, old season scores 94–105–3 spread and 87–78–0 total.

## Work Completed
- Published p2 forecast, serving artifact, verifier receipt, and standard pending run package to Preview R2. Exact hashes are in `docs/plans/2026-09-29/v5-intended-update-preview-rehearsal.md`.
- Authorized p2 in Preview and published 56 predictions with 112 new quote selections and no grades. Current selection was unchanged until the batch decision.
- Rolled Preview p1 six-week set back to originals, atomically selected repaired Weeks 0–4 plus p2 Week 5, froze p2 at `2026-09-29T20:43:53.376950Z`, then rolled that exact set back and reactivated it. Readback matched all six IDs and the shared rating SHA `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b`.
- Local Preview-backed home, ratings, and performance pages returned 200 and showed 56 Week 5 games, Post-Week 4 replacement ratings, and the replacement 215-game record (93–103–3 spread; 82–77–0 total).

## Files Modified
- `docs/plans/2026-09-29/v5-intended-update-preview-rehearsal.md` — final p2 Preview evidence and open production gates.
- `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — implementation log pointer.
- This session log.

## Validation
- [x] Exact p2 forecast/serving/verifier/package preflight hashes and Preview R2 readback.
- [x] Preview authorization, publication, 56/56 quote coverage, zero Week 5 grades.
- [x] Atomic six-week selection, rollback, reactivation, and selected-run/score/UI readback.
- [x] Read-only production baseline and zero successor authorization check.
- [ ] Exact production R2 promotion and release packet; fresh final market/freeze check.

## Amendments and Blockers
- The Preview run is frozen and internally consistent but remains a September 29 market observation. Current source availability must be rechecked at the production decision and again before the final freeze.
- No production successor mutation occurred.

## Handoff Notes
- **Resume at:** Exact production artifact graph/packet construction from the verified Preview chain and the current production rollback IDs.
- **Watch out for:** Production and Preview credentials intentionally share one R2 bucket, but their prediction/scored artifact paths and Neon branches differ. Do not use Preview output paths or Preview original selection IDs in the production packet. Week 5 has no final score or grade.

**tags:** ["v5", "ratings", "preview", "release", "week5"]
