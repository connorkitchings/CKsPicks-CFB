# Session: Stage 6B Stage 9 Dual-Baseline Repair

## TL;DR
- **Worked On:** Implemented user-directed Amendment 2 to the Stage 6B reconstruction contract and repaired Stage 9 to reconcile the September 29 immutable CSVs with the October 2 unconstrained Preview baseline.
- **Outcome:** Stage 9 now verifies the 541 Preview grades independently, recomputes 455 active CSV grades, and validates 86 historical threshold exceptions without mutating either source. Fixture tests exercise the dual baseline through the actual orchestrator.
- **Plan Contract:** [Stage 6B contract](../../docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md), Amendment 2; [Task 2 quality review](../../docs/plans/2026-10-05/02-stage6b-task2-quality-review.md).
- **Approval / Status:** User directed adoption of the dual-baseline rule on 2026-10-06. Stage 6B remains In Progress; user stages and commits.
- **Blockers:** Focused validation and a fresh live sequential Task 3 run are still required. Strict MkDocs warnings remain documented from the previous review.
- **Next:** Finish focused/full checks, then the user commits. Archive the current partial run, capture the committed HEAD, and perform fresh preflight and sequential build/verify from foundation.

## Context and Decisions
- The previous live Task 3 run on `83b0de3` passed stages 1–8 and correctly stopped at Stage 9. Read-only evidence found 541 keys on both sources, with 86 side/result differences.
- Plan 04 documents that 2026-09-29 served CSVs preserve the constrained policy (spread edge 1.0; total lean 1.0 and grade edge 1.5), while its 2026-10-02 backfill updated Preview selections and grades to the unconstrained policy.
- Amendment 2 treats both as distinct authoritative historical baselines. It requires no unexplained differences and keeps every source read-only.
- Preview role access is not used by these fixture tests. Any live Preview command must use `zsh scripts/ops/with_preview_env.sh`; no live stage was run in this session.

## Work Completed
- Added Amendment 2 with the dual-baseline gates and thresholds to the approved Stage 6B contract.
- Changed the Stage 9 builder to parse complete served target coverage, regrade active CSV rows, validate threshold-based No Bet/ungraded rows, recompute Preview selections/grades, and require exactly 455 active rows plus 86 explained exceptions.
- Changed the Stage 9 verifier to check exact gate evidence, rederive outputs from pinned artifacts/finals and read-only Preview rows, and compare the rederived bytes with persisted artifacts.
- Updated Stage 10 to require the new exact dual-baseline summary counts and gate.
- Updated the six-week fixture to represent the two historical policies and added direct summary/rederivation regressions.

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
- [x] Full Python suite `uv run pytest tests -q --no-cov` — 1,997 passed, 9 skipped.
- [ ] Fresh Task 3 sequential run on the newly committed HEAD (after user commit)

## Amendments and Blockers
- Amendment 2 was explicitly directed by the user and is recorded in the governing contract. No cutoff policy, data identity, model design, or write-scope change was made.
- The current Stage 9 fixture pass does not establish live Preview parity. The fresh committed-code run is still mandatory.

## Handoff Notes
- **Resume at:** Complete the remaining validation, then hand off changes for user-run staging/commit. After commit, archive the partial `6b-replay-20261005-r1` run from `83b0de3`, capture new HEAD, and start fresh preflight.
- **Watch out for:** Never continue past a failed stage. Stage 10–12 and publication remain gated on Stage 9's exact dual-baseline verification.

**tags:** ["stage6b", "grade-reproduction", "integrity", "contract-amendment"]
