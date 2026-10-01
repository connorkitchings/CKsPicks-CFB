# Production Boundary Refactor: Move V5 Production Logic into `src/`

- **Status:** Draft
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** Pending User Review
- **Implementation log:** Pending Terra Implementation
- **Commit policy:** One commit per phase; separate plan commit recommended (touches the production release path)

## Goal

Make the code layout match what actually runs in production. Today the weekly V5
cycle executes stages that live in `scripts/research/`, and `src/` imports from
`scripts/`. After this contract:

1. `src/cks_picks_cfb/` never imports `scripts.*`.
2. Every production V5 stage lives in `src/` (covered by the 60% coverage gate),
   with a thin CLI wrapper under `scripts/pipeline/`.
3. `ratings_lab` contains only V6 research; production modules move to a `v5` package.
4. Behavior is byte-for-byte unchanged: no estimator, population, artifact schema,
   selection, or publication change.

## Evidence (verified 2026-10-01)

- `src/cks_picks_cfb/ops/v5_cycle.py:44-57` runs five stages from `scripts/research/`:
  `run_data_first_repair_v2.py` (1,434 lines), `run_data_first_possession_measurements.py` (900),
  `run_data_first_possession_rating_replay.py` (685), `run_v5_live_forecast.py` (514),
  `run_v5_shadow_readiness.py` (1,155), plus their `verify_*` scripts.
- `scripts/pipeline/generate_v5_weekly_bets.py:34` imports `scripts.research.run_v5_live_forecast`.
- `src` → `scripts` imports: `ops/v5_cycle.py:400,596` (`scripts.pipeline.publish_to_db`),
  `ops/public_selection.py:207` (`scripts.pipeline.score_to_db.RECOMPUTE_STATS_SQL`);
  `audit/behavioral.py` edits `sys.path` and imports `scripts.research`.
- `ratings_lab` (documented as isolated research) is imported by ~12 production scripts:
  `artifacts` (20 import sites), `corpus` (10), `updaters` (7), `contracts` (7), `replay` (5),
  `adjusted_game` (5), `stages` (4), `v5_control`. Research-only: `kalman`, `reanchoring`,
  `priors`, `evaluation`, `measurements` (V6 recipes).
- `scripts/pipeline/publish_to_db.py` is 1,433 lines, `score_to_db.py` 639; coverage measures
  only `src/cks_picks_cfb` (`pyproject.toml` `fail_under = 60`), so ~24k production lines are ungated.

## Scope

### Phase 0: Safety net (no moves)
- Add `tests/test_import_boundaries.py`: assert no module under `src/` imports `scripts.`;
  start with an allowlist of the three known violations and shrink it each phase.
- Record golden hashes: run the verifier for the Week 5 p2 forecast/rating artifacts in
  Preview (read-only against R2 refs) and store expected checksums in the test fixture
  or the session log. Every later phase must reproduce them.

### Phase 1: Extract publish/score SQL into `src/cks_picks_cfb/db/`
- Move reusable functions of `publish_to_db.py` used by `ops/v5_cycle.py` and
  `RECOMPUTE_STATS_SQL` from `score_to_db.py` into `src/cks_picks_cfb/db/publish.py` /
  `db/scoring.py`. Scripts re-export from the new location (shim) so CLIs keep working.
- Point `ops/v5_cycle.py` and `ops/public_selection.py` at the new modules. Allowlist shrinks to 0 for these.

### Phase 2: Split `ratings_lab`
- Create `src/cks_picks_cfb/v5/` and move production modules (`artifacts`, `corpus`,
  `adjusted_game`, `updaters`, `replay`, `stages`, `contracts`, `v5_control`) with
  re-export shims left in `ratings_lab/` for one release.
- Leave V6 research (`kalman`, `reanchoring`, `priors`, `evaluation`, `measurements`) in `ratings_lab`.
  Update `ratings_lab/__init__.py` docstring.
- Update imports in `scripts/` and `tests/`; keep test names stable.

### Phase 3: Move the V5 stage runners
- Move the logic of the five runners and their verifiers into
  `src/cks_picks_cfb/v5/stages/{repair,measurement,rating_replay,live_forecast,readiness}.py`
  (+ `verify_*`). Leave 10–30 line wrappers in `scripts/pipeline/` with the same CLI arguments.
- `ops/v5_cycle.SCRIPTS` / `VERIFIERS` point to the wrappers. Change
  `generate_v5_weekly_bets.py` to import from `src`.
- Remove the `sys.path` hack in `audit/behavioral.py`.

### Phase 4: Remove shims and lock the boundary
- Delete the shims; the boundary test now has an empty allowlist and runs in CI.
- Add `scripts/research/README.md` stating that it holds historical/diagnostic runners only
  (V5 production stages no longer live there). Correct `AGENTS.md` ("Research scripts live in `research/`").

## Out of scope (separate contracts)
- Bringing V5 release/selection/authorization scripts under `ops` commands and Make targets.
- Dead-code prune (`training/train.py`, `loader.py`, `flows/`, etc.), V4 quarantine, deleting `research/`.
- Splitting `ops/__main__.py` (2,644 lines) and `generate_weekly_bets.run_weekly_bets`.
- Any model, config, schema, or production-data change.

## Acceptance criteria / Definition of Done
- [ ] `grep -rn "^\s*\(from\|import\) scripts" src` returns nothing; boundary test passes with an empty allowlist.
- [ ] Golden hashes from Phase 0 reproduce after every phase (no artifact bytes change).
- [ ] `uv run pytest -q` passes (≥1,543 passed, 3 skipped), `uv run ruff format --check . && uv run ruff check .`,
      `uv run python contracts/validation.py`, `uv run mkdocs build --strict`.
- [ ] Every wrapper CLI's `--help` is unchanged; `docs/ops/v5_weekly_operator.md` commands still run.
- [ ] No production or Preview Neon/R2 mutation occurred (read-only verification only).
- [ ] Coverage stays ≥ 60% and covers the moved modules.

## Risks and rollback
- Behavior drift from import-order or module-level side effects → mitigated by the golden-hash gate; each phase is a separate commit and can be reverted alone.
- A weekly operator run during the refactor → do not start a phase between Week close and freeze; keep wrappers CLI-compatible.
- Frozen artifacts embed script paths/hashes in manifests → Phase 0 must confirm which verifiers hash source files; if they do, record an amendment before Phase 3.

## Handoff to Terra
Execute with `.agent/skills/implement-plan/` on this exact path once Approved. Start at Phase 0; stop and return to Sol if a verifier hashes source paths (amendment required).
