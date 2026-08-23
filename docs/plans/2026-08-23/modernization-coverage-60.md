# Modernization Coverage Closure to 60%

- **Status:** In Progress
- **Created:** 2026-08-23
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation in this task on 2026-08-23.
- **Implementation log:** `session_logs/2026-08-23/05-modernization-coverage-60.md`
- **Commit policy:** User-controlled; coverage tests may be committed with the ongoing modernization implementation.

## Goal

Raise full-package branch coverage from 51.56% to at least 60%, targeting 61% headroom, without exclusions, `pragma: no cover`, threshold changes, production I/O, or behavior-only test doubles.

## Constraints

- Coverage scope remains all `src/cks_picks_cfb`; `fail_under = 60` stays unchanged.
- Preserve all public APIs, storage semantics, model chronology, schemas, CLI contracts, and production configuration.
- Use fake boto/psycopg clients, `LocalStorage(tmp_path)`, temporary files, and in-memory pandas fixtures only.
- Preserve the existing dirty modernization worktree and audit evidence.

## Implementation

1. Add behavior-level fake-client coverage for R2/S3/read-only storage through pagination, metadata, cache, parallel/index, write, quarantine, and denial paths.
2. Complete synthetic Silver normalizer and immutable version coverage, including malformed/provenance/policy branches.
3. Parameterize every ops command composition branch; cover state stores, notifier failures, lease/replay, subprocess scope, and invalid options.
4. Add recording psycopg coverage for catalog lifecycle, captures, ancestry, reconciliation, and point-in-time lookup failures.
5. Cover selector and persistence branches with temporary data; cover validation-service behavior with temporary manifests and synthetic aggregation/box-score frames.
6. Complete regime-training failure and temporal/refit branches. Extract only internal seams necessary for deterministic testing, preserving facades and behavior.

## Coverage Targets

- Global: >=61% on the required full command.
- R2/S3 storage >=70%; Silver builders >=75%; ops CLI >=55%; state machine >=75%; catalog >=65%; selector >=75%; persistence >=65%; validation utilities >=45%; regime training >=70%.

## Required Verification

```bash
uv run ruff format --check .
uv run ruff check .
PYTHONPATH=src:. uv run pytest tests -q -W error --cov=cks_picks_cfb --cov-branch --cov-report=term-missing:skip-covered
uv run python contracts/validation.py
uv run mkdocs build --quiet
git diff --check
```

## Verification Evidence (2026-08-23)

- The required branch-aware full command passed with `414 passed, 2 skipped` and **60.02%** coverage. This closes the enforced global `fail_under = 60` gate without changing source scope, omitting files, or using coverage pragmas.
- Offline fixtures added behavior coverage for S3-compatible storage, Silver normalizers, feature selection and recency assembly, ops command composition/state persistence/subprocess scoping, catalog registration/lookups, and local validation utilities.
- The following gates passed: `ruff format --check`, `ruff check`, `contracts/validation.py`, `mkdocs build --quiet`, and `git diff --check`.
- Module stretch targets remain work in progress: Silver is 73% (target 75%), ops CLI 45% (target 55%), persistence 7% (target 65%), validation utilities 26% (target 45%), and regime training 49% (target 70%). The 61% headroom target was not reached.

## Definition of Done

- [ ] Global and module-level coverage targets pass with no scope exclusions. Global 60% gate passes; module stretch targets remain.
- [x] Full Python suite passes with warnings treated as errors.
- [x] Required docs, audit evidence, and session log are updated.
- [ ] This plan is `Implemented` only after the remaining module targets and 61% headroom target pass.

## Amendments

- None.
