# Session: V5-10A Reclosure Implementation (Amendment 2)

## TL;DR
- **Worked On:** Implemented 10a Amendment 2 (exhaustive traversal, 16-cell behavioral matrix, hardened publication interface).
- **Outcome:** 61 checks per preflight (44 + 16 behavioral + 1 exhaustive); three byte-identical no-write preflights; verifier passes; full suite 1117 passed / 2 skipped; zero R2 writes across the audits prefix.
- **Plan Contract:** `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md` (Amendment 2)
- **Approval / Status:** Explicit user authorization for this exact path. 10a stays **In Progress** pending the user-executed commit + post-commit rerun under the new SHA.
- **Blockers:** User git commit outstanding (same procedure as the first checkpoint).
- **Next:** User commits; Terra reruns preflights under the new HEAD, then task 2 (10B) on authorization.

## Context and Decisions
- Six gaps closed without R2 writes: header dedupe (planning step), cycle-safe exhaustive traversal with nested edges + fail-closed unreadables, importlib/subprocess behavioral matrix (no static verifier/producer imports in the harness), `closure_state` on findings with validity/gate split, `rejected_seasons: [2020, 2026]` declared + enforced, exact idempotence, finalized-manifest enforcement, parent-byte reread, evidence-digest reconstruction.
- Matrix design: forecast full entry, rating parent-layer + preamble, measurement `_verify_repair` helper, repair black-box subprocess (monolithic entry) + poisoned import. All 16 cells deterministic; mismatches become provisional findings (currently zero — matrix fully matching, with Repair dependence carried by seeded finding 001 and the poison cell).
- Repair wrong-parent cell honestly records fail-closed-before-parent-validation (fixture root holds no row data); classification still follows from boundary + poison results.
- Preflight evidence digest `a26ba122…` (files `b9f962cf…` ×3), run ID `historical-audit-10a-20260918-reclosure`, cutoff unchanged, code `dcb7ac6…` (uncommitted worktree; expected == HEAD).

## Work Completed
- `register.py`: `collect_lineage` (BFS, visited-set, opaque-leaf vs error records); graph records nested parent/output edges + opaque/unreadable nodes; `check_lineage_exhaustive`.
- `behavioral.py` (new): 16-cell matrix, poison-import mechanics, fixture builders with restated (never imported) constants.
- `checks.py`: `closure_state` on findings, `behavioral_cells_to_checks`, `behavioral_findings`, rejected-seasons parameter.
- `verification.py`: closure-driven gate, `evidence_digest_for_manifest`, finalized enforcement, parent reread, validity/gate split in the result.
- Runner: matrix execution (temp dir, timing excluded), findings wiring, hardened manifest + exact idempotence, rejected seasons in config/identity.
- Config: `rejected_seasons: [2020, 2026]`.
- Tests: 55 audit tests (was 44); new coverage for traversal, matrix determinism, closure, collision, non-final rejection, parent reread, digest reconstruction.

## Files Modified
- `src/cks_picks_cfb/audit/{register,checks,verification}.py`, `behavioral.py` (new)
- `scripts/research/run_data_first_historical_audit.py`
- `conf/research/data_first_football_v1/historical_audit_v1.yaml`
- `tests/test_data_first_historical_audit.py`
- `session_logs/2026-09-18/06-v5-10a-audit-harness.md` (dated correction appended)
- `session_logs/2026-09-18/08-v5-10a-reclosure.md` (this log)

## Validation
- [x] Focused audit tests: 55 passed with `-W error` (+6 possession verification).
- [x] Full suite: 1117 passed, 2 skipped.
- [x] Ruff format + check clean on all touched files.
- [x] Contracts validation, strict MkDocs, `git diff --check` clean.
- [x] Three identical no-write preflights (61 checks, only expected `independence.repair.boundary` fail); verifier passes; gate correctly denies Contract 11 (forecast findings pending).
- [x] Zero R2 writes confirmed across the audits prefix.
- [ ] User commit + post-commit preflight rerun under the new SHA.

## Amendments and Blockers
- None beyond Amendment 2. Any defect the matrix or audit surfaces that needs code/methodology/schema changes goes to separate corrective contracts.

## Handoff Notes
- **Resume at:** User commits the reclosure files; Terra reruns one preflight under the new HEAD and confirms digest stability modulo `code_sha`; then 10a returns to Implemented and task 2 (10B, still Draft) can be authorized.
- **Watch out for:** Reclosure evidence is local-only (`audit-10a-reclosure-{1,2,3}.json`). The behavioral matrix adds ~12s per preflight (repair subprocess cells). Never import producer modules into harness files — matrix uses importlib/subprocess by design.

**tags:** ["v5", "contract-10a", "amendment-2", "implementation"]
