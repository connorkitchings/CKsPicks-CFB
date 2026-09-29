# Session: Intended-update Preview runs and Week 5 live preflight

## TL;DR
- **Worked On:** Continued Task 6 Preview rehearsal after packaging commit `10eba25`.
- **Outcome:** Published all five completed-week standard prediction/scored packages to Preview R2, registered exact Preview authorizations, and published/scored the 215 replacement games in Preview Neon without changing any selection. Built and locally verified a Week 5 pending serving candidate from the pinned September 27 market capture.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (in progress).
- **Approval / Status:** User authorized implementation and continuation of Preview rehearsal. No production mutation or activation in this session.
- **Blockers:** Week 5 live serving/verifier/package code needs a user-executed commit before immutable R2 publication. A final market refresh and freeze gate remain before prospective production release. Full atomic Preview selection and rollback have not run.
- **Next:** Commit live serving code, publish its exact Preview R2 artifacts, authorize/publish Week 5, then rehearse the full six-week batch and rollback.

## Context and Decisions
- Committed W0–4 package hashes were reproduced exactly and applied to Preview R2. Signed-chain authorization preflight passed for each; the Preview migrator inserted one successor model approval and five environment-scoped run authorizations. Pipeline-role readback matched all five exact run IDs.
- Preview publication used the restricted `cks_preview_pipeline` role, an explicit `DATABASE_URL=$PREVIEW_DATABASE_URL` inside the Keychain wrapper, and `--no-update-current`. All five runs reached `published`, with exact game counts 8/43/49/57/58 and quote-selection counts 16/86/98/113/116 (Week 3's total gap is pinned).
- Scoring produced 199 spread and 159 total grade rows; the five successor runs are `scored`. Preview's old selected runs contain zero run-specific grade rows, so its pre-selection `system_stats` remains zero. This is a Preview baseline limitation; production old/new score comparison must use a read-only production baseline. The old Preview selections remain in place.
- The existing Week 5 forecast is a signed `candidate` with 56 games, from a September 27 source; first kickoff is 2026-10-02T00:00Z. The local live serving dry-run has 56 spread and 56 total lines, and its independent quote/forecast verifier passes. It is a rehearsal candidate, not proof of final market freshness or a production freeze.
- A read-only cross-branch comparison paired all 215 production-selected completed games with the Preview successor by `(week, game_id)`. All 215 spread and total forecast values changed; mean absolute changes are 4.823 margin points and 0.850 total points (max 25.206 and 3.333). Production's selected grades are spread 94–105–3 and total 87–78–0; successor Preview grades are spread 93–103–3 and total 82–77–0. Different bet counts reflect the new edges/No-Bet labels; this is not a prospective performance claim.

## Work Completed
- Added a separate Week 5 live serving builder, independent verifier, and pending-run package adapter. Each binds forecast, rating, bridge, market, game keys, first kickoff, and signed source hashes. Apply paths require clean committed code and reviewed output SHAs; serving/package apply reject a closed kickoff window.
- Extended the Preview-only exact authorization tool to permit Week 5 pending evidence and added a focused pending-record regression check.

## Files Modified
- `scripts/pipeline/build_v5_intended_update_live_serving.py` — deterministic pending serving artifact from pinned pre-kickoff parents.
- `scripts/pipeline/verify_v5_intended_update_live_serving.py` — independent quote, forecast, market, and timing verification.
- `scripts/pipeline/package_v5_intended_update_live_run.py` — standard pending run package for Preview.
- `scripts/pipeline/authorize_v5_intended_update_preview.py` — Week 5 authorization support.
- `tests/test_intended_update_rehearsal_package.py` — pending authorization coverage.

## Validation
- [x] W0–4 immutable R2 artifact readback and exact signed authorization validation.
- [x] Preview Neon: 215 new prediction rows, 215 scored games, 199 spread and 159 total grades, no changed selected run.
- [x] Read-only production/Preview pairing: all 215 keys matched; forecast shifts and old/new grade summaries recorded above.
- [x] Week 5 local serving preflight: 56/56/56 games/spreads/totals; verifier receipt `4edd933b…`, serving manifest bytes SHA `104729ac…`.
- [x] Focused tests: 72 passed; Ruff format/lint and `git diff --check` passed.
- [ ] Week 5 immutable R2 apply, authorization, Preview publication/freeze, complete batch selection and rollback, exact production packet.

## Amendments and Blockers
- Complete six-week selection cannot proceed with only W0–4 replacement runs; the batch contract correctly rejects a mixed old/new active-week set. Week 5 pending serving must be packaged separately from completed-week scored serving.
- Preview old runs lack run-specific grades, so the Preview rollback restores its old zero-stat baseline; production's old score baseline must be compared read-only rather than inferred from Preview.

## Handoff Notes
- **Resume at:** User-executed commit of the new live-serving code; apply the reviewed Week 5 serving and verifier to Preview R2, then package/authorize/publish the pending run.
- **Watch out for:** The Week 5 source is from 2026-09-27. Refresh markets and re-evaluate the exact prospective packet before any production freeze/selection. Never label this candidate as final prospective evidence without its freeze gate.

**tags:** ["v5", "ratings", "preview", "live", "release", "task6"]
