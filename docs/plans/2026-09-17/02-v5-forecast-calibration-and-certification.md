# V5-04B: Uncertainty Calibration, Candidate Freeze, and Artifact Certification

- **Status:** Implemented
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** User approved this execution decomposition on 2026-09-17.
- **Implementation log:** `session_logs/2026-09-17/07-v5-04b-calibration-and-certification.md`.
- **Commit policy:** Separate calibration/verifier code commit and certified-evidence documentation commit; user executes Git.

## Goal

Complete Tasks 4–5 of the approved V5-04 contract after V5-04A passes and is
committed: calibrate uncertainty from nested rolling-origin residuals, freeze
the serializable forecast candidate with its fitting recipes, publish the
complete forecast tournament under a fresh immutable Preview identity,
independently reconstruct and verify the frozen design, prove exact
idempotency, and close the umbrella contract. Success produces the frozen,
uncertainty-bearing shadow candidate that Contract 05 may consume; code
completion alone is not certification.

## Current State and Entry Gate

The 04A entry gate is met. V5-04A is **Implemented** (2026-09-17): the
hardened `scripts/research/run_data_first_forecasts.py` dry run binds all
three parent URIs exactly (`parent_uris` in the forecast identity), emits
expanded `head_metrics` (pooled + by-season + by-stage MAE/CRPS with counts),
`horizon_populations`, and `selection_seasons`/`reporting_seasons` evidence,
and reports 2018/2019/2021 retained-head diagnostics excluded from every
selection gate, plan digest, and apply population. The reviewed no-write
preflight (`forecast-v1-20260917-19ca44b-04a`, cutoff `2026-09-17T14:19:09Z`,
code `19ca44b7518c05a6810b1cf82f0c1c8e8137d289`, evidence SHA
`fcdad64c…`, three byte-identical runs) selected the shared `expanding`
horizon with the alpha-10 reference head on both targets: margin MAE 14.6446
/ CRPS 10.4413, total MAE 13.5433 / CRPS 9.5469, equal 3,659-game populations
per target per horizon.

This contract is now **Approved**. An approved 04B apply must consume the same
exact 03/R6/Repair v2 parent URIs, configuration, cutoff, and run lineage
family as that reviewed preflight — but it must generate a fresh complete 04B
preflight identity of its own. Never reuse a diagnostic preflight identity
(`forecast-v1-20260917-367b4a3-04a` and `forecast-v1-20260917-820bb1d-04a`
are dead) or a failed/partial prefix.

No calibration, forecast-schema, forecast-runner, or forecast-verifier code
exists yet. The existing verifier checks nothing about forecasts; full
verifier-owned reconstruction is built here.

## Proposed Approach

Extend the runner with an evidence-bound `--apply --preflight-evidence` path
following the proven 03B pattern. Recompute the complete offsets/bridge/
horizon computation plus nested calibration once, compare every partition's
membership, row count, and canonical digest to the reviewed preflight (plus
the new calibration evidence), and write immutable children in deterministic
order. Write the candidate manifest last; its absence makes any partial prefix
permanently ineligible.

Build a verifier-owned reconstruction module that may share schema constants
and generic lake readers but must not import producer offset/head/horizon/
calibration/materializer code. It rereads exact parents, reconstructs offsets,
nested fits, predictions, bootstrap horizon selection, uncertainty, and the
serialization round trip, then publishes a signed verification record. Repeat
the exact apply must return `already_applied` without recomputation or writes.

Calibration is computed inside the existing `preflight()` function after head
evaluation and horizon selection. The preflight evidence gains a
`forecast_calibration` plan and the `"calibration": {"state":
"deferred_to_v5_04b"}` placeholder is replaced with actual records. The 04B
preflight has a different evidence shape than 04A — expected, since 04A
deferred calibration. A fresh 04B preflight identity is generated; the 04A
identity is not consumed.

## Scope

### Included

- Nested rolling-origin residual calibration with Gaussian CRPS, intervals,
  and full season/stage/FCS diagnostics.
- Frozen candidate serialization with exact replay recipes and the 2026 refit.
- Immutable partition writers, publication plan, final candidate manifest,
  independent verifier, idempotency, certification evidence, and lifecycle
  documentation.
- Negative handling for collisions, partial prefixes, mismatched preflight
  evidence, changed parents/config/code/cutoff, and verifier disagreement.

### Excluded

- Any head/horizon redesign or rerun intended to improve inspected results.
- Contract 05 readiness/prospective work, live forecasts, catalog/Neon/
  production/serving writes, markets, or promotion.
- V4 evaluation-history extension; V4 comparisons appear only where its
  predictions have verified comparable lineage, with unavailable CRPS marked
  unavailable.

## Architecture decisions

### Dataset partitioning

| Dataset | Partition keys | Type |
|---|---|---|
| `forecast_registry` | — | compact |
| `forecast_model` | `(horizon, outer_season)` | partitioned |
| `forecast_prediction` | `(season, week)` | partitioned |
| `forecast_calibration` | — | compact |
| `window_comparison` | — | compact |
| `forecast_selection` | — | compact |
| `candidate_manifest` | — | compact |

### Terminal manifest

`forecast-manifest.json` (signed, written last). Contains identity, parent
URIs + hashes, all 6 output refs (the 7th is the manifest self-ref), selected
horizon, head recipes, calibration summary, verification ref,
`production_activation_authorized: false`.

### Output root

`artifacts/research/data-first-football-v1/forecasts/runs/{run_id}/`

## Affected Components and Interfaces

- Complete `scripts/research/run_data_first_forecasts.py` apply and idempotency
  paths. Add CLI flag `--preflight-evidence <json>` for apply. The dry run
  remains the default; `--apply` requires evidence and a clean worktree.
- New verifier-owned logic in `src/cks_picks_cfb/forecast/forecast_verification.py`;
  new CLI `scripts/research/verify_data_first_forecasts.py`
  (`--manifest-uri`, `--expected-code-sha`, `--environment preview`, plus the
  three parent URIs).
- New calibration module at `src/cks_picks_cfb/forecast/calibration.py`.
- New manifest builder in `src/cks_picks_cfb/data/data_first_forecast_v1.py`.
- Use `PartitionedDatasetWriter` and existing immutable lake primitives; do not
  invent a second storage format.
- Final candidate manifest exposes exact parents, identity, seven output refs,
  preflight/selection/horizon checksums, selected horizon and head recipes,
  calibration refs, verification ref, eligibility, update recipe, and
  `production_activation_authorized: false`.

## Implementation Tasks

### Task 1 — Calibration module

**New file:** `src/cks_picks_cfb/forecast/calibration.py` (~120 lines)

```python
@dataclass(frozen=True)
class CalibrationResult:
    records: pd.DataFrame  # FORECAST_CALIBRATION_COLUMNS
    variances: dict[str, dict[int, float]]  # {target: {season: variance}}

def calibrate_uncertainty(
    features: pd.DataFrame,
    *,
    horizon: str,
    development_seasons: tuple[int, ...],
    outer_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
    residual_floor: float = 1e-6,
) -> CalibrationResult:
```

**Algorithm:** For each outer season S in `outer_seasons`:

1. `fit_seasons = fitting_seasons(S, development_seasons, horizon)` — all
   eligible earlier seasons.
2. `residual_seasons = tuple(s for s in fit_seasons if s >= 2017)` — need at
   least 2 prior fitting seasons for calibration residuals.
3. If `len(residual_seasons) < 1`: emit
   `{target, season=S, residual_count=0, variance=residual_floor,
   fallback_reason="no_prior_residuals"}`.
4. Otherwise: for each residual season R, fit the bridge on `fit_seasons` up
   to R, predict R, collect `(actual - prediction)` residuals.
5. Pool all residuals across all residual seasons for this outer season.
6. `variance = max(residual_floor, mean(residuals^2))`.
7. Emit `{target, season=S, residual_count=len(residuals), variance,
   fallback_reason=""}`.

**Key invariants:**

- Uses identical `_design`, `_fit_one`, `_target`, `select_inner_alpha` from
  `heads.py`.
- Offsets use the same `build_offsets` computation already in the feature
  frame.
- Per-target independent calibration (margin and total have separate variance
  tracks).
- No in-sample training residuals — only out-of-fold prior-season predictions.
- First eligible residual season is 2017 (after 2015, 2016 fitting seasons).

**Tests:** ~6 focused tests:

- Residual chronology (2017 earliest, no in-sample).
- Variance floor enforcement.
- Fallback when no prior residuals exist.
- Per-target independence.
- Deterministic output from identical inputs.
- Same-game/future perturbation cannot alter earlier calibration.

### Task 2 — Integrate calibration into the runner preflight

**File:** `scripts/research/run_data_first_forecasts.py`

Changes to `preflight()`:

1. Import `calibrate_uncertainty` and `FORECAST_CALIBRATION_COLUMNS`.
2. After `select_horizon()`, call `calibrate_uncertainty()` with the selected
   horizon's parameters.
3. Build `calibration_frame` from `CalibrationResult.records`.
4. Add `forecast_calibration` to the `outputs` dict with compact planning.
5. Replace `"calibration": {"state": "deferred_to_v5_04b"}` with actual
   calibration summary.
6. Add `_Progress` forced events: `calibration_started`, `calibration_complete`.

The preflight evidence shape changes:

- `calibration` key gains `{records_sha, row_count, by_target: {season:
  variance}}`.
- `preflight_plans` gains `forecast_calibration`.
- `row_counts` and `output_records_sha256` gain the calibration entry.

**Tests:** ~3 new runner tests:

- Preflight evidence includes complete calibration plan.
- Calibration variances are deterministic.
- Calibration summary matches the plan records.

### Task 3 — Apply path, evidence replay, and manifest-last publication

**File:** `scripts/research/run_data_first_forecasts.py` (~250 new lines)

**3a. Evidence replay loader** — `ForecastPreflightEvidence` dataclass +
`_load_forecast_preflight_evidence(path, identity)`:

- Validates `state == "dry_run"`, identity match, all 6 dataset plans present
  (registry, model, prediction, calibration, window_comparison, selection).
- Validates partition ordering, row counts, SHA digests for every part.
- Validates `selected_horizon`, `head_metrics` structure,
  `horizon_populations`.
- Returns typed evidence object.

**3b. Idempotency guard** — `_existing_forecast_manifest(storage,
manifest_uri, identity)`:

- Reads `forecast-manifest.json` if it exists.
- Verifies signed payload, identity match, all 6 output refs present and valid.
- Returns `already_applied` dict or raises on identity mismatch.

**3c. Partial artifact guard:**

- `storage.list_files(prefix)` — any files without valid manifest =
  permanently ineligible.

**3d. Immutable write lifecycle:**

1. Write `publication-plan.json` (identity + all plans).
2. Create `PartitionedDatasetWriter` for `forecast_model` and
   `forecast_prediction`.
3. Recompute the full pipeline (parents → offsets → features → heads →
   horizon → calibration) with a `sink` callback:
   - Partitioned datasets: `writer.add(PartitionedDatasetPart(partition,
     frame))`.
   - Compact datasets: validate row count + SHA match plan, store records.
4. Verify selection evidence matches preflight (horizon, head recipes, horizon
   SHA).
5. `writer.finish()` for partitioned datasets.
6. `build_dataset_version()` for compact datasets.
7. Write `identity.json`, per-dataset `*-ref.json` files.
8. **Write `forecast-manifest.json` LAST** (signed, with all output refs).

**3e. `main()` changes:**

- Add `--preflight-evidence` CLI flag.
- `--apply` requires `--preflight-evidence` and clean worktree.
- Dispatch to `apply()` when `--apply` is set.
- Remove the `ForecastRunError("--apply is blocked by V5-04B")` block.

**Tests:** ~8 new tests:

- Evidence replay validation (identity, plans, structure).
- Idempotency (exact identity → `already_applied`).
- Partial artifact rejection.
- Manifest-last ordering.
- Evidence mismatch rejection.
- Clean worktree requirement.
- Apply path produces all 7 datasets.
- Compact dataset SHA verification during apply.

### Task 4 — Forecast manifest builder

**File:** `src/cks_picks_cfb/data/data_first_forecast_v1.py` (~60 new lines)

```python
FORECAST_MANIFEST_SCHEMA = "data_first_forecast_manifest_v1"
FORECAST_MANIFEST_NAME = "forecast-manifest.json"

def forecast_manifest(
    *, identity, parents, output_refs, selected_horizon,
    head_recipes, calibration_summary, preflight_sha, horizon_sha
) -> dict:
```

- Uses `signed_payload` from `data_first_phase2d`.
- Contains: identity, parent URIs + raw SHA-256s, 6 output dataset refs,
  selected horizon, per-target head + alpha, calibration variance summary,
  `production_activation_authorized: false`.

### Task 5 — Independent verifier

**New file:** `src/cks_picks_cfb/forecast/forecast_verification.py` (~600-800 lines)

**Import boundary:** May import only `data_first_forecast_v1` (constants,
schemas), `lake` (generic readers), `data_first_phase2d` (signing),
`schema_contracts`, `storage`. Must NOT import `offsets`, `heads`, `horizons`,
`calibration`, or any runner code.

**Functions:**

- `verify_forecast_artifact(storage, *, manifest_uri, expected_code_sha,
  environment, rating_manifest_uri, measurement_manifest_uri,
  repair_manifest_uri, progress)` → `VerificationResult`.
- Internal: `_reconstruct_offsets()`, `_reconstruct_features()`,
  `_reconstruct_bridges()`, `_reconstruct_calibration()`,
  `_reconstruct_horizon_selection()`, `_compare_partitioned()`,
  `_compare_compact()`.
- Writes `verification/verifier-manifest.json` (signed).

**Verification steps:**

1. Load and verify the forecast manifest (signed payload check).
2. Independently load the three parents (rating, measurement, repair).
3. Reconstruct offsets from the scoring ledger.
4. Reconstruct the feature frame from team states + offsets.
5. Reconstruct every bridge fit (both horizons, all targets).
6. Reconstruct calibration from nested rolling-origin residuals.
7. Reconstruct horizon selection (paired bootstrap).
8. Compare every stored output partition-by-partition against reconstructed
   values.
9. Verify the calibration variance records match.
10. Write signed verifier manifest.

**New CLI:** `scripts/research/verify_data_first_forecasts.py` (~80 lines)

- Flags: `--manifest-uri`, `--expected-code-sha`, `--environment preview`,
  plus the three parent URIs.
- Calls `verify_forecast_artifact()`, prints JSON report.

**Tests:** ~8 focused tests:

- AST import-boundary (no producer imports).
- Bit-exact agreement on a small fixture.
- Producer perturbation detection (change an offset → verifier catches).
- Stored-bytes tamper rejection.
- Wrong parent rejection.
- Calibration variance disagreement detection.
- CLI success + CLI tamper rejection.

### Task 6 — Focused test suite expansion

**File:** `tests/test_data_first_forecasts.py` — add ~25 new tests across all
tasks above.

**File:** `tests/test_forecast_calibration.py` — new, ~8 tests for the
calibration module.

**File:** `tests/test_forecast_verification.py` — new, ~8 tests for the
verifier.

Total expected: ~55 new tests. Full suite must pass warnings-as-errors.

### Task 7 — Quality gates

Standard gate sequence:

- `uv run pytest tests/test_data_first_forecasts.py
  tests/test_forecast_calibration.py tests/test_forecast_verification.py -q -W
  error`.
- Adjacent rating/possession suites.
- Full `uv run pytest -q -W error`.
- Scoped `ruff format` + full `ruff check .`.
- `contracts/validation.py` + `make contracts-check`.
- `mkdocs build --quiet`.
- CLI `--help` and `py_compile` for new scripts.
- `git diff --check`.

### Task 8 — Certification execution sequence

After code commit:

1. Capture committed SHA, shared UTC cutoff.
2. Fresh run ID: `forecast-v1-YYYYMMDD-<shortsha>-04b`.
3. **No-write preflight** → evidence JSON (includes calibration).
4. **Evidence review**: zero warnings, all 6 dataset plans, calibration
   variances reasonable, selected horizon/head match 04A expectations.
5. **Evidence-bound apply** → all 7 datasets written, manifest last.
6. **Independent verifier** → full reconstruction, all digests match.
7. **Idempotent repeat** → `already_applied`, no writes.
8. Documentation closure: update umbrella 04 contract, roadmap, plan index,
   session log.

## Testing Strategy

- Writer tests: exact evidence reconstruction, per-part mismatch, reordered/
  missing/extra partition, checksum drift, immutable collision, partial prefix,
  manifest-last ordering, write failure, retry, and exact idempotency.
- Verifier tests: import independence, producer perturbation, future/same-game
  leakage on every path, offset/parameter/calibration disagreement,
  population/fallback/stage mismatch, tampered bytes, wrong parent/config/
  code/cutoff, and serialization round-trip fidelity.
- Integration: small complete dry-run/apply/verify/reapply fixture with all
  seven outputs, plus read-only exact-parent smoke checks before the full
  Preview run.
- Validation: focused warning-as-error tests, full warning-as-error suite and
  coverage, scoped Ruff, schema/contract checks, production-boundary
  regression, strict MkDocs, CLI help/compile, R2 prefix inventory, and
  `git diff --check`.

## Risks and Edge Cases

- Nested rolling-origin residuals multiply the already-large 04A compute;
  bound the residual history per the contract and stream by partition.
- Long computation or writes can leave immutable child objects. Manifest-last
  publication and fresh identities make these safely ineligible; never reuse
  such a prefix.
- Producer/verifier shared helpers can create false agreement. Share only
  generic serialization/schema/lake utilities, not offset, head, horizon, or
  calibration calculations.
- A valid development winner is not prospective evidence and cannot activate
  production. Contract 05 remains a separate dependency-gated task.
- If certification reveals a semantic defect, preserve the failed identity and
  return to planning. Mechanical performance/observability fixes require a new
  commit and fresh run identity.
- Runtime: Calibration adds nested rolling-origin fits. Bounded by the number
  of outer seasons × targets × residual seasons. Expect ~5-10 min total
  preflight.

## Definition of Done

- [x] Calibration module exists with full test coverage.
- [x] Preflight evidence includes calibration plans and summary.
- [x] Apply path produces all 7 datasets with manifest-last publication.
- [x] Independent verifier reconstructs the frozen design without producer imports.
- [x] Exact repeat apply is idempotent; failed/partial prefixes remain ineligible.
- [x] All quality gates pass.
- [x] Certification execution produces a verified, immutable Preview artifact.
- [x] Umbrella V5-04 and authority documentation name one frozen shadow candidate.
- [x] Required validation and full implementation/certification session logs are complete.

## Certified artifact

Run `forecast-v1-20260917-4600ddd-04b` at commit `4600dddd3e97373880d29a549f4447367940cf37`,
cutoff `2026-09-17T16:40:02Z`. Selected shared `expanding` horizon, alpha-10 reference
heads on both targets. Calibration variances: margin 361-375, total 311-326 across
2022-2025. All 6 output datasets verified; manifest at
`artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast-manifest.json`.
`production_activation_authorized: false`. This is the frozen shadow candidate for
Contract 05 prospective evaluation.

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be
logged if output order, bytes, plans, digests, identities, and acceptance
criteria are unchanged. Any change to sources, math, registry, folds, gates,
schemas, eligibility, or verification independence requires user-approved replanning.
