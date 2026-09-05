# Session: Phase 0 Repository Alignment

## TL;DR

- **Worked On:** Implemented the approved Phase 0 repository architecture,
  compatibility baseline, contract repair, and documentation alignment.
- **Outcome:** V4 and named benchmark paths remain unchanged; FIU contract drift
  is repaired; data-first command/config roots and enforceable boundaries exist.
- **Plan Contract:** `docs/plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md`
- **Approval / Status:** User explicitly authorized the exact Phase 0 plan;
  contract is `Implemented`.
- **Blockers:** None.
- **Next:** Begin Phase 1 at
  `docs/plans/2026-09-05/01-data-and-evidence-audit.md` by verifying the required
  storage backend and resolving catalog/manifests before dataset reads.

## Context and Decisions

- Baseline commit is `b930066`; production remains bundle
  `week0-2026-v4-strict-20260818-r2` with
  `conf/weekly_bets/v4_2026.yaml`. Its representative immutable manifest is
  `artifacts/preview/models/week0-2026-v4-strict-20260818-r2/manifest.json`
  with SHA-256 `72429375bfa8c434c7d6fcb455bb9e22333af8c929c0cc3e832f0b80787bf25c`.
- Existing research scripts stay at their paths because orchestration, tests,
  docs, and committed-code identities reference them. New commands use
  `scripts/research/`.
- Phase 0 performs no source/config deletion, CLI move, production operation,
  deployment, database migration, data processing, or cloud mutation.
- `contracts/teams.py` remains canonical for team-name mapping.

## Work Completed

- Added `conf/repository/compatibility_v1.yaml` with supported Make targets,
  required production/contracts/web paths, named benchmark identities, and
  dependency rules.
- Synchronized `FIU: Florida International` into canonical TypeScript, web, and
  both publisher map copies. No other team mapping changed.
- Added direct checked-in contract synchronization coverage and AST-based
  repository boundary tests.
- Created `scripts/research/` and
  `conf/research/data_first_football_v1/` with explicit ownership rules.
- Published repository architecture, compatibility baseline, and cleanup
  disposition reports.
- Updated MkDocs navigation, the docs index, plans index, assistant map and
  quickstart, historical successor/shadow runbooks, and the historical
  early-week report.

## Files Modified

- `conf/repository/compatibility_v1.yaml` - Phase 0 machine-readable baseline.
- `conf/research/data_first_football_v1/README.md` - New research config rules.
- `scripts/research/__init__.py`, `scripts/research/README.md` - New command root.
- `tests/test_repository_boundaries.py` - Static architecture enforcement.
- `contracts/teams.ts`, `web/src/lib/teams.ts`, publisher scripts, and
  `tests/test_contracts_validation.py` - FIU synchronization and regression.
- `docs/architecture/repository_boundaries.md` - Architecture authority.
- `docs/reports/2026-09-05-phase0-compatibility-baseline.md` - Before/after checks.
- `docs/reports/2026-09-05-phase0-cleanup-disposition.md` - File classifications.
- Current navigation, runbooks, assistant guides, plan index, and historical
  report - authority and status alignment.

## Validation

- [x] Focused contract and boundary tests: 19 passed.
- [x] Named benchmark CLI `--help`: 7 of 7 passed using `.venv/bin/python`.
- [x] Focused compatibility suite: 89 passed.
- [x] `uv run python contracts/validation.py`: passed.
- [x] `uv run ruff check .`: passed.
- [x] `uv run pytest -q`: 673 passed, 2 skipped.
- [x] `uv run mkdocs build --strict`: passed.
- [x] Web `npm run lint`: passed.
- [x] Web `npm run typecheck`: passed.
- [x] Web `npm run build`: passed.
- [x] `git diff --check`: passed.

The initial CLI smoke batch through `uv` was blocked before script startup by
the filesystem sandbox reading the user uv cache. Running the same read-only
commands with the repository virtual-environment Python passed. The issue is
environmental and leaves no product failure.

## Amendments and Blockers

- Amendment 1 records the bounded decision to keep existing research paths in
  place and repair only the unambiguous pre-existing FIU mapping drift.
- No blockers or remaining validation failures.

## Handoff Notes

- **Resume at:** Phase 1 Task 1: verify the task-specific R2 or local storage
  configuration without exposing credentials, then resolve manifest/catalog
  identities before inspecting data.
- **Watch out for:** Preserve V4, never read or write `./data/`, treat 2025 as
  development only within the new program, and count coverage from an
  independent schedule-derived denominator.

**tags:** ["architecture", "compatibility", "contracts", "documentation", "ratings"]
