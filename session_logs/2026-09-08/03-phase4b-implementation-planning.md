# Session: Phase 4B Implementation Planning

## TL;DR
- **Worked On:** Developed comprehensive Phase 4B implementation plan for target-context selection
- **Outcome:** Expanded `docs/plans/2026-09-07/03-phase4b-target-context-selection.md` with full technical specification
- **Plan Contract:** `docs/plans/2026-09-07/03-phase4b-target-context-selection.md`
- **Approval / Status:** Plan documented, awaiting implementation
- **Blockers:** None
- **Next:** Implement Phase 4B following the documented plan

## Context and Decisions

Phase 4B evaluates 8 context families (3 from Phase 3 context-only measurements, 5 from Phase 2e auxiliary datasets) to select at most one family per target (margin, total) that improves prediction beyond the Phase 4A rating-only baseline.

Key design decisions:
- Context features are per-side (`home_X`, `away_X`) following Phase 4A pattern
- No-context baseline is re-fit (not copied from Phase 4A) for identical code path
- Margin and total evaluated independently
- Lagged rankings join on `(season, week, game_id, team)`; other families join on `(season, team)`
- Numerical guards inherited from Phase 4A (coefficient magnitude ≤1000, feature magnitude ≤100)

## Work Completed

- Investigated Phase 2e auxiliary data structure and context family definitions
- Analyzed Phase 4A Ridge bridge mechanics and tournament pattern
- Documented parent artifact requirements with exact URIs and SHA-256 checksums
- Specified feature construction for all 8 context families
- Defined frozen bridge parameters (Ridge alpha=10, scale_floor=0.05, validation seasons)
- Detailed selection logic with gates and simplicity tie-break
- Created artifact schema specifications
- Outlined 8 implementation tasks with file manifest
- Updated Phase 4B plan from "Approved" to "In Progress" with full technical specification

## Files Modified

- `docs/plans/2026-09-07/03-phase4b-target-context-selection.md` — expanded with parent artifacts, context families, feature construction, frozen bridge, selection logic, artifacts, implementation tasks, design decisions, file manifest

## Validation

- [x] Plan reviewed against Phase 4A patterns
- [x] Parent artifact SHA-256s verified
- [x] Context family feature counts reconciled
- [x] Selection logic matches Phase 4A gates

## Amendments and Blockers

None. Plan is ready for implementation.

## Handoff Notes

- **Resume at:** Begin Task 1 (contracts module) at `src/cks_picks_cfb/data/data_first_phase4b.py`
- **Watch out for:** Preserve `.opencode/` directory and other session's `src/cks_picks_cfb/ops/__main__.py` changes

**tags:** ["data-first", "phase4b", "planning", "context-selection"]
