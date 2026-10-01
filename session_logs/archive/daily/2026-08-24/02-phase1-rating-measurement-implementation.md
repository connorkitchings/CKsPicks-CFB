# Session: Phase 1 Rating Measurement Implementation (Terra)

## TL;DR

- **Worked On:** Executed the approved Phase 1 rating measurement and
  opponent-adjustment foundation contract end to end.
- **Outcome:** Phase 1 is Implemented. The isolated `cks_picks_cfb.ratings`
  package, config, Preview-only CLI, 49 tests, and the audited 2021–2026
  Preview artifacts are complete; V4 and all production behavior are
  unchanged. Worktree holds planning docs and implementation separable for
  two user-controlled commits.
- **Plan Contract:** `docs/plans/2026-08-24/phase1-rating-measurement-foundation.md` (now `Implemented`, with Implementation Record + 3 mechanical amendments appended)
- **Approval / Status:** User authorized Terra execution in-session on 2026-08-24 with "implement first, commit later" commit handling.
- **Blockers:** None.
- **Next:** Phase 2 (minimum viable team-state baseline) requires a fresh Sol contract and Terra task; Week 0 production operations take precedence on game week.

## Context and Decisions

- V4 untouched: no V4 import, config, bundle, ops, or publication path was modified; the ratings package is import-isolated.
- Datasets built at `tier="gold"`; payloads and refs live only under `artifacts/research/rating-successor/measurements/{design_id}/`.
- Canonical 2021 byplay/drives lake versions were resolved by matching each version's parent set to the `reconciled_team_game-2021` manifest (run of 2026-08-11); the 2021 duplicate pair is byte-identical in content, differing only by `code_sha`.
- `success` is null on ~2% of eligible plays (dead-ball markers + some return/completion rows): `success_rate` now divides by eligible plays with computable success, matching the existing `off_sr` mean semantics; flagged per game.
- Output refs/report use run-stamped leaf paths (`runs/{run-stamp}/…`) because dataset identity includes `as_of`; an early un-stamped verification build correctly failed closed on immutable collision and was left in place as history.
- No Preview catalog registration performed (permitted but optional under Approved Default 4).

## Work Completed

- Task 1: `ratings/contracts.py` (frozen catalog, design-ID hashing, frame validators, market-field rejection) + `conf/ratings/measurement_baseline_v1.yaml` (design ID `5c4d5cc4d6a46d4b3d830b50607f7fa0f8984cc63ab6ee64b6a7e626b415f95f`) + executable lake schemas for both datasets in `data/schema_contracts.py`.
- Task 2: `ratings/observations.py` — long-form raw observations with exact numerators/denominators, re-derived `is_drive_play`, garbage gating, fail-closed schedule/outcome/reconciliation/as-of filters, reconstructed-vs-authentic temporal encoding.
- Task 3: `ratings/snapshots.py` — kickoff-ordered pregame snapshots, strictly prior evidence graphs, four-iteration league-centered additive adjustment (Jacobi within iteration), iter-0+4 retention, schedule-strength component, context-only pass-through, explicit first-game missing states.
- Task 4: `scripts/pipeline/build_rating_measurements.py` — Preview-only CLI (rejects `production`, enforces research prefix, immutable writes, idempotent byte-identical reuse, optional catalog registration).
- Task 5: `ratings/audit.py` + Preview build + docs. Final artifacts: observations version `b1da5e85a0438fab109937bf` (96,954 rows), snapshots version `312917237b7b60cb10d61150` (116,792 rows), audit report SHA `05fe64f10177…` under `runs/2026-08-24T1830Z/`. All checks pass (uniqueness, symmetry, reconciliation, 2020/2019 exclusion, future rows, no double counting, market-free). Byte-idempotent rerun verified on the verification build. Redundancy: Spearman vs EPA/play — success 0.92–0.94, explosive 0.78–0.79, points/opp 0.72–0.78.
- Docs: `measurement_catalog.md` (implemented disposition + audit refs) and `rating_system_requirements.md` (implemented handoff) updated.

## Files Modified

- `src/cks_picks_cfb/ratings/{__init__,contracts,observations,snapshots,audit}.py` — new isolated package.
- `conf/ratings/measurement_baseline_v1.yaml` — frozen catalog/adjustment config.
- `scripts/pipeline/build_rating_measurements.py` — Preview-only builder CLI.
- `src/cks_picks_cfb/data/schema_contracts.py` — registered both rating datasets (gold).
- `tests/ratings/{conftest,helpers,test_contracts,test_observations,test_snapshots,test_cli}.py` — 49 tests.
- `docs/modeling/measurement_catalog.md`, `docs/modeling/rating_system_requirements.md` — final Phase 1 disposition.
- `docs/plans/2026-08-24/phase1-rating-measurement-foundation.md` — status → Implemented, amendments + implementation record.

## Validation

- [x] Focused tests: `tests/ratings/` 49 passed.
- [x] Full suite + coverage floor: 463 passed, 2 skipped, 62.04% ≥ 60%.
- [x] `uv run ruff format . && uv run ruff check .` clean.
- [x] `uv run python contracts/validation.py` passed.
- [x] `make contracts-check` passed.
- [x] `uv run mkdocs build --strict --quiet` passed.
- [x] `git diff --check` clean.
- [x] Preview artifacts: all audit checks pass; immutable and reproducible.

## Amendments and Blockers

- Three mechanical amendments recorded in the plan (success-rate exposure basis; run-stamped artifact URIs; nullable lake timestamp columns). No material deviations.

## Handoff Notes

- **Resume at:** Phase 2 planning (Sol) when authorized; consume exactly the refs/checksums in the measurement catalog disposition.
- **Watch out for:** Week 0 production ops take precedence over Week 1 targets; never register research datasets in the production catalog; 2026 snapshot rows currently rest on reconstructed 2025 evidence only until authentic 2026 timing exists.

**tags:** ["ratings", "measurement", "pipeline", "phase1", "opponent-adjustment"]
