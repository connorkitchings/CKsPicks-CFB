# Session: Stage 6B Task 3 Sequential Run

## TL;DR
- **Worked On:** Fresh Stage 6B Task 3 preflight and sequential build/verify on committed HEAD `e980e7a2c0abc7c9ef9b0259fca0b42d51206139`.
- **Outcome:** Preflight and Stages 1–8 passed. Stage 9 stopped on an actual Preview selection/grade side disagreement in Week 5 p2. No Stage 9 manifest was written and Stages 10–12 were not run.
- **Plan Contract:** [Stage 6B completed-week reconstruction](../../docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md), Amendment 2.
- **Approval / Status:** User authorized fresh sequential Task 3 execution after the Stage 9 repair commit. Stage 6B remains In Progress.
- **Blockers at this run:** Stage 9 stopped on five Week 5 p2 selection/grade side pairs. The user subsequently traced them to Known Issue 6 and directed an exact-key exception.
- **Next:** Commit the Known Issue 6 repair documented in `session_logs/2026-10-06/03-stage6b-known-issue6-repair.md`; then archive this partial run and start fresh preflight from the new HEAD.

## Context and Decisions
- Used only `zsh scripts/ops/with_preview_env.sh` for Preview DB and R2 access. Database queries were read-only. Stage artifacts were written only under local `artifacts/rebuild/6b-replay-20261005-r1/`.
- Fresh preflight passed for HEAD `e980e7a2c0abc7c9ef9b0259fca0b42d51206139` with preflight manifest SHA `f36d6d3fed05b9bd0f782297210f0ece0db5afdc92ccbddd0f58e730158ef64e`.
- `foundation`, `scoring_events_2026`, `offsets_2026`, `states_at_cutoff`, `application_frames`, `predictions`, `markets`, and `finals` each built and verified successfully.
- `old_grade_reproduction` stopped with `Preview grade reproduction or source identity mismatch: 2026w5-v5repair-20260929-p2 401858245 spread` before writing its manifest. The orchestration stopped there; no grading, comparison, receipt, publication, or production/serving write occurred.
- Read-only inspection found five Week 5 p2 Preview pairs where `prediction_market_selections.side` differs from `prediction_grades.side`: `(401858245, spread)`, `(401858247, total)`, `(401862788, spread)`, `(401862788, total)`, `(401864513, spread)`.
- For the first key, Preview selection side is `home` at point `-3.5`, but stored grade side is `away` with result `win`. The pinned served CSV labels this target `no bet` (edge `0.0754169598`); the final is Virginia Tech 33, Pittsburgh 35, so the stored `away/win` grade is consistent with the final while the current Preview selection's `home` side is not. This is an internal Preview selection/grade disagreement, beyond the 86 CSV-versus-Preview policy exceptions already defined in Amendment 2.
- The Stage 9 gate was left fail-closed. No source rows were modified or coerced, and no downstream stage was run.

## Resolution after this run
- The user identified the five differences as the exact Known Issue 6 publisher fallback rows documented before Week 5. The frozen publisher populated `home`/`over` for null leans; the later grades-only backfill graded the mathematical `away`/`under` direction.
- Amendment 2 and Stage 9 now validate those exact five keys and sides, regrade using the stored mathematical grade side, and reject any additional mismatch. Fixture and full-suite validation passed; the new live run remains pending a user commit.
- The `e980e7a` partial staging directory has been archived at `artifacts/rebuild/6b-replay-20261005-r1.stages1-8-at-e980e7a-stage9-stop` (eight verified stage manifests; no Stage 9 manifest).

## Work Completed
- Captured a fresh preflight for the committed code SHA.
- Built and independently verified the first eight stages sequentially.
- Queried the implicated Preview records read-only and compared them with the pinned, hash-verified Week 5 CSV rows and rebuilt finals.
- Recorded the stopping point and the specific unresolved data keys.

## Files Modified
- `session_logs/2026-10-06/02-stage6b-task3-run.md` — Task 3 execution and Stage 9 stop evidence.

## Validation
- [x] Fresh preflight passed on `e980e7a2c0abc7c9ef9b0259fca0b42d51206139`.
- [x] Stages 1–8 each built and passed their persisted verifier.
- [x] Preview diagnostic queries ran through the required wrapper in read-only mode.
- [ ] Stage 9 dual-baseline gate — stopped on Preview source identity/grade mismatch.
- [ ] Stages 10–12 and final persisted verification — not run because Stage 9 failed.
- [ ] `git diff --check`

## Amendments and Blockers
- No contract policy or source identity was changed in this session. Amendment 2 does not define these five Preview selection-versus-grade discrepancies as accepted exceptions; treating them as such would weaken the current zero-unexplained-mismatch gate without evidence.
- Task 3 remains blocked at Stage 9 pending authoritative reconciliation of the Preview selection and grade records.

## Handoff Notes
- **Resume at:** Investigate the historical write path for the five Week 5 p2 mismatches and determine whether Preview selections or grade sides represent the intended October 2 baseline. Then amend the contract if required, implement a narrowly evidenced rule, and rerun from fresh preflight after commit.
- **Watch out for:** Keep Stage 9 fail-closed until the Preview baseline itself is reproducible; do not proceed to Stages 10–12 or publication.

**tags:** ["rebuild", "stage6b", "stage9", "preview", "data-integrity"]
