# Ratings Research Platform: V6 Development and Historical Evaluation

- **Status:** In Progress
- **Created:** 2026-09-28
- **Planner:** Sol
- **Approval source:** User accepted the proposed architecture and instructed implementation in this conversation.
- **Implementation log:** `session_logs/2026-09-28/02-v6-ratings-platform.md`
- **Commit policy:** Separate planning commit recommended; Git operations remain user-controlled.

## Goal

Build a reusable research platform for versioned rating data, alternative rating designs, historical replay, and reproducible comparison. A developer must be able to add a rating design without changing V5 or rewriting the replay/evaluation engine. No candidate is promoted by this contract.

## Current state and boundaries

The accepted V5 corpus uses Repair v2, measurement `possession-v1-measurements-20260921-r9`, ratings `possession-v1-ratings-20260921-11d59ee-r9cert`, forecast `forecast-v1-20260921-5afd577-11c`, and independent 11D verification. V5 runners seal their own candidates and source versions; they are not a general research interface. R2 is the immutable data authority. Preview and production currently share R2 storage, so a prefix in the same bucket is insufficient physical isolation. The existing worktree contains uncommitted September 28 audit documentation; preserve it.

## Chosen architecture

Use a distinct, private R2 research bucket (default `cks-picks-cfb-research`) with bucket-scoped credentials. Source access is read-only; research output access is limited to the new bucket. Use explicit `CFB_R2_LAB_SOURCE_*` and `CFB_R2_LAB_*` settings, no production/Preview fallback, no Neon or website integration. Fixture implementation may proceed before bucket provisioning, but real-data completion cannot.

New reusable code lives under `src/cks_picks_cfb/ratings_lab/`, commands under `scripts/research/`, configuration under `conf/research/ratings_lab_v1/`, and immutable research objects under `ratings-lab/v1/` in the dedicated bucket. Existing V5 runners, artifacts, configs, and weekly behavior are unchanged. Reuse stable storage readers and pure helpers without widening sealed V5 contracts.

Research contracts distinguish (1) source/corpus manifests, (2) measurement recipes, (3) individual team-game observations, (4) cumulative measurements with contributor identity, (5) pregame rating states and explanations, (6) forecast predictions, and (7) evaluation reports. Store source bucket identity, URI, SHA-256, schema, counts, code/config/lock hashes, timing class and parent identities. Expose missing evidence and full schedule denominators. Historical reconstructed availability is not represented as an actual pre-kickoff capture.

Rating implementations register a versioned measurement, prior, update method, and state meaning. The replay engine owns admissible cutoffs and supports separate incremental-event and cumulative-recomputation modes. The former consumes each eligible observation once; the latter rebuilds from a complete evidence set and must never add cumulative exposure repeatedly. Every state retains provenance and an explanation of its evidence. Exact prior/evidence shares are required for linear methods only.

The historical protocol uses 2015–2019 and 2021–2025, excluding 2020; rolling-origin headline seasons 2022–2025, with 2018/2019/2021 reported separately. All transformations, priors, bridge fitting, and calibration use earlier data only. Use the accepted earlier-week plus kickoff-six-hour reconstructed information policy initially; a different policy gets a new protocol identity. Keep the 2019→2021 calendar gap. The complete eligible schedule is the comparison denominator; missing predictions cannot silently improve a candidate score.

Maintain two benchmarks: import frozen accepted V5 predictions and independently recompute their scores; and refit a common alpha-10 Ridge bridge separately on V5 states and each research candidate under identical folds, features, offsets, and earlier-only calibration. Never apply fixed V5 coefficients to an arbitrarily scaled V6 rating. Report margin/total MAE, RMSE, bias, CRPS, interval coverage/width, paired season/week bootstrap differences (2,000 replicates, seed 20260928, 90% interval), seasons and completed-game stages 0/1/2/3/4+. 2026 observed results may enter a separately labeled diagnostic replay but never historical fitting or selection. Prospective evidence and production promotion are separate contracts.

The CLI supports `validate`, `import-corpus`, `build-measurements`, `replay`, `evaluate`, `compare`, `explain`, and `status`. Mutating commands default to dry run and require explicit apply. Resume preserves deterministic identities and verifies prior outputs; changed inputs require a new identity. The first real reference estimator is carryover-only with fixed rho 0.60 and no in-season mean update; synthetic estimators prove both update modes. A possession-update correction is out of scope.

## Ordered implementation tasks

### 1. Storage and artifact foundation

Implement explicit research source/destination clients, destination identity checks, content-addressed Parquet/JSON artifacts, create-once manifest publication, stage receipts, checksum verification, and bounded partitions. Reject shared source/destination identities, credentials missing for cloud apply, conflicting collisions, and incomplete runs. Fixture tests cover concurrency/conflict/idempotence. No laboratory imports from production commands.

### 2. Corpus and measurement contracts

Pin exact accepted V5 parents and verification receipts. Import schedule/outcome and validated game-level measurements from signed/checked immutable refs, with full-population coverage, timing, source semantics, and missing-data reasons. Preserve lower-level references for new recipes. Keep individual game observations separate from cumulative snapshots. A corpus can be rebuilt with the same logical identity and no ambiguous latest-source selection.

### 3. Rating engine and reference candidates

Implement registry, chronological replay, incremental and cumulative update modes, state/uncertainty outputs, and team explanations. Add immutable V5 benchmark adapter and carryover-only reference. Synthetic estimator registration must require no replay-engine edit. Test equal kickoffs, byes, delayed evidence, missing priors, FCS opponents, postponed games, 2019→2021 gap, and 2020 rejection.

### 4. Historical forecast and comparison

Implement common bridge, earlier-only calibration, full-population validation, saved predictions, independent metric calculation, paired bootstrap and comparison reports. Prove no validation-season data fits a candidate and detect mismatched populations. The accepted V5 import must reproduce 7,318 rows/3,659 games across 2022–2025, with approximately 14.160 margin and 13.356 total MAE in 2025.

### 5. Real-data acceptance and documentation

Provision/verify research bucket and scoped credentials. Complete one pinned historical corpus, V5 import, V5 common-protocol comparison, carryover reference, team explanation, deterministic rerun and resume. Record runtime and storage. Document extension example and operator commands. Keep the contract In Progress if credentials, parents, or real-data verification remain unavailable.

## Validation and definition of done

- Focused new tests for isolation, immutable writes, corruption, chronology, evidence semantics, explanations, coverage, fitting windows, and comparisons.
- Existing storage, repository-boundary, V5 ratings/serving/weekly-cycle regressions and CI gates pass; scoped Ruff, docs build, `git diff --check` pass.
- Frozen V5 import reproduces accepted prediction population and metrics; common-protocol runs complete on the same game keys; deterministic rerun preserves logical hashes.
- No V5 artifact, production database, public selection or deployment changed. Documentation and implementation log are complete.
- Mark `Implemented` only after real-data cloud acceptance; local fixtures alone are insufficient.

## Implementation progress (2026-09-28)

Tasks 1–4 are implemented in `src/cks_picks_cfb/ratings_lab/`, `scripts/research/ratings_lab.py`, and `conf/research/ratings_lab_v1/protocol.yaml`. The isolated store, signed-parent corpus import, versioned game and cumulative measurement contracts, two-mode replay, carryover reference, frozen V5 benchmark, common Ridge bridge, earlier-only calibration, early diagnostic seasons, paired bootstrap, CLI stages, tests, and operator documentation are present.

A local-output end-to-end run read the actual accepted V5 parents through a read-only adapter: 8,936 population games, 8,935 eligible feature games, 35,744 individual PPP observations, 35,535 cumulative snapshots, 35,740 pregame states, and 7,318 predictions each for frozen V5, common-bridge V5, and the carryover reference. The immutable local corpus rerun reproduced the same manifest. Independently recomputed frozen V5 2025 MAE was 14.1596 margin and 13.3558 total. The carryover-only common-bridge result trailed common-bridge V5 by 0.597 margin and 0.051 total MAE. Early 2018/2019/2021 diagnostic output had 5,318 rows and remained separate from the headline comparison.

Task 5 remains open: `CFB_R2_LAB_SOURCE_*` and `CFB_R2_LAB_*` credentials and a separate research bucket are not present in this environment. Provision the bucket with scoped credentials, then run the documented `validate → import-corpus → build-measurements → replay → evaluate → compare → explain → status` sequence with `--apply`. Record manifest keys, checksums, runtime, storage size, and deterministic cloud rerun before changing status to `Implemented`. No production or V5 artifact was modified.

## Risks and amendment rule

Dedicated bucket and credentials may be unavailable at first implementation. The platform can be built and verified locally, but the contract remains In Progress. Existing cumulative adjusted snapshots can be imported as labeled data but may not be treated as independent single-game measurements. Historical data timing is reconstructed. A material change to storage isolation, corpus eligibility, evaluation folds, estimator semantics or production boundaries requires a new approved amendment.
