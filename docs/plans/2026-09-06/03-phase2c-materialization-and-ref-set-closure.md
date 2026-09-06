# Phase 2c Materialization and Ref-Set Closure

- **Status:** In Progress
- **Created:** 2026-09-06
- **Planner:** Sol
- **Approval source:** User explicitly approved implementation of this exact contract on 2026-09-06.
- **Implementation log:** `session_logs/2026-09-06/04-phase2c-materialization-and-ref-set-closure.md`
- **Commit policy:** Separate plan, implementation, and evidence commits

## Goal

Finish Phase 2c by hardening the committed Preview-only rebuild runner,
materializing the ten-season regular-plus-postseason Silver corpus at a
committed code SHA, verifying every immutable object and catalog registration,
and publishing the exact ref set required by Phase 2d.

## Current State

Commit `79e760b` contains the initial Phase 2c runner and mixed-capture
normalization fixes. The repository has no tracked modifications other than the
unrelated `.opencode/` directory, but the Preview Phase 2c output prefix is
empty: no season checkpoint, dataset ref, or final ref set exists. Phase 2d
therefore has no authorized input.

The runner selects the intended manifests and can calculate the corpus, but it
does not yet prove Phase 1/R1 source-set equality, preserve complete capture
checksum/timing evidence in its ref set, or implement the promised immutable
resume protocol. Its script-level orchestration also lacks focused tests.

## Proposed Approach

Treat this as Phase 2c closure, not Phase 2d. Extract testable selection and
evidence helpers, strengthen the existing runner without changing its CLI or
Silver schemas, commit that implementation, then run dry-run and apply with one
fresh immutable identity. Phase 2d remains blocked until the verified ref set
is complete.

## Scope

### Included

- Exact source-manifest and capture-lineage validation.
- Explicit omission, timing, population, and reconciliation evidence.
- Immutable per-run and per-season checkpoints with verified resumption.
- Preview Silver materialization, catalog/R2 verification, and Phase 2c
  documentation closeout.

### Excluded

- Phase 2d audit v4, eligibility, measurements, or automation activation.
- Provider calls, schema-version changes, production, V4, model selection,
  2020, and `.opencode/`.

## Affected Components and Contracts

- `scripts/research/build_data_first_phase2c.py` remains the public execution
  CLI. Its existing arguments remain stable.
- Move reusable validation/ref-set logic into the data package or an equivalent
  importable module so it can be unit-tested without executing the CLI.
- `data_first_phase2c_ref_set_v1` is the sole Phase 2c output authorized as an
  input to Phase 2d. Existing Silver schema versions remain unchanged.

## Implementation Tasks

### Task 1 — Complete exact input validation

**Changes:**

- Require the Phase 1 v3 regular capture IDs to equal the corresponding
  certified R1 source-set entries for every season and entity.
- Hash and record the raw bytes of all input manifests, including manifests
  without embedded hashes.
- Resolve every Phase 2 run result back to its request and catalog capture;
  verify provider, entity, endpoint, year, season type, Week 1 where applicable,
  classification, registered state, timing class, row count, content checksum,
  object checksum, and readable object.
- Reject 2020, duplicates, conflicting game identities, crossed run identities,
  malformed manifests, and any Preview/production ambiguity.

**Acceptance criteria:** All selected sources are exact, checksum-verifiable,
and attributable to one sealed manifest. A single mismatch fails before any
write.

### Task 2 — Complete evidence and immutable resumption

**Changes:**

- Emit an immutable run identity binding run ID, environment, `as_of`, code
  SHA, configuration SHA, source manifests, and their checksums.
- After each season succeeds, emit one immutable checkpoint containing source
  evidence, output refs, row counts, populations, season types, omissions, and
  reconciliation classes.
- On restart, accept only a byte-identical run identity. Verify every
  checkpointed R2 object, dataset checksum, schema, and Preview catalog row
  before skipping that season.
- Assign exact reasons to missing play/stat detail, such as
  `provider_response_omission`; retain schedule rows and never synthesize FCS
  detail.
- Publish the final ref set only after all ten checkpoints pass. Include exact
  capture requests, timing classes, capture checksums, output refs, parents,
  counts, omissions, code/config identities, and a deterministic manifest
  checksum.

**Acceptance criteria:** Interrupted execution can resume safely under the same
identity; changed inputs or code require a new run ID. No partial run can
produce a complete ref set.

### Task 3 — Validate and materialize the corpus

**Changes:**

- Commit Tasks 1–2 before data operations.
- Generate one UTC `as_of` and a run ID ending in
  `phase2c-expanded-silver-v1`; reuse both for dry-run and apply.
- Review the dry-run's exact 80-output plan: eight datasets for each of ten
  seasons. Apply only if it reports 8,936 games (8,521 regular, 415
  postseason), 7,792 FBS-FBS, 1,144 FBS-FCS, 8,936 outcomes, complete
  postseason plays/stats, only evidence-backed regular omissions, no 2020, and
  zero blocking reconciliation conflicts.
- Execute apply in Preview, verify every R2 object and Neon registration, then
  compare the committed ref set with a repeated dry-run.

**Acceptance criteria:** `ref-set.json` is `complete`, checksummed, covers all
ten permitted seasons, and exactly matches verified Preview storage/catalog
state.

### Task 4 — Close Phase 2c

**Changes:**

- Record actual run identity, refs, checksums, row/population counts,
  exclusions, reconciliation results, and validation in the Phase 2 contract
  and implementation log.
- Mark this contract and Phase 2c `Implemented`, mark Phase 2d `Unblocked`, and
  keep overall Phase 2 `In Progress`.
- Propose a documentation-only evidence commit for the user.

## Testing Strategy

- Unit-test Phase 1/R1 equality, crossed lineage, capture provenance/timing,
  manifest hashing, duplicate/conflict rejection, 2020 rejection, and omission
  reasons.
- Test dry-run non-mutation, deterministic ref-set hashing, immutable identity
  collisions, partial-season resumption, corrupt/missing checkpoint outputs,
  and exact ten-season/eight-dataset closure.
- Retain mixed timestamp, serialized team-stat, regular/postseason builder, and
  reconciliation regression tests.
- Run focused Phase 2c tests, warning-as-error Python coverage, Ruff lint and
  scoped format-check, contracts validation, MkDocs, V4 compatibility checks,
  and `git diff --check`. Do not broad-format the 24 unrelated files already
  known to fail repository-wide format-check.

## Risks and Edge Cases

- R2 writes and Neon registration are not one transaction; deterministic
  identities plus checkpoint verification provide safe convergence.
- Missing regular play detail is permissible only when supported by the exact
  certified R1 manifests. Postseason omissions are not expected and block
  apply.
- The Phase 1 v3 state `resolved_with_blockers` is accepted only for its exact
  verified selections; the unrelated non-canonical research objects remain
  visible and do not become eligible through Phase 2c.

## Definition of Done

- [ ] Hardened implementation and tests are committed before materialization.
- [ ] Committed-SHA dry-run passes the exact corpus and reconciliation gates.
- [ ] All 80 per-season outputs are registered and checksum-verified in Preview.
- [ ] The complete Phase 2c ref set is published and matches a repeated dry-run.
- [ ] Phase 2c is documented as implemented and Phase 2d as unblocked.
- [ ] Required validation passes and the evidence-only closeout is ready.

## Implementation Record

- **2026-09-06 code checkpoint:** Added the reusable
  `data_first_phase2c` lineage, immutable-identity, checkpoint, ref-set, and
  omission contracts. The Preview-only runner now validates exact Phase 1/R1
  capture equality plus catalog/source evidence, writes and verifies immutable
  checkpoints on apply, and rejects a final ref set until all ten seasons pass
  the approved corpus gates.
- **Validation:** focused Phase 2c/Silver tests (47), full Python suite with
  warnings as errors (716 passed, 2 skipped), Ruff lint/format check,
  repository lint, contracts validation, MkDocs, V4/repository-boundary tests
  (14), and `git diff --check` passed.
- **Materialization blocker:** Per the contract, the implementation must be
  committed before dry-run/apply so immutable identities bind the code SHA.
  The user-owned implementation commit is pending; no Phase 2c R2/Neon writes
  or provider calls have occurred.

## Amendments

Production changes, provider purchases/calls, schema changes, relaxed gates,
new measurement definitions, or acceptance of an unexplained omission require
a revised plan and explicit approval.
