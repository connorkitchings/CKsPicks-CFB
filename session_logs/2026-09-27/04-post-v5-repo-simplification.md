# Session: Conservative Post-V5 Repository Simplification

## TL;DR

- **Worked On:** Replaced the unsafe cleanup draft with an approved conservative contract, inventoried proposed removals, reconciled V5/V4 operating guidance, protected V5 entry points, and verified local output cleanup.
- **Outcome:** No tracked source, script, config, test, plan history, or log was moved or deleted. V5 replay/Week 5 Preview/V4 rollback status is clear. Removed only regenerated MkDocs output and pytest coverage data (13,754,419 apparent bytes at deletion).
- **Plan Contract:** `docs/plans/2026-09-27/01-post-v5-repo-simplification.md` (Implemented).
- **Approval / Status:** User explicitly requested implementation of the linked plan on 2026-09-27.
- **Blockers:** None. Large ignored training and experiment artifacts remain without byte-verified copies.
- **Next:** User may stage and commit the tracked changes. Any broader source-tree retirement needs a separate evidence-backed contract.

## Context and Decisions

- Session began on `main` at `e5588f3`, with only the old draft plan untracked. The previously dirty Silver-pin test had already been committed; no user change was overwritten.
- During final validation, a separate edit appeared in `scripts/research/run_v5_shadow_readiness.py`. This session did not make, alter, or include that change; preserve it for its owner.
- The original draft's deletion claims conflicted with the shared weekly generator, V5 replay imports, scheduled capture workflow, compatibility manifest, and historical evidence paths. The report dispositions all 129 named tracked candidates and the proposed log/plan moves as retained for this pass.
- `weekly` remains an alias for `publish-week`; only its help text changed. The existing V5 stage operator and exact release gates remain authoritative.
- Local R2 backend and source/Preview credential presence were checked without exposing values. No R2 content was read and no training artifact was deleted without a matching immutable copy or backup.

## Work Completed

1. Recorded the tracked-path scan and local artifact inventory in `docs/reports/2026-09-27-post-v5-cleanup-inventory.md`.
2. Added 28 V5 stage, verifier, serving, replay, publication, and scheduled-capture paths to `required_paths.v5` in the repository compatibility manifest. The existing boundary test now enforces their presence.
3. Updated current-status summaries and V4 rollback labels across repository entry points and operations documentation. Preserved the dated historical contract records.
4. Rebuilt MkDocs to `/tmp/post-v5-mkdocs-site` and confirmed all 223 old `site/` files were regenerated before deleting that ignored directory. Deleted `.coverage` only after the final passing pytest-cov run. Retained MLflow, Hydra, Preview training, archived artifacts, event logs, CatBoost diagnostics, and model binaries.

## Files Modified

- `docs/plans/2026-09-27/01-post-v5-repo-simplification.md` — replacement implementation contract and completed lifecycle.
- `docs/reports/2026-09-27-post-v5-cleanup-inventory.md` — disposition evidence and exact local byte accounting.
- `conf/repository/compatibility_v1.yaml` — V5 required-path protection.
- `Makefile` — help text only; recipes unchanged.
- `AGENTS.md`, `README.md`, `.agent/CONTEXT.md`, `.codex/QUICKSTART.md` — dated V5/V4 entry-point status.
- `docs/modeling/v5_status.md`, `docs/ops/production_runbook.md`, `docs/ops/v5_weekly_operator.md`, `docs/ops/weekly_pipeline.md`, `docs/plans/index.md` — current operating status and rollback guidance.
- Ignored local deletions: `site/`, `.coverage` only.

## Validation

- [x] Baseline before tracked edits: `ruff format --check` and `ruff check` clean; full CI-equivalent pytest 1,456 passed, 2 skipped, 66.17% coverage.
- [x] Final `PYTHONPATH=src:. .venv/bin/python -m pytest tests/ -q -W error -n 4 --dist loadfile --cov=cks_picks_cfb --cov-report=term-missing:skip-covered`: 1,456 passed, 2 skipped, 66.17% coverage.
- [x] Focused documentation-authority and repository-boundary tests: 23 passed. The first post-edit full run exposed three stale wording assertions; documentation was corrected without changing tests, then the focused and full suites passed.
- [x] `.venv/bin/python -m ruff format --check .` and `.venv/bin/python -m ruff check .` passed.
- [x] `.venv/bin/python contracts/validation.py` passed.
- [x] `.venv/bin/mkdocs build --quiet --site-dir /tmp/post-v5-mkdocs-site-final` passed.
- [x] `make help` shows the unchanged `weekly` alias as the V4 path and points to the V5 operator.
- [x] `git diff --check`; no tracked deletions.
- [x] `uv run pytest` could not access uv's shared cache inside the sandbox; the installed `.venv` ran the same CI flags successfully.

## Amendments and Blockers

- No material amendment. The current checkout incorporated the prior Silver-pin test fix before this implementation began.
- Local artifacts lacking byte-verified copies were retained; this is the contract's required disposition, not a blocker.

## Handoff Notes

- **Resume at:** Review and stage the docs, manifest, Makefile help, report, plan, and this log; commit manually. Exclude the concurrent `scripts/research/run_v5_shadow_readiness.py` edit from this cleanup commit.
- **Watch out for:** Do not restore the old draft's archive waves without a new dependency and identity contract. Do not treat a Week 5 Preview candidate as prospective production activation.
- **Suggested commit message:** `docs: reconcile V5 operations and inventory safe cleanup`

**tags:** ["v5", "cleanup", "repository", "operations", "documentation"]
