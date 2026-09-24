# Session: V5 replay and Preview rehearsal implementation

## TL;DR
- **Worked On:** Implemented the approved `docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md` end to end: Task 1 rollback-capable web code, Task 2 immutable Weeks 0–3 replay, Task 3 Preview publish/score/select, Task 4 populated Preview serving plus V4 rollback and V5 restoration.
- **Outcome:** All four tasks pass with recorded evidence. Week 0 V5 replay run `2026w0-cb2252a0w0v5` is published, scored, and explicitly selected on Preview; the Preview deployment rendered V5, a legacy fallback, true V4-strict, then V5 again. V4 still serves production; no production writes occurred.
- **Plan Contract:** `docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md` (Implemented).
- **Approval / Status:** User authorized implementation and all four tasks; user executes all git operations. Two user-directed amendments recorded in the plan (deploy-then-verify ordering; rollback-target lineage correction).
- **Blockers:** None open. User must re-enable Vercel Deployment Protection (was temporarily disabled for the rehearsal).
- **Next:** User re-enables Vercel auth and runs the closing commit; Week 4 07/08 refresh remains the next V5 dependency (outside this contract).

## Context and Decisions
- Checkpoint 1 (rollback-capable code): `cb2252a8cd56bfe30abc082fd0681f650cb7be16`. Checkpoint 2 (replay pin): `5d2ff6cb1b326716ead61cda0ffe7f97f2b944d8`. Worktree was verified clean before replay apply.
- Replay run `v5-replay-20260924-cb2252a` from exact Contract 07/08 parents: measurement `possession-v1-measurements-20260922-2026c`, rating replay `possession-v1-rating-replay-20260922-fcaa571`, bridge `forecast-v1-20260921-5afd577-11c`, pinned inference bundle `f80b63ef…`. Result: 157 games / 314 paired rows / 0 gaps, weeks 8/43/49/57, independent verification `verified: true` (digest `67910422…`), receipt idempotent across reruns.
- Immutable replay artifacts (Preview R2, `forecasts/replay-runs/v5-replay-20260924-cb2252a/`): predictions.csv `81b5e001…` (314 rows), gaps.csv `4752857f…` (empty), replay-manifest.json `3e32a091…` (pinned in `conf/weekly_bets/v5_replay_2026.yaml`, validated through the serving adapter), verifier receipt `1cfc7d43…`.
- Pipeline runs: publish `cb2252a0w0v5` → prediction run `2026w0-cb2252a0w0v5`; score `cb2252a0w0sc` with certified Silver `game_outcomes` ref `lake/silver/dataset=game_outcomes/version=669856aa8ebddabfd5cd8ff4` from the certified repair chain. Publish and score commands were each run twice with stable IDs to prove resume behavior.
- Published/scored state: run `2026w0-cb2252a0w0v5` is `scored`, `evidence_class=replay`, 8/8 predictions, 8/8 finals, verified artifact, `frozen_at` NULL (no prospective freeze), 0 grades (no market lines — anticipated). `current_week` untouched throughout (`2025, 16, v4replay-2025-w16`).
- Selection history (Preview): V5 select 15:30:22Z → V2-preview drill 15:47:51Z → V4-strict drill 15:56:07Z → V5 restore 15:56:20Z. Final selection is V5.
- Rollback lineage correction (Amendment 2): the plan named `2026w0-a0edb9e72cb1` as the V4 run; it is `Trench Warfare V2 Preview` (frozen, legacy, 8/8/8). Its selection proved fallback mechanics (health + page rendered its own label, 8 games, no V5 banner). The true V4 run `2026w0-3e4fa1b9b07d` (`Trench Warfare V4`, `week0-2026-v4-strict-20260818-r2`, published, 8/8/8) was then selected per user direction as the definitive rollback proof: reselection <1s, health instant, page within ~20s ISR.
- Binding proof (Amendment 1): the Vercel Preview `DATABASE_URL` is Sensitive (non-decryptable) and the `cks_preview_web` password is unrecoverable locally, so isolation was proven functionally on the fresh deployment `https://c-ks-picks-jts98vil5-connorkitchings-projects.vercel.app`: `/api/health` shows the Preview-only singleton `(2025, 16, v4replay-2025-w16)` and `?season=2026&week=0` shows the Preview-only selection (production has neither and lacks migration 0013).
- Populated serving evidence: Week 0 page (8 games, V5 label/banner/replay badge), 138 current rating rows on /ratings, populated /teams/Texas, replay/live split on /performance, selected-run health for V5/V4/missing cases.
- Preview env: added Preview-scoped `CFB_PUBLICATION_MODE=predictions` via API (required for the rehearsal; production untouched). Vercel Authentication was temporarily disabled for the checks and must be re-enabled by the user.

## Work Completed
- Task 1: `run-selection.ts` eligibility mirror, V4-capable `getRunForWeek`/`getAvailableWeeks` with `modelId` on `RunSummary`, V5-only banner gating, selected-week health endpoint, fixtures (V5 week + V4 week), 5 node + 10 Python + 2 new/1 rewritten e2e tests. Commit C.
- Task 2: dry-run → reviewed preflight (/tmp) → apply from clean checkpoint-1 SHA → double independent verification → pin validated through the serving adapter. Commit D.
- Task 3: preview preconditions (0013, policy, baseline), outcomes ref artifact, publish + resume, score + resume, explicit V5 selection with reason and history.
- Task 4: amendment, preview env mode, fresh Preview deployment, binding proof, populated checks, legacy + true-V4 rollback drills, V5 restoration.
- Closed the plan as Implemented with both amendments recorded.

## Files Modified
- `web/src/lib/run-selection.ts` — new render-eligibility predicate (Task 1, committed).
- `web/src/lib/run-selection.test.ts` — new unit tests (Task 1, committed).
- `web/src/lib/queries.ts` — V4-capable selection queries + `modelId` (Task 1, committed).
- `web/src/app/page.tsx` — V5-only banner, test-mode mode param (Task 1, committed).
- `web/src/app/api/health/route.ts` — selected-week health (Task 1, committed).
- `web/src/test/fixtures/publication.ts` — V5/V4 fixture weeks (Task 1, committed).
- `web/e2e/publication.spec.ts`, `web/package.json` — banner tests, test script (Task 1, committed).
- `tests/test_public_selection.py` — selection fallback semantics (Task 1, committed).
- `conf/weekly_bets/v5_replay_2026.yaml` — replay manifest pin (Task 2, committed).
- `docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md` — In Progress → Implemented, Amendments 1–2 (uncommitted).
- `docs/plans/2026-09-23/01-v5-product-transformation.md` — rehearsal checkpoint (uncommitted).
- `session_logs/2026-09-24/03-v5-replay-preview-rehearsal.md` — this log (uncommitted).

## Validation
- [x] Full pytest: 1310 passed, 2 skipped (incl. 10 new selection tests)
- [x] Ruff format + check; `git diff --check`
- [x] Contracts validation + `make contracts-check`; strict MkDocs
- [x] Web lint, typecheck, `test:publication`, production build; 6/6 Playwright UI tests
- [x] Replay: 157/314/0, exact parents, `verified: true`, byte-identical idempotent receipts
- [x] Preview: 8/8 predictions + finals, replay evidence, no freeze ts, singleton unchanged
- [x] Binding: preview-only singleton + preview-only selection on the fresh deployment
- [x] Serving: V5/V4-fallback/V4-strict/V5-restored all rendered with correct labels and banner behavior
- [ ] User re-enables Vercel Deployment Protection (pending user action)

## Amendments and Blockers
- Amendment 1: deploy-then-verify binding proof (user-authorized; Sensitive env value undecryptable).
- Amendment 2: rollback drill moved to the true V4 run (user-authorized; plan misattributed V2-preview run as V4).
- Pre-existing, untouched: ruff-format drift in 9 non-milestone files; stale 62d-old preview deployment; V4 production serving unchanged.

## Handoff Notes
- **Resume at:** Week 4 07/08 refresh after stabilized finals (next V5 dependency; outside this contract). Then Contract 09 forecast, serving rehearsal, V4 rollback proof on stabilized slate, separate activation decision.
- **Watch out for:** Do not treat this retrospective replay as prospective evidence. The `cks_preview_web` password remains unknown — future Preview serving work needs rotation or the user's saved credential. Preview deployment `jts98vil5` remains (SSO-walled once auth is restored).

**Suggested commit message:** `Complete V5 replay and Preview rollback rehearsal`

**tags:** ["v5", "replay", "preview", "rollback", "verification"]
