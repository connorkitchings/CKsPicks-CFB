# Session: V5-11B Ratings Rebuild from r9 (Implementation)

## TL;DR
- **Worked On:** Terra execution of `docs/plans/2026-09-21/03-v5-11b-possession-ratings-r9-rebuild.md`.
- **Outcome:** Contract 11B fully **Implemented**. Preview run `possession-v1-ratings-20260921-11d59ee-r9cert` completed preflight → apply → independent verification → idempotent repeat. Retained candidate: `ppp__rho_0_60__exposure` — **no selection flip** from the r6 run. All 8 DoD items pass (5 contract + lifecycle/test updates).
- **Plan Contract:** `docs/plans/2026-09-21/03-v5-11b-possession-ratings-r9-rebuild.md` (Status: Implemented)
- **Approval / Status:** User authorized Terra execution ("done, proceed"). Awaiting user review of the retained manifest as the 11C entry gate.
- **Blockers:** None.
- **Next:** Fresh Terra task → `implement-plan` → `docs/plans/2026-09-21/04-v5-11c-forecast-bridge-and-final-fit.md`, binding the rating parent below.

## Context and Decisions
- Reconciliation resolved the r9 parent identity from R2 (read-only): measurement manifest `certification_sha256 = fc26a3d0...` (equals r9 `certification.json` `manifest_sha256`); repair parent unchanged.
- Pin swap renamed `REQUIRED_R6_CERTIFICATION_SHA256` → `REQUIRED_R9_CERTIFICATION_SHA256` (stale name would be dangerous) plus the run-id pin and both test fixtures; historical lanes (forecast/conditional/shadow/audit pins) untouched.
- Preflight: 60/60 candidates ok, 8,935 eligible games, 758,160 bridge rows, selection `ppp__rho_0_60__exposure` (selection SHA `93ad3f5f...`). Apply published the retained manifest; verifier reconstructed everything (`status: verified`); repeat returned `already_applied`.
- Full suite initially failed on `test_historical_first_contracts_preserve_lifecycle_and_gate_2026_application`, which pinned umbrella 11 at `status: draft`. Updated the pinned expectation to `status: approved` — the promotion was user-authorized via the decomposition. Full suite green after.

## Certified Evidence
- **Run ID:** `possession-v1-ratings-20260921-11d59ee-r9cert` (code SHA `11d59ee...`)
- **Retained manifest:** `artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260921-11d59ee-r9cert/retained-rating-manifest.json` (raw SHA `9d00e635...`, `manifest_sha256: 2f1cdc5f...`, state `frozen`, selected `ppp__rho_0_60__exposure`)
- **Verifier manifest:** `.../verification/verifier-manifest.json` (raw SHA `85d1ae64...`, status `verified`)
- **Parents:** r9 measurements (`certification_sha256 fc26a3d0...`) + `repair-v2-20260909T1417Z`
- **11C parent binding (resolve from the run, never hand-type):** rating manifest URI above; run-id `possession-v1-ratings-20260921-11d59ee-r9cert`; candidate `ppp__rho_0_60__exposure`.

## Work Completed
- Swapped ratings-layer pins to r9 (constant rename + run-id + comments) and both test fixtures.
- Executed Preview preflight/apply/verify/repeat for the 60-candidate tournament.
- Fixed the documentation-authority lifecycle test for the authorized umbrella promotion.
- Updated 11B contract to Implemented (DoD checked) and the index row.

## Files Modified
- `src/cks_picks_cfb/data/data_first_possession_rating_v1.py` — r9 pin swap + rename
- `tests/test_data_first_possession_rating_runner.py` — fixture pins
- `tests/test_possession_rating_verification.py` — fixture pins
- `tests/test_data_first_documentation_authority.py` — umbrella-11 lifecycle expectation draft → approved
- `docs/plans/2026-09-21/03-v5-11b-possession-ratings-r9-rebuild.md` — In Progress → Implemented
- `docs/plans/index.md` — 11B row Implemented with evidence
- `session_logs/2026-09-21/07-v5-11b-ratings-r9-rebuild.md` — this log

## Validation
- [x] Focused ratings suites — 14 passed
- [x] Full suite — 1212 passed, 2 skipped (confirmed after lifecycle-test fix)
- [x] `uv run ruff check` + format on touched paths — clean
- [x] Preflight exit 0; apply `applied`; verify `verified`; repeat `already_applied`
- [x] `uv run python contracts/validation.py` — passed
- [x] `uv run mkdocs build --strict --quiet` — passed
- [x] `git diff --check` — clean

## Amendments and Blockers
- None. No selection flip — recorded, no re-tuning (per contract).

## Handoff Notes
- **Resume at:** Fresh Terra task → `implement-plan` → 11C contract. 11B's retained identity above is the only accepted parent.
- **Watch out for:** 11C's runner is fail-closed on the pin chain — verify ratings-layer pins accept r9 before touching forecast pins. Rating phases run ~10–12 min each; use extended timeouts.

**tags:** ["v5", "contract-11b", "ratings", "publication", "verified"]
