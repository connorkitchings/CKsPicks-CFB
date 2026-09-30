# Session: V6 Ratings Lab Phase 1 — Deterministic 4-Factor Recipe

## TL;DR
- **Worked On:** V6 Ratings Lab Phase 1 implementation per approved plan contract `02-v6-phase1-measurement-recipe.md`.
- **Outcome:** Resolved 4 audit review code integrity fixes in `updaters.py` and `test_platform.py`. Added `--recipe` and `--measurement-id` flags to `ratings_lab.py`. Implemented deterministic 4-factor measurement recipe (`v6_4factor_game_v1`) in `measurements.py` with play taxonomy, goal-to-go thresholds, per-factor exposure, zero-success handling, and dual explosiveness columns (primary yards/success + diagnostic margin). All 21 ratings lab unit tests pass.
- **Plan Contract:** [`docs/plans/2026-09-30/02-v6-phase1-measurement-recipe.md`](../../plans/2026-09-30/02-v6-phase1-measurement-recipe.md)
- **Approval / Status:** User authorized and approved; Implemented and fully verified.
- **Blockers:** None.
- **Next:** Phase 2 of V6 research roadmap: Preseason continuity prior engine (blending prior terminal states with returning production, recruiting composite, and coaching stability).

## Context and Decisions
- **Audit Fixes Completed:**
  1. *`_parse_candidate` hardening:* Retired dead `_CANDIDATE_SCHEMA`, added unexpected fields check, and strictly validated finite numeric $k$ and $\rho$.
  2. *`load_candidate_configs` path error:* Added `FileNotFoundError` when candidate directory does not exist.
  3. *Test registry isolation:* Added autouse fixture `_restore_measurement_registries` in `test_platform.py` to prevent registry leakage between test runs.
  4. *Collision test:* Tested collision against real `REGISTRY` (`carryover_only_rho_0_60_v1`).
- **Phase 1 Recipe Architecture:**
  - Registered recipe `v6_4factor_game_v1` in `measurements.py`.
  - Defined strict play taxonomy on non-garbage regulation plays: sacks mapped to pass dropbacks, scrambles to rushes, dead plays (kneels/spikes/etc) excluded.
  - Implemented goal-to-go fallback and down-and-distance success thresholds ($0.5 \times, 0.7 \times, 1.0 \times$).
  - Emitted dual explosiveness metrics: primary (`yards / success`) and diagnostic (`(yards - threshold) / success`).
  - Enforced per-factor exposure ($N_{\text{rush}}$ for Rush SR, $N_{\text{succ}}$ for Expl).
  - Maintained contracts invariant: missing reasons emitted when attempts=0 (`"no_rush_attempts"`, `"no_pass_attempts"`) or successes=0 (`"no_successful_plays"`).

## Work Completed
- Updated `src/cks_picks_cfb/ratings_lab/updaters.py` with hardened validation and path checks.
- Added `storage`, `byplay`, and `read_byplay()` support to `Corpus` in `src/cks_picks_cfb/ratings_lab/corpus.py`.
- Implemented `_build_4factor()` and registered `v6_4factor_game_v1` in `src/cks_picks_cfb/ratings_lab/measurements.py`.
- Updated `scripts/research/ratings_lab.py` with `--recipe` and `--measurement-id` argument plumbing.
- Added unit tests for 4-factor calculations, goal-to-go, zero-success handling, and CLI help/argument parsing in `tests/ratings_lab/test_platform.py` (21 tests now passing).

## Files Modified
- `docs/plans/2026-09-30/02-v6-phase1-measurement-recipe.md` - Phase 1 plan contract (marked Implemented).
- `src/cks_picks_cfb/ratings_lab/updaters.py` - Hardened candidate parsing and path checks.
- `src/cks_picks_cfb/ratings_lab/corpus.py` - Added byplay access to Corpus.
- `src/cks_picks_cfb/ratings_lab/measurements.py` - Implemented 4-factor builder and registered `v6_4factor_game_v1`.
- `scripts/research/ratings_lab.py` - Added `--recipe` and `--measurement-id` flags.
- `tests/ratings_lab/test_platform.py` - Added registry fixture, hardened tests, and 4-factor calculation tests.
- `session_logs/2026-09-30/03-v6-phase1-measurement-recipe.md` - This session log.

## Validation
- [x] `uv run pytest tests/ratings_lab/ -q` (21 passed)
- [x] `uv run ruff check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py tests/ratings_lab/` (0 errors)
- [x] `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py tests/ratings_lab/` (all clean)
- [x] `uv run mkdocs build --quiet` (clean build)
- [x] `git diff --check` (clean)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Phase 2: Preseason continuity prior engine.
- **Watch out for:** All research remains private in `ratings_lab/`; production pipelines untouched.

**tags:** ["research", "ratings_lab", "v6", "measurements", "testing", "phase1"]
