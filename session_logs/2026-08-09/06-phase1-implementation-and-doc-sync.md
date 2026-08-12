# Session: Phase 1 Implementation + Documentation Sync

## TL;DR

- **Worked On:** Implemented Phase 1 of the approved execution plan (legacy
  market quarantine + canonical Week 0 policy + exact-market audit) and
  synchronized all project documentation to reflect current 2026 status.
- **Completed:** Both Silver dataset contracts, the schedule policy builder
  script, the 2026 Week 0 game-ID assignments file, provider-based capture
  routing, the exact-market audit mode, 17 contract tests, and five doc
  updates. All quality gates pass.
- **Blockers:** None for Phase 1. External blockers for later phases: CFBD
  talent feed still empty (gates preseason snapshot); Week 1 betting line
  coverage 51/99.
- **Next:** Run `make import-history` in preview to begin Phase 2.

## Changes Made

### Phase 1: Legacy Market Adjudication (B1)

- `src/cks_picks_cfb/data/silver.py`: Added `legacy_market_references`
  SilverContract and `normalize_legacy_market_references()` normalizer.
  Every row is stamped with `exact_replay_eligible=false`,
  `grading_eligible=false`, `lean_eligible=false`, and
  `timestamp_status=missing_authentic_timestamp`. Rejects non-legacy
  providers and records with authentic timestamps.
- `src/cks_picks_cfb/data/silver.py`: Added `DATASET_PROVIDERS` routing
  table. Canonical `market_quotes`/`market_snapshots` only consume `cfbd`
  captures; `legacy_market_references` only consumes `legacy_cfbd_export`.
- `scripts/pipeline/build_history_silver.py`: Added
  `legacy_market_references` to SOURCE_ENTITIES, provider-filtered capture
  selection, provenance stamping (`__source_uri`, `__source_sha256`), and
  `--week-policy-ref-uri` support.
- `scripts/pipeline/build_silver.py`: Same provenance stamping and
  `--week-policy-ref-uri` support.
- `scripts/pipeline/assemble_model_ready_features.py`: Made
  `--markets-ref-uri` optional. Added `require_dataset` guard to reject
  any ref that is not `market_snapshots`. Validation now reports
  `markets_joined` flag and skips timestamp check when no markets joined.
- `src/cks_picks_cfb/data/lake.py`: Added `require_dataset()` helper.

### Phase 1: Canonical Week 0 Policy (B2)

- `src/cks_picks_cfb/data/silver.py`: Added `schedule_week_policy`
  SilverContract and `normalize_schedule_week_policy()` normalizer with
  full coverage validation. Updated `normalize_games()` to preserve
  `provider_week` and accept an optional `week_policy` frame that assigns
  `canonical_week`. Games contract schema bumped to `games_v2`.
- `src/cks_picks_cfb/data/week_policy.py` (new): Week policy module with
  `WeekAssignment`, `WeekPolicySpec`, `load_week_policy_spec()`,
  `build_policy_rows()`, and `policy_config_sha()`.
- `scripts/pipeline/build_schedule_week_policy.py` (new): Builds the
  versioned `schedule_week_policy` Silver dataset from games captures and
  explicit assignments.
- `conf/policy/canonical_week_2026_v1.yaml` (new): Explicit Week 0
  assignments for the 8 verified August 29 opening-slate games (game IDs
  and kickoffs confirmed against production source R2).

### Phase 1: Exact-Market Audit Mode (B3)

- `src/cks_picks_cfb/ops/data_audit.py`: Updated `required_silver` to
  exclude market datasets (they're expected absent for historical
  bootstrap). Added coverage for legacy market rows and canonical market
  versions. Added `audit_exact_markets()` function that verifies legacy
  quarantine flags, lineage purity (no legacy in canonical, no non-legacy
  in legacy), and reports promotion-gate blockage.
- `src/cks_picks_cfb/ops/__main__.py`: Added `exact-market` to
  `--mode` choices. Restructured `_history_silver_steps` to build Week 0
  policy for 2026, build legacy references for all seasons, make canonical
  market builds optional, update combine list, and drop markets from
  selection Gold assembly. Added `--week-policy-ref-uri` to build-silver op.

### Phase 1: Contract Tests (B4)

- `tests/test_silver_reconciliation.py`: 11 new tests for legacy normalizer
  (flags, provider rejection, timestamp rejection, provenance, spread/total),
  games provider_week preservation, games policy application, incomplete
  policy rejection, schedule week policy validation, and `require_dataset`.
- `tests/test_week_policy.py` (new): 6 tests for policy spec loading,
  duplicate detection, canonical week assignment, unknown game rejection,
  kickoff mismatch rejection, and season mismatch.
- `tests/test_history_bootstrap.py`: Added provider routing test.

### Documentation (Part A + B5)

- `docs/planning/roadmap.md`: Full rewrite as 2026 execution roadmap with
  timeline, phase status, external blockers, and stop conditions.
- `AGENTS.md`: Replaced stale V2 "PAUSED" section with current 2026
  execution status. Updated data line and date.
- `docs/guide.md`: Updated header, reframed V2 as reference, added 2026
  execution plan links and data platform links.
- `.agent/CONTEXT.md`: Fixed stale production models reference (Nov 2024
  CatBoost/XGBoost → 2026 per-regime routing). Updated time period.
- `README.md`: Added execution phase pointer. Updated key docs list.
- `docs/planning/2026_historical_bootstrap_week0_execution.md`: Marked
  Phase 1 items as complete. Updated resume point to Phase 2.
- `docs/architecture/data_platform_2026.md`: Added legacy market references
  and canonical week policy documentation.

## Testing

- [x] `uv run ruff format .` — clean
- [x] `uv run ruff check .` — clean
- [x] `uv run pytest -q` — 285 passed, 5 pre-existing external_ratings failures
- [x] `uv run python contracts/validation.py` — passed
- [x] `npm run lint` in `web/` — passed
- [x] `npm run typecheck` in `web/` — passed
- [x] `npm run build` in `web/` — passed
- [x] `git diff --check` — clean

## Notes for Next Session

Phase 1 is code-complete. The next boundary is the resumable historical
bootstrap import. Run `make import-history` in preview to begin Phase 2.
No additional credential setup is needed — read-only source R2, preview R2,
and preview Neon are configured and verified.

The 2026 opening slate game IDs (8 FBS-vs-FBS games on August 29) are
verified against the production source and encoded in
`conf/policy/canonical_week_2026_v1.yaml`. If the schedule changes, a new
policy version file is required.

**Proposed commit:** `feat(phase1): encode legacy market quarantine and canonical Week 0 policy`

**tags:** ["phase-1", "legacy-market", "week-0", "policy", "audit", "documentation"]
