# V5-11C: Forecast Bridge Rebuild and Through-2025 Final Fit

- **Status:** Implemented
- **Created:** 2026-09-21
- **Planner:** Sol
- **Approval source:** User authorized the full Contract 11 decomposition on 2026-09-21 ("Let's do it all"); final-fit design (same run, recipe refit, alpha policy, 2025 calibration carry-forward) confirmed by structured decision the same day.
- **Implementation log:** `session_logs/2026-09-21/08-v5-11c-forecast-bridge-and-final-fit.md`
- **Commit policy:** Separate commits — schema/pin checkpoint, then evidence checkpoints per phase. User controls Git operations.

## Goal

Rebuild the forecast bridge from the 11B r9-derived rating parent and add the
through-2025 final fit, closing Finding 004. Success is a new forecast run
whose `forecast_model` registry shows `training_max >= 2025` on a targeted
re-run of `corpus.forecast.final_fit_existence`, with all validation-season
selections recomputed (not carried) from the new parents. This artifact becomes
the 11D verification target.

## Current State

- Existing artifact `forecast-v1-20260917-4600ddd-04b` descends from R6/r6-rated
  parents and caps training at 2024 (`max_training_season=2024`, Finding 004).
- Runner `scripts/research/run_data_first_forecasts.py` fully recomputes
  offsets → both horizons' heads → horizon selection → calibration from raw
  parents on every preflight/apply; 04A selections are recorded but never
  consumed as inputs — so a new parent re-fits everything automatically.
- Parent binding is fail-closed pins in
  `src/cks_picks_cfb/data/data_first_forecast_v1.py:26-31`
  (`REQUIRED_RATING_RUN_ID`/`REQUIRED_RATING_MANIFEST_URI`/`REQUIRED_RATING_CANDIDATE`)
  and `src/cks_picks_cfb/forecast/forecast_verification.py:1131,1139`,
  plus the ratings-layer pins (updated by 11B — this contract's entry gate).
- No final-fit code path exists anywhere: every fit trains strictly before its
  test season and the last outer season is 2025.

## Proposed Approach

Re-pin the forecast layer to 11B's retained rating identity (run-id, URI, and
candidate — whatever 11B selected), implement the approved final-fit design as
a schema extension of the same run (mirroring V4's "unchanged design refit"
pattern), then execute preflight → apply under a fresh run identity. Horizon,
offset, and head selections re-run from the new parents; no outcome is
pre-declared.

## Scope

### Included

- Pin re-binding to the 11B rating manifest (identity resolved from 11B's
  published run, never hand-typed).
- Final-fit implementation: `final` rows in `forecast_model` (trained on all
  development seasons 2015–2019 and 2021–2025, no test season, reporting
  seasons included) and `forecast_calibration` (the design's 2025
  rolling-origin variance carried forward); schema, config, and frame
  validation extended; no predictions emitted for the final fit.
- Alpha policy: reference head → fixed 10.0; challenger head → re-run
  inner-alpha selection on the full development window.
- Fresh run `forecast-v1-20260921-<shortsha>-11c`; targeted
  `final_fit_existence` re-run against the new artifact.
- Pinned-test updates (`tests/test_data_first_forecasts.py:44,277` and
  fixtures binding the old rating/forecast identities).

### Excluded

- Methodology, gates, horizon registry, or alpha-grid changes.
- 11D verification work (11D re-points and extends the verifier).
- Any edit to 11A/12A/10B/04A/04B evidence or frozen pins; in-sample
  final-fit calibration (rejected as biased).

## Affected Components and Contracts

- `src/cks_picks_cfb/data/data_first_forecast_v1.py` (rating pins; final-fit
  schema/config support).
- `src/cks_picks_cfb/forecast/` producer modules (final-fit fit path only).
- `scripts/research/run_data_first_forecasts.py` (final-fit plan steps).
- New Preview R2 run prefix under
  `artifacts/research/data-first-football-v1/forecasts/runs/`.
- Feeds 11D; resolves the 04/04B full-lane blocker via the decomposition.

## Implementation Tasks

### Task 1 — Parent re-pinning and final-fit implementation

**Files:**

- `src/cks_picks_cfb/data/data_first_forecast_v1.py`
- `src/cks_picks_cfb/forecast/*.py` (heads/calibration/schema as needed)
- `scripts/research/run_data_first_forecasts.py`
- `conf/research/data_first_football_v1/forecast_v1.yaml` (if final-fit needs
  declared support)

**Changes:**

- Bind the 11B rating run-id/URI/candidate exactly; reject all older rating
  identities fail-closed.
- Add the final-fit path: after horizon selection, fit the selected head's
  recipe on all development seasons; emit one `final` model row per target
  (`training_max = 2025`, recipe/alpha recorded) and one `final` calibration
  row per target (2025 rolling-origin variance, source recorded). Extend
  frame/schema validators for the new rows; fail closed on any in-sample
  calibration attempt.

**Acceptance criteria:**

- Preflight computes the final rows deterministically; preflight rejects the
  old rating parent and any r6 measurement lineage.

**Validation:**

- Unit tests for the final-fit fit path (recipe reuse, alpha policy, training
  window contents, calibration source); negative tests for stale parents.

### Task 2 — Forecast run: preflight and apply

**Files:**

- `scripts/research/run_data_first_forecasts.py`

**Changes:**

- Execute preflight → evidence-bound apply in Preview; record the selected
  horizon, heads, populations, and final-fit rows. ~8–10 min preflight scale
  expected; longer apply accepted with heartbeat review.

**Acceptance criteria:**

- Byte-identical evidence between preflight and apply; six output datasets
  plus final rows published; population 8,936/8,935 holds; partial prefixes
  never reused.

**Validation:**

- Full focused forecast suites; ruff; `git diff --check`.

### Task 3 — Targeted Finding-004 evidence

**Files:**

- `src/cks_picks_cfb/audit/corpus_ratings.py` (read-only check reuse)

**Changes:**

- Re-run `corpus.forecast.final_fit_existence` against the new artifact and
  record `training_max >= 2025` with the check output. No harness edits, no
  new audit publication.

**Acceptance criteria:**

- The check passes on the new artifact; output recorded in the session log.

**Validation:**

- Check output reviewed against the new `forecast_model` registry bytes.

## Testing Strategy

- Unit: final-fit math (window contents, alpha policy, calibration provenance),
  pin accept/reject matrix, schema validation of new rows.
- Integration: end-to-end Preview cycle (preflight/apply/repeat semantics).
- Regression: existing forecast suites pass apart from intentional pin updates.

## Risks and Edge Cases

- **Selection flip:** horizon/head/calibration may differ from 04B; record,
  never tune; adjacent consumers (`REQUIRED_FORECAST_HORIZON` etc.) update
  only under their own contracts later.
- **Final-fit scope creep:** the final fit is a model row, not predictions —
  any emission of final-fit "predictions" against historical seasons is out
  of scope and must fail review.
- **Pin-chain depth:** 11B must be Implemented first; verify the ratings-layer
  pins accept r9 before touching forecast pins.

## Definition of Done

- [x] 11B is Implemented and its retained identity is the only accepted parent.
- [x] Final-fit rows publish with `training_max = 2025` per target.
- [x] `final_fit_existence` passes on the new artifact (targeted re-run).
- [x] Tests, ruff, contracts validation, strict MkDocs, `git diff --check` pass.
- [x] This contract and `docs/plans/index.md` updated to `Implemented`.

## Amendments

### Amendment 1 — `model_registry` earlier-only carve-out for final-fit rows (2026-09-21)

**Reason:** The preflight Halo revealed that `check_forecast_model`'s earlier-only
rule (`max_training_year >= outer_season` → fail) flags the new final-fit rows,
whose training window (through 2025) necessarily covers their sentinel season
(`outer_season == 0`). Final-fit rows have no validation season by design, so
the rule — written before final fits existed — misfires on them while
`final_fit_existence` correctly passes.

**Original approach:** No harness edits; targeted check re-run only.

**Revised approach:** Minimal carve-out in `check_forecast_model`: the
`bad_fit` computation excludes `outer_season == FINAL_FIT_SEASON` rows
(imported from `forecast.heads`, single source of truth);
`training_max` still counts all rows. `check_calibration` needs no change
(carried variances/counts already satisfy it). Covered by two new unit tests:
final rows pass both checks; a validation row training on its own outer
season still fails. Old artifacts contain no sentinel rows and behave
identically.

**Impact:** No architecture, scope, or acceptance change. The preflight
evidence predating this amendment is superseded; preflight re-runs under the
amended code SHA with a fresh run-id before apply.

A flipped selection that breaks an adjacent consumer, or a population
deviation, returns to Sol — the design is frozen.
