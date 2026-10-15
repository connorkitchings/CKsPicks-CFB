# Session: Phase 2 documentation truth and V4 retrospective

## TL;DR

- **Worked On:** Phase 2 of the Weeks 6–7 review fixes.
- **Outcome:** Phase 2 complete and validated locally, awaiting owner commit; Phase 1 commit `2807e087` verified before work began.
- **Plan Contract:** `docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md`.
- **Approval / Status:** Owner confirmed Phase 1 committed after the agreed Phase 2 handoff; the approved contract is In Progress.
- **Blockers:** Week 8 revision dry run still requires Week 7 finals/controller inputs; no operational execution is included here.
- **Next:** Owner reviews and commits Phase 2; Phase 3 remains deferred.

## TODO

- [x] Verify Phase 1 commit and worktree exclusions.
- [x] Consolidate operations docs and navigation.
- [x] Correct model/data methodology and write evidence-backed V4 retrospective.
- [x] Update entry points and documentation-authority regression checks.
- [x] Reconcile status/history, contract lifecycle/index and correction notes.
- [x] Run required validation and review the final diff.
- [x] Propose Phase 2 commit; Phase 3 remains deferred.

## Context and decisions

- Work only in the existing `worktree-connorkitchings-review-and-v5-streamline` worktree. No commit, staging, push, stash, remote write or Production operation.
- Preserve the two untracked exclusions from Phase 1 unchanged: `conf/season/2026/revision_manifest_w8_v1.json` and `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md`.
- Split ownership among operations docs, modeling/data docs and entry points; orchestrator owns status/history, plan lifecycle/index and session logs.
- `tests/test_data_first_documentation_authority.py` hardcodes a superseded selected Week 5 run, Week 4 text and per-packet authorization. Updating those assertions is a mechanical Phase 2 amendment: verify current season-release authority while retaining mathematical, historical and no-six-slate-launch-gate protections. Runtime interfaces and model semantics are unchanged.


## Work completed

- Archived all seven superseded ops runbooks under `docs/archive/ops/`, retaining one-line old-path redirects and rebasing archive-relative links. Historical bodies were checked against the original content. Moved validation byte for byte to `docs/data/validation.md`; navigation has only the canonical runbook under Operations and data-first capture under Research.
- Updated active model/record/data-platform docs for the controller, `season_verification_v2`, exact reconciliation, source precedence, intended best-quote grading, started-game presentation and the unchanged active versus pending rebuilt record. Preserved known data limitations and deferred repairs.
- Added `docs/modeling/v4_retrospective.md`: V4 methodology, chronology, feature admission, historical results/market limitations and verified recovery commit `2807e0871c53a659943c5c23e5def888e0be5fbc` containing the retained V4 training code/configuration. No V4 code was deleted.
- Updated entry points to V5 season operations and removed `.codex/HYDRA.md` and `GEMINI.md` as contracted. A deleted-path audit found one extra current reference in `CLAUDE.md`; replaced that guide reference with the canonical runbook (mechanical scope amendment, no workflow change). Dated audit/inventory reports retain historical deleted-path names.
- Moved old status release/open-work narrative to history; kept the active release IDs, week table and published scoreboard unchanged. Added the accepted candidate correction as pending activation and retained Week 8 prerequisites. Superseded ten overlapping contracts with explicit backlog pointers; added three missing index contracts and marked CI Merged. The season bridge remains In Progress until first controller weekly update; documentation is not operational proof.
- Appended October 15 correction notes to October 14 logs 07 and 08 without rewriting their original claims.

## Review

Applied the `code-reviewer` skill with independent authority/reliability and entrypoint/functionality reviews, plus orchestrator integration checks. Corrected the one confirmed evidence-attribution issue: venue completion now links to the venue-catalog contract, not the Stage 4 cutover log. Rejected a suggested change to the skills-catalog relative link after resolving both candidates locally: existing `../../docs/ops/weekly_runbook.md` correctly resolves from `.agent/skills/`; `../../../` would point outside the worktree. No unresolved actionable review findings remain.

## Validation

- Focused documentation authority tests: 22 passed.
- Web lint: passes with the existing unused `retrospectiveRepair` warning; typecheck passes; publication tests 163 passed, 1 skipped; production build passes. The sandbox blocked the first Turbopack CSS worker's local port; expanded-permission local retry passed, with no deployment.
- Strict MkDocs passes; contracts pass; quality registry passes (32 checks, no problems); Ruff format check (825 files) and lint pass; diff whitespace checks pass.
- Seven redirect paths, moved validation bytes, sole Operations navigation, recovery Git tree and unchanged excluded-file checksums independently verified. Staging area remains empty.
- Full parallel Python suite: **3,227 passed, 33 skipped in 260.18s**. Expanded serial database suite: **147 passed, zero skips in 31.33s** with `PGTZ=UTC`; details and initial non-UTC failure below. Every disposable database cluster was stopped and removed. The Week 8 revision dry run remains blocked by missing Week 7 finals/controller inputs and is not claimed as passed.


## Proposed Phase 2 commit scope

`docs(season): consolidate V5 operations and preserve V4 history`

Explicit allowlist (including the two guide deletions and validation move); no staging performed:

```text
.agent/CONTEXT.md
.agent/skills/CATALOG.md
.codex/HYDRA.md
.codex/MAP.md
.codex/QUICKSTART.md
AGENTS.md
CLAUDE.md
GEMINI.md
README.md
contracts/README.md
docs/architecture/data_platform_2026.md
docs/archive/ops/mlflow_mcp.md
docs/archive/ops/production_runbook.md
docs/archive/ops/rating_shadow_operations.md
docs/archive/ops/rating_successor_research.md
docs/archive/ops/v5_shadow_runbook.md
docs/archive/ops/v5_weekly_operator.md
docs/archive/ops/weekly_pipeline.md
docs/data/known_issues.md
docs/data/validation.md
docs/decisions/decision_log.md
docs/index.md
docs/modeling/record_methodology.md
docs/modeling/v4_retrospective.md
docs/modeling/v5_status.md
docs/ops/mlflow_mcp.md
docs/ops/production_runbook.md
docs/ops/rating_shadow_operations.md
docs/ops/rating_successor_research.md
docs/ops/v5_shadow_runbook.md
docs/ops/v5_weekly_operator.md
docs/ops/validation.md
docs/ops/weekly_pipeline.md
docs/ops/weekly_runbook.md
docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md
docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md
docs/plans/2026-10-08/02-repair-track-certification-and-closure.md
docs/plans/2026-10-09/02-week6-display-production-release.md
docs/plans/2026-10-10/01-week7-cutover-run-sheet.md
docs/plans/2026-10-11/01-week6-closeout-and-transition-review.md
docs/plans/2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md
docs/plans/2026-10-11/03-week7-standalone-fallback.md
docs/plans/2026-10-13/02-task4-verification-and-catalog-repair.md
docs/plans/2026-10-13/03-task4-baseline-and-week7-display-continuation.md
docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md
docs/plans/2026-10-14/03-ci-speedup.md
docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md
docs/plans/index.md
docs/status.md
docs/status_history.md
mkdocs.yml
session_logs/2026-10-14/07-web-ui-cleanup-and-early-games-reconstruction.md
session_logs/2026-10-14/08-stage4-production-migration-and-cutover.md
session_logs/2026-10-15/03-phase2-documentation-truth.md
tests/test_data_first_documentation_authority.py
web/README.md
```

Exclude the untouched untracked `conf/season/2026/revision_manifest_w8_v1.json` and `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md`. No code cleanup, dependency removal, Nx/CI rewrite or database/serving change belongs in this Phase 2 commit.


## Database validation diagnosis

The first expanded serial database run finished **146 passed, 1 failed** in 30.70s. The failure was the unchanged legacy `test_null_lean_with_quotes_persists_no_selection`, raising `conflicting immutable market snapshot snap1`. Disposable clusters were stopped and removed.

A fresh cluster reported session timezone `America/New_York`. The legacy publisher normalizes incoming timestamps to UTC, while `verify_snapshot` compares JSON using `default=str` without normalizing returned timestamp offsets. Equal instants serialize differently in non-UTC sessions. The reviewed runtime files are unchanged from Phase 1; this is an existing legacy-path portability limitation, not a documentation regression. An independent reviewer reproduced the canonical comparison mismatch for equal UTC/New York instants without database access.

Rerun all seven serial database modules with `PGTZ=UTC` for every new libpq client session, matching the CI UTC environment; confirmed `SHOW timezone` reports UTC before starting. This is an environment-only test correction. No legacy publisher behavior is changed in Phase 2. Non-UTC compatibility remains a separate runtime concern if this legacy writer is retained; its planned Phase 3 disposition does not silently certify it.


## Handoff notes

- **Resume at:** owner review and Phase 2 commit. The first complete controller weekly update in Preview remains the bridge acceptance gate after Week 7 finals; no run or release was executed here.
- **Watch out for:** refresh score exceptions and replace the stale Week 8 manifest before regeneration, prepare from a clean tree, and do not commit between prepare and release. Owner rollback requires the missing owner Keychain item. Production activation remains an owner decision.
- **Phase 3:** deferred. Preserve research; check live/research import reachability before deletion and baseline combined CI coverage before pruning, stopping below 60%.

**tags:** ["phase2", "documentation", "v5", "v4-history", "validation"]
