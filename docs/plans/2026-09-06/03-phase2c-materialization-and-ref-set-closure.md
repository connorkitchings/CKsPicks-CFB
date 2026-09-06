# Phase 2c Materialization and Ref-Set Closure

- **Status:** Implemented
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

The committed runner now has explicit lineage, immutable-identity, checkpoint,
and ref-set contracts. On 2026-09-06 it materialized the complete Preview-only
corpus, verified its 80 R2 objects and 80 Preview Neon catalog registrations,
and published the sealed Phase 2c ref set. Phase 2d is unblocked to consume
that ref set in a subsequent task; it has not begun here.

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

- [x] Hardened implementation and tests are committed before materialization.
- [x] Committed-SHA dry-run passes the exact corpus and reconciliation gates.
- [x] All 80 per-season outputs are registered and checksum-verified in Preview.
- [x] The complete Phase 2c ref set is published and matches a repeated dry-run.
- [x] Phase 2c is documented as implemented and Phase 2d as unblocked.
- [x] Required validation passes and the evidence-only closeout is ready.

## Implementation Record

- **2026-09-06 code checkpoint:** Added the reusable
  `data_first_phase2c` lineage, immutable-identity, checkpoint, ref-set, and
  omission contracts. The Preview-only runner now validates exact Phase 1/R1
  capture equality plus catalog/source evidence, writes and verifies immutable
  checkpoints on apply, and rejects a final ref set until all ten seasons pass
  the approved corpus gates.
- **Validation:** focused Phase 2c/Silver tests (47), final full Python suite
  with warnings as errors (717 passed, 2 skipped), scoped Ruff format check,
  repository Ruff lint, contracts validation, MkDocs,
  V4/repository-boundary tests (14), and `git diff --check` passed.
- **Committed implementation:** `095f464b6996fe94c2c4259a9c001e6074949e7e`
  established the code checkpoint. `6be713a33ee32c1d661bd536e2db9c9d0fa73ca1`
  retained the runner contract while avoiding a duplicate preflight capture
  read; this is the code SHA bound to the run.
- **Run identity:**
  `2026-09-06T1437Z-phase2c-expanded-silver-v1`, Preview,
  `as_of=2026-09-06T14:37:06+00:00`, identity SHA-256
  `b3a02b56ca0f0c7495ce9bbc8221b38d15ac50be32104a48638e2ffa0e7e41a6`,
  configuration SHA-256
  `75992691ca876bfa4ad871806b828ca8b8e013114793a5cb3d59c919993ea780`.
- **Published ref set:**
  `artifacts/research/data-first-football-v1/phase2/silver/runs/2026-09-06T1437Z-phase2c-expanded-silver-v1/ref-set.json`
  (`data_first_phase2c_ref_set_v1`, complete; manifest SHA-256
  `b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3`).
- **Closure:** ten checkpoints cover 2015–2019 and 2021–2025, with eight
  datasets each (80 total). The verified corpus has 8,936 games/outcomes:
  8,521 regular, 415 postseason, 7,792 FBS–FBS, and 1,144 FBS–FCS. There are
  zero blocking reconciliation conflicts and no 2020 rows. The 32 missing
  regular play responses and one missing regular team-stat response are sealed
  as `provider_response_omission`; `omission_reasons` rejected any postseason
  omission before materialization.
- **Verification:** the first dry-run passed the exact gates; apply reread and
  registered every object before checkpointing; an independent post-apply read
  confirmed all ten checkpoints, 80 readable objects, and 80 matching Preview
  catalog rows. The repeated dry-run completed under the same identity and
  matched the published ref set.

## Amendments

Production changes, provider purchases/calls, schema changes, relaxed gates,
new measurement definitions, or acceptance of an unexplained omission require
a revised plan and explicit approval.
