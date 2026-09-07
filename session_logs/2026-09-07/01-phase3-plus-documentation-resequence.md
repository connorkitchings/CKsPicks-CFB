# Session: Phase 3+ Documentation Resequencing

## TL;DR

- **Worked On:** Implemented Task 1 of the approved Phase 3–6 resequencing
  contract: active-authority reconciliation and replacement implementation
  contracts.
- **Outcome:** Phases 0–2 are closed consistently in active documentation.
  Phase 3 now certifies measurement meaning and selects only the shared core;
  Phase 4A selects context-free ratings; Phase 4B selects target context;
  Phase 5 selects final forecasts; and Phase 6 collects prospective evidence.
- **Plan Contract:** `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-07. The resequencing contract remains `In Progress` because its
  research phases must run as separate Terra tasks.
- **Blockers:** None for documentation. Phase 3 execution must use its
  replacement contract in a fresh task.
- **Next:** Execute
  `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md`.

## Context and Decisions

- The signed Phase 2d 70-ref handoff is the sole Phase 3 parent. Phase 2e
  reconstructed-only auxiliary evidence is not read until Phase 4B.
- Superseded 2026-09-05 Phase 3–6 contracts retain their original content with
  current-authority banners; the Phase 2 repair evidence remains authoritative.
- The active roadmap now records Phase 0–2 evidence identities, checksums,
  code bindings, timing restrictions, permitted uses, and activation status.
- Corrected inventory terminology is explicit: 1,300 returning-production and
  26,844 betting-line Bronze captures; game statistics are reconciliation
  evidence, and the obsolete 2016–2018 play-gap claim is removed from active
  authority.

## Work Completed

- Published approved replacement contracts for Phase 3, 4A, 4B, 5, and 6 under
  `docs/plans/2026-09-07/`.
- Updated the data-first roadmap, documentation index, contract index, modeling
  authority, historical operations roadmap, and Phase 2 completion status.
- Added regression coverage for active sequence, certified handoffs, inventory
  totals, and closed-Phase-2 wording.

## Files Modified

- `docs/planning/data-first-football-forecasting-roadmap.md` - active sequence
  and certified predecessor evidence table.
- `docs/plans/2026-09-07/` - approved replacement Phase 3–6 contracts.
- `docs/plans/index.md` and superseded 2026-09-05 contracts - active authority
  and historical supersession markers.
- `tests/test_data_first_documentation_authority.py` - documentation authority
  regression checks.

## Validation

- [x] Focused documentation, repository-boundary, and contract tests: 14 passed.
- [x] `uv run ruff check tests/test_data_first_documentation_authority.py`
- [x] `uv run python contracts/validation.py`
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None. This session intentionally stops after the documentation task because
  the approved contract requires Phase 3 execution in a separate Terra task.

## Handoff Notes

- **Resume at:** Use the repository-local `implement-plan` skill with
  `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md`.
- **Watch out for:** Preserve `.opencode/`, V4, production, 2020 exclusion, and
  Preview-only immutable research routing. Do not admit Phase 2e context before
  Phase 4B.

**tags:** ["data-first", "phase3", "documentation", "contracts"]
