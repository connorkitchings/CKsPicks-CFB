# Session: Phase 3 v2 implementation

## TL;DR

- **Worked On:** Implementing the approved Phase 3 corrected-measurement and
  core-selection v2 contract.
- **Plan Contract:** `docs/plans/2026-09-08/phase3-measurement-and-core-selection-v2.md`
- **Approval / Status:** Explicit user authorization; implementation in progress.
- **Outcome:** Local implementation is complete and passes the Python,
  schema/contract, lint, CLI, documentation, and regression gates. Preview dry
  run/materialization is intentionally pending the clean committed checkpoint
  required by the approved contract.
- **Blockers:** Preview execution awaits the user-created checkpoint. Focused
  coverage instrumentation is blocked before test collection by an existing
  CFBD/Pydantic duplicate-validator import failure; the ordinary full
  warning-as-error suite passes.
- **Next:** User creates the clean code checkpoint, then run the Preview dry run
  specified by the contract before any artifact write.

## Guardrails

- Repair v2 is the sole modeling parent; Phase 3 v1 is diagnostic-only.
- Preserve `.opencode/`, V4, production, Neon, web, and all v1 behavior.
- Do not create repository-local data. Preview apply requires a later clean,
  committed checkpoint; local implementation and dry-run checks precede it.

## Work Completed

- Added versioned Phase 3 v2 population, timing, common-bootstrap, certification,
  retention, replay, runner, verifier, configuration, and schema contracts.
- Preserved the repaired schedule population independently of measurement joins:
  8,936 schedule rows, 8,935 eligible rows, and 8,903 usable rows are enforced.
- Added six-hour, prior-canonical-week-only reconstructed historical admission.
- Reused v1 only for frozen measurement definitions and state/tournament
  primitives; v2 replaces population completion, cutoff behavior, output
  identities, and common-bootstrap seeding.
- Added focused tests for config drift, parent rejection, complete missing-grid
  behavior, cutoff inclusivity, deterministic common resamples, retention, and
  schemas.
- Updated the plan index and forecasting roadmap to show Phase 3 v2's local
  implementation status without claiming Preview evidence or production authority.

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase3_v2.py` - V2 population, lineage,
  timing, selection, certification, and immutable-interface contracts.
- `src/cks_picks_cfb/ratings/phase3_v2.py` - Cutoff replay, adjustment,
  terminal state, and sealed tournament adapter.
- `scripts/research/run_data_first_phase3_v2.py` - Preview-only dry-run/apply
  orchestrator.
- `scripts/research/verify_data_first_phase3_v2.py` - Raw-parent and
  independently recomputed artifact verifier.
- `conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml` -
  Sealed Phase 3 v2 configuration.
- `src/cks_picks_cfb/data/schema_contracts.py` - Seven V2 dataset schemas.
- `tests/test_data_first_phase3_v2.py` - Focused contract coverage.
- `docs/plans/index.md`, `docs/planning/data-first-football-forecasting-roadmap.md`
  - Current execution status.

## Validation

- [x] `uv run pytest -q tests/test_data_first_phase3_v2.py` — 9 passed.
- [x] `PYTHONPATH=. uv run pytest -q tests/test_data_first_phase3.py tests/test_data_first_repair_v2.py tests/test_data_first_phase3_v2.py` — 30 passed.
- [x] `uv run pytest -q -W error` — 799 passed, 2 skipped.
- [x] Ruff format check and lint for all V2 implementation files.
- [x] Both V2 CLI `--help` checks.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `git diff --check`.
- [ ] Focused coverage: `pytest --cov=...` is blocked before collection by
  CFBD/Pydantic's duplicate `outcome_validate_enum` validator. This also occurs
  with the alternate coverage core and is unrelated to the V2 test code.

## Handoff Notes

- **Resume at:** Commit the exact local implementation, then run the exact
  Preview dry run with the Repair v2 manifest URI and committed SHA.
- **Watch out for:** Do not use the Phase 3 v1 retained manifest as an input; do
  not apply/write Preview artifacts until dry-run review passes; do not update
  the plan to `Implemented` until verifier and deterministic rerun succeed.

**tags:** ["implementation", "data-first", "phase3", "research", "lineage"]
