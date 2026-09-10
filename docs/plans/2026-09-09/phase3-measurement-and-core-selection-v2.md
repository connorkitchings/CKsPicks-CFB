# Phase 3 v2: Streaming Measurement Replay and Core Selection

- **Status:** In Progress
- **Created:** 2026-09-10
- **Planner:** Astra
- **Approval source:** User explicitly approved this replacement contract on 2026-09-10.
- **Implementation log:** `session_logs/2026-09-10/01-phase3-v2-streaming.md`
- **Supersedes:** `docs/plans/2026-09-08/phase3-measurement-and-core-selection-v2.md`
- **Commit policy:** The user creates the clean committed checkpoint required before Preview apply and executes all Git operations.

## Summary

Replace the incomplete all-in-memory Phase 3 v2 implementation with bounded,
deterministic materialization. Preserve the sealed Repair v2 parent, six-hour
availability policy, fixed football measurements, candidate registry, gates,
and Preview-only boundary. V4, Phase 4–6, Neon, web, production, and local
repository data are out of scope.

## Binding Inputs and Invariants

Repair v2 is the sole modeling parent:

```text
artifacts/research/data-first-football-v1/repair/v2/runs/
repair-v2-20260909T1417Z/repair-manifest.json
raw SHA-256: b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4
canonical SHA-256: 2fefcb95a2e8b4ae27e8fb2bf740328413aa576bcd725ebd9a18378edd50ac48
```

The 2015–2019 and 2021–2025 population remains exactly 8,936 scheduled,
8,935 forecast-eligible, and 8,903 measurement-usable games. The 32 completed
measurement-missing games remain eligible; `401640992` remains incomplete and
forecast-ineligible. 2020 is forbidden. The chosen source admission rule is
strictly prior canonical week plus `source_kickoff_utc + 6h <= earliest target
week kickoff`; every historical result remains `historically_reconstructed`.

Expected outputs remain: 303,790 observations, 1,215,160 snapshots,
6,777,120 adjusted-history rows, 6,318 validation games, and 202,176
candidate predictions. The frozen two-recurrency, four-pass adjustment,
eight-candidate Ridge tournament, 2,000-draw common bootstrap, and selection
gates are unchanged.

## Implementation

- Add an append-only shared-lake `partitioned_dataset_v1` interface. It writes
  schema-bound immutable child `DatasetRef`s then a root manifest containing
  ordered partition keys, child refs, child and canonical row digests, counts,
  aggregate logical digest, parent lineage, and root checksum. Add bounded
  `iter_partitioned_dataset()` reads; do not alter legacy `read_dataset()`.
- Partition Phase 3 population and observations by season; snapshots and
  adjusted history by `(season, week)`; terminal and predictions by season;
  attribution as one partition. Validate every partition's schema, key space,
  timing, domain, count, and canonical digest. Retain only iteration-four core
  state needed by the tournament, never all snapshots or history.
- Make dry runs fully compute the streaming preflight and emit partition
  inventory, digests, counts, cutoff/fallback summaries, and selection without
  writes. Apply repeats preflight; writes an immutable publication plan; streams
  parts while matching the preflight digest; and writes root manifests,
  certification, and retained core last. A missing root manifest is incomplete
  and ineligible; exact child parts may be reused after interruption.
- Change Phase 3 `output_refs` to explicit `partitioned_dataset_v1` refs. The
  retained-core and certification documents bind root/logical digests, exact
  Repair lineage, code/config, timing, and
  `production_activation_authorized=false`.
- Update the independent verifier to stream stored and independently rebuilt
  partitions, verify all checksums before decode, compare aggregate digests and
  counts, and then independently recompute selection evidence.

The existing runner CLI remains unchanged. Apply requires Preview R2/catalog
credentials, exact parent/config/code SHA, and a clean tracked worktree.

## Validation and Rollout

- Test deterministic partition manifests, ordered iteration, empty partitions,
  collisions, malformed maps, child checksum failures, interrupted reuse, and
  unchanged single-file lake behavior.
- Test repaired-population reconciliation, omitted-game preservation, 2020 and
  timing rejection, adjustment reconstruction, candidate coverage, bootstrap,
  exact output counts, no-write dry runs, and apply preflight mismatch failure.
  Include a high-partition fixture proving snapshot/history records are emitted
  rather than retained globally.
- Run focused and full warning-as-error pytest, coverage, Ruff format/lint,
  schema/contract checks, V4/boundary regressions, strict MkDocs, CLI help, and
  `git diff --check`.
- After local validation, the user creates the clean checkpoint. Run Preview
  dry run, review its preflight, then apply, independent verification, and an
  idempotent rerun. Do not mark this contract Implemented until all Preview
  gates pass, and do not begin Phase 4A here.

## Assumptions

- The shared partitioned-dataset capability is additive and must not change
  existing V4 or production consumers.
- Orphan child parts are harmless because no consumer accepts them without an
  exact final root manifest.
- The prior Phase 3 v2 mathematical contract is authoritative; this replacement
  changes materialization and verification mechanics only.
