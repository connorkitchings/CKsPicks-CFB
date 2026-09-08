# Session: Phase 4B Target-Context Implementation

## TL;DR
- **Worked On:** Implemented Phase 4B target-context selection contracts, tournament computation, runner, verifier, config, and tests
- **Outcome:** All Phase 4B code complete; 12 focused tests pass; full suite 777 passed; awaiting Preview dry run and apply
- **Plan Contract:** `docs/plans/2026-09-07/03-phase4b-target-context-selection.md`
- **Approval / Status:** User-authorized 2026-09-08; contract status is `Implemented`
- **Blockers:** Preview dry run requires committed code and clean tracked worktree
- **Next:** Commit changes, run Preview dry run, apply, and independent verification

## Context and Decisions

Phase 4B evaluates 8 context families beyond the Phase 4A rating-only baseline:
- 3 from Phase 3 context-only measurements: field_position, pace, turnovers
- 5 from Phase 2e auxiliary datasets: recruiting, returning_production, coaching, roster_continuity, lagged_rankings

Each target (margin, total) independently selects at most one context family that improves MAE by ≥0.5% with 90% bootstrap excluding zero, no season regression >5%, and equal coverage. Simplicity tie-break selects fewest features within 0.5% of best.

Key design decisions:
- Context features are per-side (home_X, away_X) following Phase 4A pattern
- No-context baseline is re-fit (not copied from Phase 4A) for identical code path
- Ridge alpha=10, scale_floor=0.05, same numerical guards as Phase 4A
- Three parents required: Phase 4A retained rating, Phase 3 retained core, Phase 2e eligibility

## Work Completed

- Created contracts module with Phase4BError, identity, parent verification, config validation, selection logic, retained manifest
- Registered 3 Phase 4B dataset schemas (predictions, attribution, coverage)
- Implemented tournament computation with context feature loading, Ridge fitting, paired bootstrap
- Created runner script with dry-run/apply modes and 3-parent verification
- Created independent verifier script
- Created sealed YAML config with 8 context families and selection parameters
- Created 12 focused tests covering contracts, selection, bootstrap, standardization, Ridge guards
- Updated Phase 4B plan status to Implemented
- Updated roadmap checkpoint

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase4b.py` — contracts module (new)
- `src/cks_picks_cfb/ratings/phase4b.py` — tournament computation (new)
- `src/cks_picks_cfb/data/schema_contracts.py` — added Phase 4B schemas
- `scripts/research/run_data_first_phase4b.py` — runner (new)
- `scripts/research/verify_data_first_phase4b.py` — verifier (new)
- `conf/research/data_first_football_v1/phase4b_target_context_v1.yaml` — config (new)
- `tests/test_data_first_phase4b.py` — tests (new)
- `docs/plans/2026-09-07/03-phase4b-target-context-selection.md` — updated status
- `docs/planning/data-first-football-forecasting-roadmap.md` — updated checkpoint

## Validation

- [x] Focused Phase 4B tests: 12 passed
- [x] Full warning-as-error Python suite: 777 passed, 2 skipped
- [x] Ruff format + lint: clean
- [ ] Preview dry run: pending commit
- [ ] Preview apply: pending dry run
- [ ] Independent verification: pending apply

## Amendments and Blockers

- No amendments to the plan contract
- Blocker: Preview dry run requires committed code and clean tracked worktree

## Handoff Notes

- **Resume at:** After committing, run Preview dry run with:
  ```bash
  PYTHONWARNINGS=error PYTHONPATH=.:src uv run python scripts/research/run_data_first_phase4b.py \
    --phase4-rating-uri "artifacts/research/data-first-football-v1/phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json" \
    --phase3-retained-uri "artifacts/research/data-first-football-v1/phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json" \
    --auxiliary-eligibility-uri "artifacts/research/data-first-football-v1/phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json" \
    --run-id "phase4b-v1-20260908T1600Z" \
    --expected-code-sha <commit-sha> \
    --environment preview
  ```
- **Watch out for:** Preserve `.opencode/` directory and other session's `src/cks_picks_cfb/ops/__main__.py` changes

**tags:** ["data-first", "phase4b", "context-selection", "implementation"]
