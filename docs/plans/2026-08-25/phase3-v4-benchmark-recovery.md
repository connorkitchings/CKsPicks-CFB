# Phase 3 V4 Historical Benchmark Recovery

- **Status:** Implemented
- **Created:** 2026-08-25
- **Planner:** Sol
- **Approval source:** User explicitly authorized the approved recovery plan on 2026-08-25.
- **Implementation logs:** `session_logs/2026-08-25/02-v4-benchmark-recovery.md`,
  `session_logs/2026-08-25/03-v4-benchmark-recovery-materialization.md`
- **Commit policy:** Commit code and configuration before any Preview artifact write.

## Goal

Recover a complete, immutable, research-only historical V4 comparison artifact
for Phase 3.  The artifact must reproduce the frozen Games 1--4 routes and
derive a temporally valid established-route replay without modifying V4,
production, Neon, or publication.

## Current State

The frozen V4 selection and locked reports preserve route decisions and the
strict feature references, but no final game-level routed historical artifact
was retained.  The bundle's recorded code SHA (`5371d7f...`) predates the
corrective V4 materialization commit (`33432e8`); that discrepancy remains a
historical fact and is not repaired in place.

## Implementation Tasks

### Task 1 -- Add the isolated replay contract and engine

**Changes:**

- Add a versioned `rating_v4_historical_predictions_v1` frame contract and a
  Preview-only CLI under the ratings research namespace.
- Freeze the two strict model-ready refs, V4 reports, V4 bundle, V2
  established-route source manifest, 2022--2025 folds, and output prefix in
  a versioned configuration.
- Require the recovery code/configuration to be tracked and byte-identical to
  its recorded commit before a Preview write.
- Execute candidate generation from a temporary detached worktree at
  `33432e8`; retain the recovery-code SHA separately from the historical bundle
  SHA.

**Acceptance criteria:**

- Production targets, catalog registration, model-bundle writes, and output
  paths outside `artifacts/research/rating-successor/v4-benchmark-replay/` are
  rejected before any read or write.
- The report permanently records the bundle-code discrepancy as a warning.

### Task 2 -- Recover and certify historical predictions

**Changes:**

- Rebuild Games 1--4 using only each frozen route, feature variant,
  shrinkage design, and blend weight.  Apply the selection routing to
  2022--2024 and finalized routing to 2025; never reselect a route.
- Rebuild `established` from the V4 manifest's exact direct-Ridge feature
  order and alpha on strictly preceding established rows.  Label these rows
  `derived_compatibility_replay`; label Games 1--4
  `native_route_replay`.
- Emit one prediction per `(season, game_id, target)` plus immutable dataset
  ref, audit, and manifest.  Report route coverage, parent checksums,
  training-year chronology, source kinds, frozen-report parity, and all
  exclusions.

**Acceptance criteria:**

- Every eligible 2022--2025 V4 game has exactly one spread and total row.
- Games 1--4 reproduce frozen aggregate metrics; established rows pass strict
  lineage, chronology, and deterministic replay checks.
- Failed certification may retain only its immutable diagnostic report and
  must not publish successful ref files.

### Task 3 -- Gate Phase 3 on the recovered artifact

**Changes:**

- Amend the Phase 3 contract to consume only the passing recovery ref for
  paired V4 comparisons and to retain `source_kind` in its evaluation output.
- Do not alter any Phase 3 prediction or historical safety threshold.

## Testing Strategy

- Unit-test frozen-route extraction, blends, direct and points-derived routes,
  established chronology, duplicate/missing keys, checksum/report tampering,
  resultless rows, and rejection of retrospective full-refit predictions.
- Integration-test Preview-only CLI isolation, commit identity, audit-gated
  ref publication, and immutable reruns with local storage/test engine seams.
- Run focused ratings tests, the full Python suite, Ruff, contracts validation,
  strict MkDocs, and `git diff --check` before materialization.

## Definition of Done

- [x] The recovered V4 benchmark artifact and passing audit exist in Preview.
- [x] The early-route replay matches frozen report metrics and the established
  route is explicitly, reproducibly labeled derived compatibility evidence.
- [x] Immutable reruns are byte-identical.
- [x] Phase 3 documentation names the certified comparison ref and no V4 or
  production interface has changed.
- [x] This contract is marked `Implemented` with a complete session log.

## Amendments

### Amendment 1 -- Pre-materialization lineage hardening (2026-08-25)

**Reason:** Review of the first implementation found that the audit labeled a
data URI as a manifest URI, the configured V4 experiment path was not used by
the replay subprocesses, and established spread/total feature-order equality
was assumed rather than checked.

**Revised approach:** The recovery CLI now derives the actual lake manifest
URI, passes the frozen experiment path to every pinned-engine subprocess, and
rejects unequal established feature orders. A local-storage integration test
also proves successful ref publication and a byte-identical same-run rerun.

**Impact:** No public, V4, production, or artifact-interface change. The
first Preview materialization remains gated on a commit containing these
corrections.

### Implementation Record -- Certified Preview recovery (2026-08-25)

- **Recovery code commit:** `a8827bfda34f6fb5e2ef43c8c6993f8dfe93dd21`;
  **pinned replay engine:** `33432e81465aea67206df938cf48182b3684add9`.
- **Design ID:** `341285d246cb24c1e4d978e60eeed306b67a5734931324c807b17da799bf97c3`;
  **cutoff:** `2026-08-25T13:23:26Z`; **run:**
  `2026-08-25T1323Z-v4-recovery`.
- **Prediction ref:** `rating_v4_historical_predictions_v1`, version
  `f4ec062c7f931f125ce6be99`, content SHA
  `6bdbe75ce83554c5828ac1a807056e26844db44c77defb6607d2ec7386efca2d`,
  URI `lake/gold/dataset=rating_v4_historical_predictions/version=f4ec062c7f931f125ce6be99/data.parquet`.
- **Audit:** all six checks pass; report SHA
  `f601ba9d24becc07019d0bfb97e6d8ed74801eaae3da89f2148e52dbfd821538`;
  manifest SHA
  `4c20a1deab68a5994575c84cdedc00a418e12a3b364a66feae2151810b2a9f2b`.
- **Coverage:** 5,994 expected and recovered game-target rows (2022: 1,468;
  2023: 1,500; 2024: 1,504; 2025: 1,522). Of these, 2,270 are
  `native_route_replay` and 3,724 are `derived_compatibility_replay`.
- The same-stamp rerun returned the identical prediction version, content SHA,
  and audit SHA. No Neon, production, V4, public, or catalog state changed.
