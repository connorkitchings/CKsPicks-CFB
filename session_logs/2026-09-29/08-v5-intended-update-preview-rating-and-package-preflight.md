# Session: Intended-update Preview rating projection and package preflight

## TL;DR
- **Worked On:** Task 6 Preview rehearsal after the migration/authorization fix commit.
- **Outcome:** Reverified the already-published R2 bridge, rating, and serving chains. Projected 1,370 verified successor rating snapshots to Preview Neon. Built a fail-closed adapter for standard prediction/scored run artifacts and a Preview-only exact authorization command; all five completed-week packages pass read-only preflight.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (in progress).
- **Approval / Status:** User accepted keeping production 0018 and continuing Preview. No production activation or additional production mutation.
- **Blockers:** New packaging and authorization code must be committed before immutable Preview R2 run publication. Preview authorization, run publication, scoring, batch selection, rollback/reactivation, and exact production packets remain open.
- **Next:** User-executed commit; publish exact standard Preview prediction/scored artifacts, insert Preview-only authorization with the migrator role, then publish and score runs before atomic selection.

## Context and Decisions
- HEAD `d3ce871` was clean on entry. Preview 0018 already existed with its committed checksum. R2 already held the bridge, 2026 rating generations, six forecast manifests (Week 5 still candidate), and five completed-week serving artifacts with verifier receipts.
- Independent read-only R2 verification passed: bridge historical states 35,740; rating generation maximum numerical difference `6.66e-16`; serving game counts 8/43/49/57/58.
- Preview Neon had no successor rating rows, approvals, authorizations, or prediction runs. Ratings projection appended 680 pregame and 690 current rows under rating SHA `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b`. Read-only post-check confirmed those counts, 138 teams, zero successor authorizations, and zero successor runs.
- The research serving artifacts are not standard `prediction_run_v1` or scored run artifacts; the new adapter bridges that existing Task 6 gap and checks every signed source, verifier, quote parent, forecast value, game key, and child SHA before publication.
- Week 5 remains a candidate. A prospective freeze requires a fresh source/kickoff gate; it is not included in the completed-week packaging adapter.

## Work Completed
- Added a versioned successor serving config and deterministic Preview run/scored package builder. Apply requires exact reviewed packet SHA and clean expected commit; production packaging is excluded until a separate decision.
- Added Preview-only admin authorization tooling that validates each exact R2 chain before inserting the new model pair and run authorization. It requires the exact Preview migrator role and checked record SHA.
- Added a publisher guard that rejects a successor run if its committed serving config changes.
- Read-only package preflight passed for Weeks 0–4: 215 games, lined counts 8/43/49/56/58; the Week 3 missing total is the pinned allowed gap.

## Files Modified
- `conf/weekly_bets/v5_intended_update_2026.yaml` — versioned serving identity and thresholds.
- `scripts/pipeline/package_v5_intended_update_runs.py` — standard immutable run/scored packaging.
- `scripts/pipeline/authorize_v5_intended_update_preview.py` — exact Preview-only admin authorization.
- `scripts/pipeline/publish_to_db.py` — successor serving config checksum gate.
- `tests/test_intended_update_rehearsal_package.py`, `tests/test_publish_to_db.py` — focused regression checks.

## Validation
- [x] Independent R2 bridge, rating, and serving verifiers passed read-only.
- [x] All five standard package preflights passed read-only.
- [x] Preview Neon projection readback: 1,370 rows, correct rating SHA, no successor run selected.
- [x] Focused Python tests, Ruff format/lint, and `git diff --check` before handoff.
- [ ] Immutable package `--apply`, Preview admin authorization, publication/scoring, batch selection, rollback/readback, exact production packets.

## Amendments and Blockers
- Task 6 needs a committed adapter from verified research serving output to standard operations artifacts. This was absent from the Task 5 preflight and has now been implemented but not yet applied.
- The original Week 5 forecast is only `candidate`; do not present it as frozen prospective evidence.

## Handoff Notes
- **Resume at:** Commit current code, then generate and review exact package SHAs with `package_v5_intended_update_runs.py` and apply each to Preview R2. Generate Preview authorizations after artifacts exist.
- **Watch out for:** `CFB_STORAGE_BACKEND=r2`, Preview Keychain wrapper, `PYTHONPATH=.:src`, and clean code SHA are required. Do not run `make migrate-db` or write to production.

**tags:** ["v5", "ratings", "preview", "release", "task6"]
