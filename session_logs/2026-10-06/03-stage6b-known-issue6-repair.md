# Session: Stage 6B Known Issue 6 Reconciliation

## TL;DR
- **Worked On:** Incorporated the user's Known Issue 6 provenance into Amendment 2 and Stage 9.
- **Outcome:** Stage 9 now allows only the exact five documented Week 5 p2 publisher-default sides, validates the `home`/`over` fallback against `away`/`under` mathematical grades, and recomputes grades/profit using `prediction_grades.side`. Any other selection/grade side disagreement still fails.
- **Plan Contract:** [Stage 6B contract](../../docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md), Amendment 2.
- **Approval / Status:** User directed the exact Known Issue 6 reconciliation on 2026-10-06. Stage 6B remains In Progress; all Git operations remain user-run.
- **Blockers:** Fresh live Task 3 is pending a user commit.
- **Next:** User commits the repair, captures the resulting HEAD, and executes fresh preflight followed by sequential build/verify from Stage 1.

## Context and Decisions
- Known Issue 6 in `docs/data/known_issues.md` documented before Week 5 that null-lean rows received publisher fallback sides (`home`/`over`) in `prediction_market_selections`; the later grades-only backfill used mathematical sides (`away`/`under`) for the exact five keys. No Preview mutation is permitted or needed.
- The Stage 9 Preview baseline requires equal selection/grade sides for the other 536 rows. For the exact five, it validates the fallback side, validates the mathematical grade side against pinned prediction and line, then recomputes result/profit from that grade side and pinned finals.
- The five exception keys are persisted as explicit Stage 9 summary evidence and checked exactly by the persisted verifier and Stage 10 gate. The exact set is: Week 5 p2 `401858245/spread`, `401858247/total`, `401862788/spread`, `401862788/total`, `401864513/spread`.
- No Preview or production data was written during this session.
- Archived the failed `e980e7a` partial staging directory as `artifacts/rebuild/6b-replay-20261005-r1.stages1-8-at-e980e7a-stage9-stop`; verified it contains the eight prior stage manifests and no Stage 9 manifest.

## Work Completed
- Added the exact Known Issue 6 exception map and mathematical-grade rederivation in `recon_grades.py`.
- Added exact exception records/count and a required gate to the Stage 9 summary and persisted verifier; Stage 10 now requires that evidence.
- Updated Amendment 2 with the narrow five-key rule and the Task 3 run record.
- Extended the six-week real-orchestrator fixture with all five Known Issue 6 rows and regressions for altered sides, any unlisted side mismatch, and tampered persisted exception evidence.
- Updated the Task 2 review and added the Task 3/repair logs.

## Files Modified
- `docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` — Amendment 2 rule and execution record.
- `docs/plans/2026-10-05/02-stage6b-task2-quality-review.md` — status and evidence.
- `src/cks_picks_cfb/rebuild/recon_grades.py` — fail-closed exception handling and independently checked receipt evidence.
- `tests/test_rebuild_6b_flow.py` — full fixture and regression coverage.
- `session_logs/2026-10-06/02-stage6b-task3-run.md` — preceding live Stage 9 stop record.
- `session_logs/2026-10-06/03-stage6b-known-issue6-repair.md` — this repair and handoff.

## Validation
- [x] `.venv/bin/pytest tests/test_rebuild_6b_flow.py -q --no-cov` — 34 passed.
- [x] `.venv/bin/pytest tests -q --no-cov` — 2,002 passed, 9 skipped.
- [x] `.venv/bin/ruff check .` — passed.
- [x] `.venv/bin/ruff format --check src/cks_picks_cfb/rebuild/recon_grades.py tests/test_rebuild_6b_flow.py` — passed.
- [x] `.venv/bin/python contracts/validation.py` — passed.
- [x] `.venv/bin/python -m mkdocs build --quiet` — passed.
- [x] `git diff --check` — passed.
- [ ] Fresh committed-HEAD Task 3 preflight and sequential stage run.

## Amendments and Blockers
- Amendment 2 now explicitly admits only the five exact publisher-default rows already documented by Known Issue 6. All other source mismatches remain hard failures. No cutoff, data identity, model design, or write scope changed.
- Stage 9–12 live execution and publication remain pending the new commit and clean sequential rerun.

## Handoff Notes
- **Resume at:** After the user commit, capture the new HEAD, run fresh preflight into a clean `artifacts/rebuild/6b-replay-20261005-r1/`, and build/verify each stage sequentially, stopping at the first failure.
- **Watch out for:** The exception applies only to those exact five Stage 9 selection/grade keys. Never widen it by generic `home`/`over` fallback or continue downstream after another mismatch.

**tags:** ["rebuild", "stage6b", "stage9", "known-issue-6", "grade-reproduction"]
