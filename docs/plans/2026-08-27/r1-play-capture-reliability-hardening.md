# R1 Play-Capture Reliability Hardening

- **Status:** In Progress
- **Created:** 2026-08-27
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact
  plan in Codex on 2026-08-27.
- **Implementation log:**
  `session_logs/2026-08-27/11-r1-play-capture-reliability-hardening.md`
- **Commit policy:** Commit with implementation; the governing historical
  roadmap already received its required separate plan commit.

## Goal

Replace the all-or-nothing 2015–2018 CFBD play capture with a Preview-only,
resumable weekly-request capture set. Every provider week becomes an
independently bounded, checksummed Bronze observation. Silver may proceed only
from a complete, verified, immutable request set.

## Current State

The existing `PlaysIngester` fetches all weekly responses in memory and writes
Bronze captures only after every request has succeeded. A stalled CFBD response
therefore blocks the season and leaves no completed-week evidence. The recorded
2015 diagnostics prove the issue: two terminated child processes and two
operation deadlines left all associated catalog ingestion runs in `running`.

R1 is Preview-only. V4, production operations, candidate-v1, protected 2026
inference, and successor-v2 methodology/tournament rules are unchanged.

## Proposed Approach

Use the existing CFBD weekly request model as the durable unit. A capture-set
header stores the immutable plan; each request has a deterministic semantic
identity and durable attempt history. Successful weeks are captured immediately
and later reused only when their catalog row and R2 object checksum verify.
The compatibility projection and all successor Silver work remain blocked until
the complete request set is present.

## Scope

### Included

- Preview-only successor-history CFBD play capture and its catalog lifecycle.
- Per-request attempt evidence, process isolation, timeout finalization,
  complete capture-set manifests, reconciliation, tests, and operator docs.

### Excluded

- Production/V4 behavior, production Neon/R2 writes, candidate-v1, 2026
  outcomes, 2020 data, market inputs, and rating/tournament selection rules.

## Affected Components and Contracts

- `catalog.ingestion_runs` remains the immutable capture-set header.
- New append-only migration `0009` adds request attempts keyed by
  capture-set ID, deterministic request SHA, and attempt number.
- `history_play_capture_v1` is the successor R1 policy: weekly requests,
  sequential execution, 120-second SDK deadline, 300-second hard deadline,
  four attempts, and bounded backoff.
- `prepare-rating-history` receives the profile only for 2015–2018 play
  capture. Its successful output is a `play-capture-set-v1` manifest with
  explicit ordered capture IDs; downstream Silver consumes that manifest.

## Implementation Tasks

### Task 1 — Persist request-set and attempt contracts

**Changes:**

- Add migration `0009` and schema synchronization for request attempts,
  including request SHA, state, timestamps, error evidence, and capture ID.
- Add catalog APIs to create/resume an immutable planned request set, validate
  the original semantic plan, record attempts, resolve verified completed
  requests, and fail a capture set without deleting evidence.
- Add canonical request hashing that excludes `requested_at` but includes
  provider, entity, endpoint, and exact provider parameters.

**Acceptance criteria:** A retry with the same capture-set ID can use only its
stored plan and exactly one verified capture per request; conflicting, duplicate,
extra, missing, quarantined, or checksum-invalid captures fail closed.

### Task 2 — Build the isolated weekly play-capture path

**Changes:**

- Add the versioned history play-capture policy and a private worker that reads
  a task-scoped temporary request/result payload outside the repository.
- Execute each R1 weekly request sequentially in an isolated process group;
  terminate and clean it up at 300 seconds while preserving provider status for
  retry classification.
- Capture/register every successful week immediately, stop at the first
  exhausted request, and reconstruct the compatibility projection only after
  complete verified capture coverage.
- Calculate the historical play subprocess bound from the planned request count
  and policy rather than applying the old ten-minute season-wide limit.

**Acceptance criteria:** An interrupted/stalled week is terminally recorded,
does not orphan a child or leave an ingestion run `running`, and cannot create a
partial projection or Silver artifact. A rerun skips verified completed weeks.

### Task 3 — Close the capture set and wire R1 consumers

**Changes:**

- Emit an immutable `play-capture-set-v1` completion manifest containing the
  policy/config SHA, code SHA, ordered requests, captures/checksums/row counts,
  and returned/missing game IDs.
- Require this manifest before history Silver can receive 2015–2018 play
  capture IDs; reject incomplete sets and broad ingestion-run queries.
- Add a Preview-only reconciliation interface for the four known abandoned
  2015 runs. It may finalize only runs whose outer R1 step is already failed
  and retains the original diagnostic evidence.

**Acceptance criteria:** Completed-manifest retries are byte-identical. Silver
dependencies are exactly the manifest capture IDs in plan order.

### Task 4 — Document, test, and stage R1 recovery

**Changes:**

- Update the R1 runbook: retry the same pipeline run ID; reserve
  `--skip-capture` for downstream-only recovery after a completion manifest;
  require read-only verification and session-log evidence before Silver.
- Add a Preview-only controlled 2015 Week 1 verification against the known
  15,369-play compatibility sample before the full R1 run is resumed.

**Acceptance criteria:** Operators have exact start, resume, verify,
reconcile, and stop commands without any production path.

## Testing Strategy

- Unit-test canonical request identity, immutable-plan resume, attempt
  sequencing, retry classification, timeout cleanup, and reconciliation rules.
- Integration-test a stalled weekly worker, immediate successful captures,
  no partial projection/Silver on failure, exact resume skipping, collisions,
  checksum mismatch, duplicate or extra requests, missing game diagnostics,
  and byte-identical completion-manifest retries.
- Re-run ingestion, catalog, lake, Silver, ops-state-machine, migration,
  successor-history, V4 production-boundary, contracts, and web regressions.
- Require focused tests, full pytest with the coverage gate, scoped Ruff,
  contracts validation/synchronization, strict MkDocs, CLI smoke tests, and
  `git diff --check`.

## Risks and Edge Cases

- Historical captures are reconstructed research evidence. Capture timestamps
  are observation time, never claimed historical provenance.
- An incomplete capture set is diagnostic-only; it cannot reach measurement,
  state, coverage certification, or tournaments.
- Provider throttling is retried within the sealed policy; a request that remains
  unavailable after exhaustion stops safely rather than weakening coverage.
- The shared R2 bucket remains intentional. Preview Neon catalog state and
  immutable successor namespaces provide isolation.

## Definition of Done

- [ ] Request-attempt contract and migration are applied and synchronized.
- [ ] Isolated, resumable R1 weekly capture passes focused and integration tests.
- [ ] Complete-manifest-only Silver wiring and abandoned-run reconciliation pass.
- [ ] R1 runbook and implementation session log are updated.
- [ ] Required validation passes with no production/V4 behavior changes.
- [ ] Plan status is updated to `Implemented`.

## Amendments

None at approval. Material changes to weekly capture granularity, same-set
resume semantics, production isolation, or R1 coverage gates require a new
planning review.
