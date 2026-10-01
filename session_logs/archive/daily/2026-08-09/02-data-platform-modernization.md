# Session: 2026 Data Platform Modernization

## TL;DR

- **Worked On:** Implemented immutable lake/catalog contracts, run-specific grading, resumable orchestration, model bundle v2 controls, and serving correctness for the 2026 season.
- **Completed:** Code, schemas, migrations, tests, operational commands, and documentation are ready for an environment-backed preview rollout.
- **Blockers:** Live migration/replay requires an isolated Neon preview branch, preview R2 bucket/credentials, explicit immutable dataset versions, and a promoted `model_bundle_v2`.
- **Next:** Provision preview infrastructure, publish/freeze the promoted bundle and dataset refs, run migrations, then execute the 2025 preview replay and 2026 Week 1 readiness rehearsal.

## Changes Made

- Added content-addressed Bronze captures and immutable Silver/Gold dataset manifests with lineage, validation, checksums, and point-in-time selection.
- Added provider-neutral source adapters, CFBD retry/failure handling, capture deduplication, quarantine behavior, and catalog registration.
- Added `catalog` and `ops` schemas, append-only checksummed migrations, canonical market snapshots, run-specific prediction grades, role boundaries, and compatibility behavior.
- Added the resumable `cks_picks_cfb.ops` state machine for readiness, publish, freeze, close, replay, and reconciliation.
- Added `model_bundle_v2` validation and direct ten-cell spread/total regime routing with explicit feature datasets and bookmaker-feature exclusion.
- Updated publication, scoring, and website reads to resolve immutable runs through Neon; added signed on-demand Next.js revalidation.
- Updated environment templates, Make targets, architecture/runbook documentation, and migration guidance.

## Testing

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run pytest -q` — 233 passed, 12 existing numerical warnings
- [x] `.venv/bin/python contracts/validation.py`
- [x] `git diff --check`
- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run build`
- [x] `uv run mkdocs build` — succeeds with two pre-existing broken-link warnings

## Notes for Next Session

Do not run production publication until `PREVIEW_DATABASE_URL`, `CFB_R2_PREVIEW_*`, `CFB_MODEL_BUNDLE_URI`, and explicit prediction dataset references are configured and the preview replay passes. R2 is authoritative for immutable bytes; Neon is authoritative for version selection, pipeline state, and active/frozen runs. Mutable R2 pointers remain only under the deprecated `legacy-pointers` namespace for compatibility.

**Proposed commit:** `feat: modernize 2026 data platform and resumable pipeline`

**tags:** ["data-platform", "r2", "neon", "orchestration", "model-bundle", "2026"]
