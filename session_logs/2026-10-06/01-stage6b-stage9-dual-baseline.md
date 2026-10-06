# Session: Stage 6B Stage 9 Dual-Baseline Repair

## TL;DR
- **Worked On:** Implemented user-directed Amendment 2 to the Stage 6B reconstruction contract and repaired Stage 9 to reconcile the September 29 immutable CSVs with the October 2 unconstrained Preview baseline.
- **Outcome:** Stage 9 independently verifies the 541 Preview grades, recomputes 455 active CSV grades, and validates 86 ungraded CSV rows without mutating either source. A fresh live run exposed one historical Week 5 graded row below the total threshold; the verifier was corrected to preserve CSV-grade status and test that threshold rules explain the actual ungraded rows.
- **Plan Contract:** [Stage 6B contract](../../docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md), Amendment 2; [Task 2 quality review](../../docs/plans/2026-10-05/02-stage6b-task2-quality-review.md).
- **Approval / Status:** User directed adoption of the dual-baseline rule on 2026-10-06. Stage 6B remains In Progress; user stages and commits.
- **Blockers:** The repaired code is uncommitted. A fresh live sequential Task 3 run is still required. Strict MkDocs warnings remain documented from the previous review.
- **Next:** User commits the repair. Archive the partial `8e10f19` stage 1–8 run, capture the new committed HEAD, then perform fresh preflight and sequential build/verify from foundation.

## Context and Decisions
- The previous live Task 3 run on `83b0de3` passed stages 1–8 and correctly stopped at Stage 9. Read-only evidence found 541 keys on both sources, with 86 side/result differences.
- Plan 04 documents that 2026-09-29 served CSVs preserve the constrained policy (spread edge 1.0; total lean 1.0 and grade edge 1.5), while its 2026-10-02 backfill updated Preview selections and grades to the unconstrained policy.
- Amendment 2 treats both as distinct authoritative historical baselines. It requires no unexplained differences and keeps every source read-only.
- The run on `8e10f19bff4fd6aa834551c9647aaeeecbcdc58d` passed fresh preflight (`20f1b573…`) and built/verified stages 1–8. Stage 9 stopped before producing a manifest because it classified a graded Week 5 row (game `401871089`, total edge `1.070459`, `under`/`loss`) as required No Bet. Read-only Preview evidence for the same key is `under`/`loss`, point 57.5, price -110, with the same quote and snapshot.
- The 86 actual ungraded `No Bet` rows are threshold-explained by week: 1, 14, 20, 15, 21 and 15 for Weeks 0–5. The Week 5 p2 graded row remains active as recorded and regrades correctly; it is not an unexplained CSV/Preview difference.
- Preview commands use `zsh scripts/ops/with_preview_env.sh`. No external writes occurred; all built stage artifacts are in local staging.

## Work Completed
- Added Amendment 2 with the dual-baseline gates and thresholds to the approved Stage 6B contract.
- Changed the Stage 9 builder to parse complete served target coverage, regrade active CSV rows, validate threshold-based No Bet/ungraded rows, recompute Preview selections/grades, and require exactly 455 active rows plus 86 explained exceptions.
- Changed the Stage 9 verifier to check exact gate evidence, rederive outputs from pinned artifacts/finals and read-only Preview rows, and compare the rederived bytes with persisted artifacts.
- Updated Stage 10 to require the new exact dual-baseline summary counts and gate.
- Updated the six-week fixture to represent the two historical policies and added direct summary/rederivation regressions.
- Corrected the CSV gate after live evidence showed that one graded Week 5 row is below the threshold; ungraded rows alone are subjected to the No Bet threshold test. The fixture now exercises this specific case.

## Files Modified
- `docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` — Amendment 2 and Stage 9 contract.
- `docs/plans/2026-10-05/02-stage6b-task2-quality-review.md`, `docs/plans/index.md` — review status and rerun gate.
- `src/cks_picks_cfb/rebuild/recon_grades.py` — dual-baseline build and persisted verification.
- `tests/test_rebuild_6b_flow.py` — fixture and regression coverage.
- `session_logs/2026-10-06/01-stage6b-stage9-dual-baseline.md` — this record.

## Validation
- [x] `uv run pytest tests/test_rebuild_6b_flow.py -q --no-cov` — 29 passed.
- [x] `uv run ruff check .` — passed.
- [x] Contract validation via `.venv/bin/python contracts/validation.py` — passed. `make contracts-check` itself could not access the sandbox-restricted uv cache.
- [x] Documentation build via `.venv/bin/python -m mkdocs build --quiet` — passed.
- [x] `git diff --check` — passed.
- [x] Full Python suite `.venv/bin/python -m pytest tests -q --no-cov` — 1,997 passed, 9 skipped.
- [x] Fresh Task 3 on `8e10f19`: preflight passed; stages 1–8 built and verified; Stage 9 stopped on the overstrict Week 5 threshold classification.
- [ ] Fresh Task 3 sequential run on the next committed HEAD (after user commit)

## Amendments and Blockers
- Amendment 2 was explicitly directed by the user and is recorded in the governing contract. No cutoff policy, data identity, model design, or write-scope change was made.
- The updated Stage 9 fixture passes the 455/86 split and the below-threshold graded Week 5 case, but does not establish live parity. A fresh committed-code run is mandatory.

## Handoff Notes
- **Resume at:** User stages and commits the Stage 9 correction. Archive local staging `artifacts/rebuild/6b-replay-20261005-r1` to a labeled `stages1-8-at-8e10f19-stage9-stop` directory, capture the new HEAD, and start fresh preflight.
- **Watch out for:** Never continue past a failed stage. Stage 10–12 and publication remain gated on Stage 9's exact dual-baseline verification.

**tags:** ["stage6b", "grade-reproduction", "integrity", "contract-amendment"]
