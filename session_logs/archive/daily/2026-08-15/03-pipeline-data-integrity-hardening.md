# Session: Pipeline and data integrity hardening

## TL;DR

- **Worked On:** Implemented the approved v2 lineage, environment isolation, durable pipeline ownership, and executable schema contract plan.
- **Outcome:** New immutable datasets have v2 identities and schema hashes; mutating operations resolve explicit environments; pipeline resume is definition-bound, lease-fenced, and output-verified; PostgreSQL migration and CI coverage validate fresh and pre-hardening upgrade paths.
- **Plan Contract:** `docs/plans/2026-08-15/pipeline-data-integrity-hardening.md`
- **Approval / Status:** User authorized implementation; contract marked `Implemented` after validation.
- **Blockers:** None.
- **Next:** Review the changes and apply migration `0006_pipeline_data_hardening.sql` to Preview in a separately approved rollout before running lease-fenced operations there.

## Context and Decisions

- Existing v1 R2 artifacts and catalog rows remain readable and were not rebuilt or mutated.
- New writes use `dataset_identity_v2`, which includes point-in-time cutoff, partitions, schema SHA, content, ordered parent identities, captures, code, and config without parent URIs.
- Preview never falls back to production credentials. Mutating Make and direct pipeline paths require an explicit target environment.
- A 120-second DB lease with a 30-second heartbeat is authoritative. The monotonically increasing epoch is propagated to subprocesses and checked in publish, freeze, and scoring transactions.
- Output-bearing steps may resume only after their validators verify durable outputs; all other completed steps rerun.

## Work Completed

- Added executable Silver and Gold schema contracts, schema SHA registration, pre-write validation, and strict immutable catalog conflict handling.
- Added the append-only `0006_pipeline_data_hardening.sql` migration and schema snapshot parity.
- Added run and step definition hashing, leases, heartbeats, stale-worker fencing, and verified resume semantics.
- Added fresh and synthetic pre-hardening PostgreSQL migration integration coverage to CI.
- Updated operational and architecture documentation for explicit environments and v2/lease behavior.

## Files Modified

- `src/cks_picks_cfb/data/` - v2 identity, runtime resolution, executable schemas, Silver validation, and strict catalog registration.
- `src/cks_picks_cfb/ops/` - definition-bound state machine, durable leases, and database write fencing.
- `scripts/pipeline/` - fail-closed environment resolution and fenced publish/freeze/score writes.
- `contracts/` and `contracts/migrations/0006_pipeline_data_hardening.sql` - schema and migration contract updates.
- `.github/workflows/ci.yml`, `tests/`, `.codex/QUICKSTART.md`, and `docs/` - validation coverage and operating guidance.

## Validation

- [x] `TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55432/cks_picks_test uv run pytest -q tests/test_migration_integration.py` — 2 passed
- [x] `uv run pytest -q` — 321 passed, 2 skipped
- [x] `uv run ruff check .`
- [x] Scoped `uv run ruff format --check ...`
- [x] `uv run python contracts/validation.py`
- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`

## Amendments and Blockers

- None. A temporary local PostgreSQL 16 container was used only for migration validation and removed afterward.

## Handoff Notes

- **Resume at:** Review and commit the hardening change set; plan a separately approved Preview migration/code rollout.
- **Watch out for:** Do not run the new lease-fenced pipeline code against an unmigrated database. Preserve the untracked `artifacts/preview/` directory; it is user-owned and outside this change.

**tags:** ["pipeline", "data-platform", "integrity", "catalog", "migrations"]
