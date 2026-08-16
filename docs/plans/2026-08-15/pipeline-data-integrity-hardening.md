# Pipeline and Data Integrity Hardening

- **Status:** Implemented
- **Created:** 2026-08-15
- **Planner:** Sol
- **Approval source:** User instruction in this Codex task: “Implement the plan.”
- **Implementation log:** `session_logs/2026-08-15/03-pipeline-data-integrity-hardening.md`
- **Commit policy:** Separate, reviewable hardening commit; Git actions remain user-controlled.

## Goal

Harden the pipeline's immutable data lineage, environment boundaries, durable run
ownership, and executable dataset schemas without rebuilding, mutating, or
invalidating existing v1 Preview artifacts and workflow history.

## Current State

- Existing immutable objects, catalog rows, and pipeline history use v1 dataset
  identities and remain readable evidence.
- Dataset identity currently omits the point-in-time cutoff and failed manifests
  can be overwritten.
- Preview-aware builders can fall back to production database configuration.
- Resumption does not bind a run ID to an exact context or step graph, and its
  advisory lock is vulnerable to connection loss during long steps.
- Silver contracts verify required columns and keys, but do not provide
  executable types/nullability/domain schemas; `catalog.schema_versions` is
  unused.

## Proposed Approach

Introduce v2 identity and schema metadata only for new builds. Centralize
environment resolution, make run definitions immutable, use durable Neon leases
with fencing for run ownership, and validate all active Silver and Gold schemas.
Preserve v1 read compatibility and refuse unsafe legacy resumption.

## Scope

### Included

- v2 dataset identity, immutable manifest behavior, and strict catalog conflicts.
- Fail-closed environment selection and explicit mutating CLI environments.
- Run definition hashing, durable leases, fencing, typed outputs, and verified
  resume behavior.
- Executable schemas for active Silver and Gold datasets, schema registration,
  migration parity tests, and CI PostgreSQL coverage.

### Excluded

- Rebuilding or changing existing v1 R2 artifacts or catalog records.
- Broad artifact reconciliation, monitoring dashboards/alerts, documentation
  remediation, module decomposition, and unattended automation.
- Production migration, data publication, deployment, or Pick'em submission.

## Affected Components and Contracts

- Lake and catalog contracts in `src/cks_picks_cfb/data/`.
- Operations state machine and all mutating pipeline entry points.
- Append-only migration `0006_pipeline_data_hardening.sql` and shared contract
  validation.
- CI PostgreSQL migration checks.

## Implementation Tasks

### Task 1 — Versioned immutable identities and catalog registration

**Changes:**

- Add v2 identity/schema metadata to new dataset build manifests. Include
  normalized cutoff, partitions, schema SHA, content, ordered parent identities,
  source captures, code, and config in v2 identity; exclude parent URIs.
- Treat manifests without identity metadata as v1. Keep v1 read/registration
  behavior compatible, but never overwrite a canonical manifest.
- Validate before canonical writes; failed v2 validation produces no canonical
  lake data or manifest.
- Replace blind catalog conflicts with equality-checked idempotency for
  ingestion runs, source captures, schemas, datasets, and dependency edges.

**Acceptance criteria:**

- Distinct cutoffs or partitions yield distinct v2 versions; URI-only changes do
  not.
- Exact retries succeed; metadata/lineage collisions fail.
- Existing v1 manifests remain readable.

### Task 2 — Fail-closed environments and immutable run definitions

**Changes:**

- Introduce a shared runtime environment resolver. Preview requires Preview
  credentials and never falls back to production.
- Require explicit environments for every mutating Make/CLI path and pass the
  selected environment to child processes.
- Persist canonical pipeline and ordered step definitions with SHA-256 hashes.
- Permit resume only with an exact definition match; definition-less legacy runs
  cannot resume under the new runner.

**Acceptance criteria:**

- Missing Preview configuration fails even if production credentials exist.
- Changed command, scope, cutoff, configuration, or step graph is rejected.

### Task 3 — Leases, fencing, and verified resume

**Changes:**

- Add DB lease owner, monotonically increasing epoch, expiry, and heartbeat.
- Use a 120-second lease and 30-second heartbeat. All state mutations require
  the active owner and epoch; stale workers cannot finalize a run.
- Pass the lease context to activation, freezing, and scoring transactions.
- Store typed output references and validate them before skipping a completed
  step; steps without durable output validation rerun.

**Acceptance criteria:**

- Expired leases can be taken over; stale epochs are fenced.
- Valid outputs skip on resume, corrupt/missing outputs rerun, and unsafe steps
  rerun.

### Task 4 — Executable schemas and migration parity

**Changes:**

- Define Arrow-compatible executable schemas for every active Silver contract
  and active Gold output. Include key/type/nullability/domain rules and schema
  JSON/SHA registration.
- Allow dynamic Gold features only under explicit numeric/boolean prefix rules.
- Add migration `0006_pipeline_data_hardening.sql` for new catalog and workflow
  metadata.
- Strengthen shared contract validation and add PostgreSQL fresh/upgrade schema
  parity tests in CI.

**Acceptance criteria:**

- New v2 datasets validate/register their schema; invalid types, nullability,
  domain, or dynamic-feature values fail.
- Fresh snapshot and legacy upgrade paths produce equivalent normalized schema,
  constraints, indexes, and grants.

## Testing Strategy

- Unit tests for v1/v2 identity, failed validation, catalog collision behavior,
  environment isolation, definition mismatch, leases/fencing, and resume output
  verification.
- Schema contract tests for all active Silver and Gold datasets.
- PostgreSQL 16 migration integration tests in CI for fresh and upgrade paths.
- Full Python tests, Ruff format check/lint, contract validation, documentation
  build, and `git diff --check`.

## Risks and Edge Cases

- Existing v1 rows cannot gain mandatory metadata retroactively; v2-only rules
  are enforced in application code and nullable migration columns.
- A deployment must not mix old and lease-fenced runners. Preview validates the
  migration/code order before any separately approved production rollout.
- Immutable R2 and catalog writes remain retriable but must fail on divergent
  identity instead of silently accepting a conflict.

## Definition of Done

- [x] All four tasks and acceptance criteria are complete.
- [x] Existing v1 artifacts remain readable and unmodified.
- [x] Required unit, integration, CI configuration, and quality checks pass.
- [x] No production data operation, migration, deployment, or submission occurs.
- [x] This contract and the implementation session log are updated.
- [x] Status is `Implemented` after validation passes.

## Amendments

None.
