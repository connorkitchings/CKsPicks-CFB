# Conservative Post-V5 Repository Simplification

- **Status:** Implemented 2026-09-27
- **Created:** 2026-09-27
- **Planner:** Sol, revised after repository review
- **Approval source:** User explicitly requested implementation of this exact linked plan on 2026-09-27
- **Implementation log:** `session_logs/2026-09-27/04-post-v5-repo-simplification.md`
- **Commit policy:** Separate plan commit recommended; user controls staging and commits

## Goal

Make the repository's operating guidance accurate and establish a defensible cleanup inventory without breaking the V5 live, V5 replay, V4 rollback, or historical evidence paths. Recover local disk space only where regeneration or a byte-verified copy is demonstrated. Success is a complete disposition of the old draft's proposed moves, accurate entry-point guidance, passing validation, and a record of every local deletion and retained candidate.

## Current State

- Production serves V5 best-quote replay for Weeks 0–4. The 2026-09-27 session log records Week 4 scoring and a verified Week 5 live forecast published to Preview; it does not record prospective Week 5 production activation. V4 runs remain rollback targets.
- `scripts/pipeline/generate_weekly_bets.py` dispatches both V5 live and replay paths. The V5 operator uses it for `prepare`; preflight and publication import replay serving. A scheduled GitHub workflow invokes `capture_data_first_phase2.py`.
- `conf/repository/compatibility_v1.yaml` protects V4 and named research paths but does not yet declare the current V5 chain. The prior Phase 0 disposition forbids moving candidates solely because static references appear sparse.
- The previous draft described imported modules and referenced scripts as dead, proposed archiving failing tests, and treated ignored local artifacts as uniformly regenerable. Existing `archive/` is gitignored; indiscriminate moves would also need tracking and link repair.
- The worktree had an untracked draft plan at session start. The previously edited 2026 Silver-pin test is already committed; preserve all current user work.

## Proposed Approach

Replace the unsafe archive waves with an evidence inventory and documentation/manifest reconciliation. Do not change operational code, command behavior, model/data lineage, schemas, or public interfaces. Treat unresolved references as reasons to retain files. Local deletion requires path-specific proof and a before/after byte accounting.

## Scope

### Included

- Inventory every tracked move/removal proposed by the prior draft, with reference classes and disposition.
- Correct current-status summaries and command descriptions, including the Makefile's `weekly` help text.
- Add V5 required paths to the compatibility manifest and validate them through the existing repository-boundary test.
- Inventory ignored local cleanup candidates and remove only proven disposable outputs or byte-verified duplicates.

### Excluded

- Moving/deleting tracked source, scripts, configs, tests, plans, logs, or assistant redirect files.
- Repointing `weekly`, adding a one-command V5 pipeline, or altering stage/approval gates.
- Web, database, storage, prediction, scoring, and state-machine behavior.

## Affected Components and Contracts

- Documentation and command guidance: `AGENTS.md`, `README.md`, `.codex/QUICKSTART.md`, `.agent/CONTEXT.md`, `docs/modeling/v5_status.md`, `docs/ops/production_runbook.md`, `docs/ops/v5_weekly_operator.md`, `docs/plans/index.md`, and `Makefile` help text only.
- Compatibility declaration: `conf/repository/compatibility_v1.yaml` under `required_paths`; keep the existing V4 baseline and research benchmark entries.
- Evidence: `docs/reports/2026-09-27-post-v5-cleanup-inventory.md` and the implementation session log.
- No public API, CLI argument, schema, data format, or production command behavior changes.

## Implementation Tasks

### Task 1 — Baseline and disposition inventory

1. Capture current Git status and CI-equivalent Python baseline. Distinguish pre-existing failures from changes introduced here.
2. Enumerate every proposed tracked move/removal from the old draft, including wildcard expansions. Check imports, subprocess/path strings, Make targets, CI, tests, docs/contract links, compatibility declarations, and code-identity references.
3. Record a path-level or precisely enumerated group-level disposition with evidence. All tracked candidates remain in place for this contract; unknown external use remains a retain reason.

**Acceptance:** The report covers every prior proposed category and identifies current V5, V4 rollback, research/benchmark, scheduled, test, and documentary dependencies.

### Task 2 — Clarify operations and protect V5 paths

1. Reconcile the dated status summaries: V5 replay public, Week 5 live candidate in Preview, V4 rollback retained. Clearly mark V4-era runbook procedures as rollback/historical without rewriting their commands.
2. Label Makefile `weekly` as the existing `publish-week` alias; leave recipes unchanged. Point readers to the reviewed V5 stage operator and production release procedure.
3. Add a `required_paths.v5` section covering the operator's stage scripts and verifiers, shared generator, replay dependencies, and serving/publishing entry points. Keep all current manifest declarations.

**Acceptance:** No stale entry-point summary says V4 is the public default, and the boundary test protects the V5 paths without altering command behavior.

### Task 3 — Verify local cleanup

1. Record existence, size, file count, ignore/tracking status, generator, and proof status for each ignored path from the old draft. Verify the selected R2 backend and credential presence before any R2 read; never expose secrets or use a project-root data fallback.
2. Remove generated build/test outputs only after their regeneration path is known. For training artifacts, require a byte-identical immutable R2 object or verified backup for each file before deletion. Retain unverified data, MLflow runs, logs, and model binaries; V4 configs reference local model paths.
3. Record exact removed paths and reclaimed bytes, plus retained paths and reasons. Do not use a broad `rm -rf` over mixed evidence.

**Acceptance:** Every deleted path has a recorded proof and no tracked file is deleted.

## Testing Strategy

- Run `ruff format --check`, `ruff check`, full pytest with CI warnings/coverage settings, repository-boundary tests, shared-contract validation, MkDocs build, and `git diff --check`. Use the installed `.venv` tools if `uv run` cannot access its cache in the sandbox.
- Inspect the V5 live/replay dispatch, operator stage paths, scheduled capture path, and V4 rollback references after edits.
- Do not archive or change tests to resolve a failure. Report any baseline or environment-only failure separately.

## Risks and Edge Cases

- Historical artifacts may embed code SHA and relative path identities. A missing textual import does not prove safe removal.
- `archive/` is ignored by Git; this contract creates no new archive moves.
- Local MLflow and Hydra outputs can contain unique run evidence. Keep them when byte-identical backups cannot be proven.
- The Week 5 Preview and public selection state are a dated 2026-09-27 snapshot; do not imply prospective production activation without a later release record.

## Definition of Done

- [x] Prior cleanup candidates inventoried and dispositioned; no tracked candidates moved or deleted.
- [x] Operating summaries and Makefile help reconciled; V5 paths declared in compatibility manifest.
- [x] Local cleanup evidence and retained/reclaimed bytes recorded.
- [x] Required validation passes; the `uv` cache sandbox error was bypassed with the installed `.venv` tools without weakening checks.
- [x] Implementation session log completed and plan status updated accurately.

## Amendments

None.
