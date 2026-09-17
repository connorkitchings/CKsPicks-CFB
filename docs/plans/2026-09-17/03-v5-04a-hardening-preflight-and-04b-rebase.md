# V5-04A Hardening, Preview Preflight Closure, and 04B Rebase

- **Status:** In Progress
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** User approved this plan in the 2026-09-17 planning session after the static review of committed checkpoint `d380765`.
- **Implementation log:** `session_logs/2026-09-17/04-v5-04a-hardening-and-preflight.md`.
- **Commit policy:** Separate hardening code commit (user executes) before any Preview preflight identity is chosen; separate 04A closure documentation commit; separate 04B rebase documentation commit.

## Goal

Close the two static-review gaps in the committed V5-04A checkpoint (`d380765`) —
exact parent URI binding and separate 2018–2019/2021 horizon reporting — plus
the supporting evidence/observability expansions, then produce the reviewed,
deterministic, byte-equivalent, no-write Preview preflight evidence that
Contract 04A's Definition of Done requires, close 04A, and rebase Contract 04B
onto the implemented interfaces. No Preview identity is selected before the
hardening code commit exists.

## Current State

- HEAD is `d380765` ("feat(research): add V5 forecast offset and horizon
  preflight") with a clean worktree; Contract 04A
  (`docs/plans/2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md`) is
  **In Progress**; 04B is a blocked **Draft**.
- Static review gap 1: `verify_rating_parent` in
  `src/cks_picks_cfb/data/data_first_forecast_v1.py` validates only
  `measurement/repair_manifest_raw_sha256` hashes. The retained rating
  manifest's `parents` block pins exact URIs, and the 03B verifier already
  enforces URI equality
  (`src/cks_picks_cfb/ratings/possession_rating_verification.py:2137-2142`);
  the forecast runner does not.
- Static review gap 2: `evaluate_heads` computes only
  `selection.outer_seasons` (2022–2025). Contract 04A Task 3 requires 2018,
  2019, and 2021 to be reported separately without becoming the selection
  population; no such reporting exists.
- `head_metrics` evidence is pooled MAE only — no Gaussian CRPS, no
  season/completed-game-stage slices, no per-horizon population counts.
- The runner silences progress (`lambda *_a, **_k: None`) despite long parent
  loading and two-horizon evaluation; the proven bounded secret-safe stderr
  `_Progress` pattern exists in
  `scripts/research/run_data_first_possession_ratings.py:90-168`.
- Exact parents (URIs verified against docs and manifest structure):

  - Rating (03 cert):
    `artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json`
  - Measurement (R6):
    `artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json`
  - Repair v2:
    `artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`

- `.env` carries the required `CFB_STORAGE_BACKEND` and R2 (source + preview)
  credential variable names; no values are printed or logged.

## Proposed Approach

Treat the two review items as completion of existing 04A Task 3/DoD language,
not semantic amendments: exact-URI binding implements "Exact 03/R6/Repair
parents reconcile", and reported-season output implements "report 2018–2019 and
2021 separately without relabeling them as the selection period". The
head-metrics expansion and stderr progress implement the contract's
evidence/observability requirements. Selection gates, registry, folds, and
populations remain byte-identical in behavior. After gates pass and the user
commits, execute the committed no-write preflight three times under one
identity and require byte-equivalent evidence; only a fully passing review
closes 04A. 04B is then rebased in wording only and left for a fresh Terra task
with its own fresh preflight identity.

User decision (recorded): pin **all three** parent URIs — the rating
manifest's own URI becomes a required constant, and CLI R6/Repair URIs must
equal the URIs pinned inside the rating manifest.

## Scope

### Included

- Exact-URI parent binding (rating constant + pinned measurement/repair URIs)
  in forecast parent validation, identity, and evidence.
- Reported-season (2018, 2019, 2021) head evaluation per horizon with
  retained-head reporting, excluded from every selection gate and planned
  output.
- Expanded `head_metrics` (MAE + Gaussian CRPS; pooled, by-season, by-stage,
  with counts) and `horizon_populations` counts.
- Bounded secret-safe stderr progress events; stdout stays pure JSON.
- Regressions for URI substitution rejection, reporting-period exclusion from
  selection, and deterministic expanded evidence.
- Quality gates; user-executed hardening commit; three-repeat committed
  no-write Preview preflight with byte-equivalence; 04A closure documentation;
  04B contract rebase (wording only).

### Excluded

- Any change to head retention gates, horizon adoption gates, bootstrap
  procedure, alpha grid, offsets mathematics, schema versions of the seven
  forecast datasets, or selection population (2022–2025).
- Calibration, candidate freeze, immutable writes, independent verification,
  idempotent apply (all Contract 04B).
- Contract 05 work, live 2026 forecasts, markets, Neon/catalog/production
  writes, V4 evaluation-history extension.
- Reopening the 03 structural design or the committed 04A approach that
  consumes certified 03 team states.

## Affected Components and Contracts

- `src/cks_picks_cfb/data/data_first_forecast_v1.py` —
  `REQUIRED_RATING_MANIFEST_URI` constant; `verify_rating_parent` URI
  parameters and equality checks; `forecast_identity` parents payload carries
  the three URIs; `validate_config` gains reporting-season drift checks.
- `src/cks_picks_cfb/forecast/heads.py` — `evaluate_heads(
  ..., reporting_seasons=())`; `HeadComputation.reporting_predictions`.
- `scripts/research/run_data_first_forecasts.py` — URI pass-through and
  `parent_uris` evidence; expanded `head_metrics`; `horizon_populations`;
  `selection_seasons`/`reporting_seasons` keys; bounded stderr `_Progress`
  (local, mirroring the proven ratings-runner pattern) wired into
  `load_rating_inputs`, `_stream_output`, and `_stream_partitioned`.
- `conf/research/data_first_football_v1/forecast_v1.yaml` —
  `selection.reporting_seasons: [2018, 2019, 2021]`.
- `tests/test_data_first_forecasts.py` — three new regression groups.
- `docs/plans/2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md` —
  closure record (Implemented + reviewed evidence summary).
- `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` —
  Current State/Entry Gate rebase onto implemented 04A interfaces.
- `docs/plans/index.md` — lifecycle/status rows.

## Implementation Tasks

### Task 1 — Exact-URI parent binding

**Files:**

- `src/cks_picks_cfb/data/data_first_forecast_v1.py`
- `scripts/research/run_data_first_forecasts.py`

**Changes:**

- Add `REQUIRED_RATING_MANIFEST_URI` equal to the exact rating cert URI above.
- Extend `verify_rating_parent` with `rating_manifest_uri`,
  `measurement_manifest_uri`, and `repair_manifest_uri` keyword parameters.
  Enforce, before the existing hash checks: `rating_manifest_uri ==
  REQUIRED_RATING_MANIFEST_URI`; `rating["parents"]["measurement_manifest_uri"]
  == measurement_manifest_uri`; `rating["parents"]["repair_manifest_uri"] ==
  repair_manifest_uri`. Error messages must name which parent URI diverged;
  mirror the 03B verifier semantics ("stored parents differ from the requested
  URIs" style). Keep every existing check (signature, schema, frozen state,
  run id, selected candidate, raw SHA-256 equality, output roles,
  `verify_parents`).
- Extend `forecast_identity`'s `parents` payload to include the three URIs
  alongside the three raw SHAs (additive; `identity_sha256` recomputed; no
  frozen 04 identity exists yet).
- Runner: pass the CLI URIs into `verify_rating_parent` and record a
  `parent_uris` block (rating/measurement/repair) in the evidence JSON.

**Acceptance criteria:**

- A wrong measurement URI with a byte-identical manifest (hash matches) is
  rejected; likewise wrong repair or rating URIs.
- Exact URIs continue to pass with all existing checks intact.

### Task 2 — Reported horizons 2018–2019 and 2021

**Files:**

- `conf/research/data_first_football_v1/forecast_v1.yaml`
- `src/cks_picks_cfb/data/data_first_forecast_v1.py`
- `src/cks_picks_cfb/forecast/heads.py`

**Changes:**

- Config: add `selection.reporting_seasons: [2018, 2019, 2021]`.
- `validate_config`: require reporting seasons to equal exactly
  `(2018, 2019, 2021)`, be disjoint from `outer_seasons`, and be a subset of
  `development_seasons`; fail closed on drift.
- `evaluate_heads(frame, ..., reporting_seasons: tuple[int, ...] = ())`:
  additionally fit and evaluate **both** heads on each reporting season using
  the identical procedure (same `fitting_seasons` horizon policy, per-season
  inner-alpha selection, offset add-back, finite-output checks), returning the
  rows in a separate `reporting_predictions` frame on `HeadComputation`.
  Reporting rows never enter retention gates, the paired bootstrap, `models`
  retention flags, or any planned output. Raise `HeadError` on empty train or
  test for a required reporting season — no silent missing slices.
- Runner: report retained-head metrics for reporting seasons per horizon,
  labeled reporting-only; `selection_seasons: [2022, 2023, 2024, 2025]` and
  `reporting_seasons: [2018, 2019, 2021]` appear as top-level evidence keys.
- Reporting-only 2018/2019/2021 rows are retained in the preflight evidence
  but are excluded from all selection inputs, from every `preflight_plans`
  digest and row count, and from the future 04B apply evidence population;
  they never become a publication surface.

**Acceptance criteria:**

- 2018/2019/2021 results exist per horizon and target with the retained head
  and never alter `retained`, `selected_horizon`, bootstrap bounds, gate
  outcomes, plans, or row counts.
- Perturbing or removing reporting-season rows cannot change any selection
  output (regression-tested).

### Task 3 — Expanded head_metrics and horizon populations

**Files:**

- `scripts/research/run_data_first_forecasts.py`

**Changes:**

- `head_metrics[horizon][target]` becomes:
  - `head`: retained head;
  - `selection`: `pooled`, `by_season` (each outer season), `by_completed_game_stage`
    — every slice `{mae, gaussian_crps, n}` over retained-head 2022–2025 rows;
  - `reporting`: `by_season` over retained-head 2018/2019/2021 rows.
- Add `horizon_populations[horizon][target]` row counts so reviewers can
  confirm equal forecast populations across horizons (the paired bootstrap in
  `select_horizon` already enforces equality fail-closed).
- Serialization stays deterministic (insertion-ordered construction plus
  top-level `json.dumps(..., sort_keys=True)`).
- Gate math in `evaluate_heads` and `select_horizon` is untouched.

**Acceptance criteria:**

- Every outer season × target × horizon appears in `by_season`; all three
  reporting seasons appear; stage slices are non-empty where rows exist.
- Evidence composed twice from identical inputs is byte-identical.

### Task 4 — Bounded stderr progress

**Files:**

- `scripts/research/run_data_first_forecasts.py`

**Changes:**

- Add a local `_Progress` class mirroring the proven ratings-runner pattern
  (`scripts/research/run_data_first_possession_ratings.py:90-168`): thread
  heartbeat, ~30 s interval cap, secret-safe field filtering (credential/
  password/secret/token/access_key), forced emission for phase starts,
  JSON lines to stderr only.
- Wire it into `load_rating_inputs`, `_stream_output`, and
  `_stream_partitioned` (replacing both `lambda *_a, **_k: None` sinks).
- Phase events: `preflight_started`, `parents_loaded`, per-source
  `source_streamed` (population, outcomes, terminal, snapshots,
  scoring_events, team_states), `offsets_built`, `horizon_started`/
  `horizon_complete` (per horizon), `horizon_selected`,
  `evidence_constructed`, `dry_run_complete`.
- Stdout remains pure JSON evidence.

**Acceptance criteria:**

- Long phases emit heartbeats without polluting stdout or leaking secrets;
  no behavior change beyond logging.

### Task 5 — Regressions

**Files:**

- `tests/test_data_first_forecasts.py`

**Changes:**

- URI substitution rejection: build a signed rating-manifest fixture (use
  `signed_payload` from `data_first_phase2d`, mirroring existing fixtures)
  whose `parents` pin the exact URIs + hashes; assert `verify_rating_parent`
  rejects (a) wrong measurement URI with matching hash, (b) wrong repair URI,
  (c) wrong rating URI constant; assert exact URIs pass.
- Reporting-period exclusion from selection: construct frames where 2018/2019/
  2021 rows would flip head retention or horizon adoption if (incorrectly)
  included; assert gate outputs are unchanged and reporting rows are absent
  from `forecast_prediction` plans/row counts, appearing only under
  `head_metrics[...].reporting`.
- Deterministic expanded evidence: compose the evidence document twice from
  identical inputs and assert byte-equal `json.dumps(..., sort_keys=True)`;
  assert slice completeness (all outer seasons both targets both horizons;
  all three reporting seasons).
- Reporting population mismatch: corrupt or truncate a required
  reporting-season population (for example, drop all 2019 rows from the
  evaluation frame) and assert the run fails reporting loudly rather than
  silently proceeding with an altered 2022–2025 selection population or
  changed gate outputs.

**Acceptance criteria:**

- All three regression groups pass under warnings-as-errors.

### Task 6 — Gates and hardening commit

**Validation:**

- `uv run pytest tests/test_data_first_forecasts.py -q -W error` plus adjacent
  rating/forecast suites.
- Full `uv run pytest -q` suite.
- Scoped `uv run ruff format` on the changed files only — a repository-wide
  formatter conflicts with the project's dirty-worktree guardrail — plus full
  `uv run ruff check .`.
- `uv run python contracts/validation.py`; `make contracts-check`.
- `uv run mkdocs build --quiet` (strict — treat warnings as failures).
- CLI `--help` and compile checks; `git diff --check`.

Then the user executes the hardening commit (proposed message:
`feat(research): harden V5-04A parent binding and reporting evidence`). No
Preview identity is chosen before this commit.

### Task 7 — Committed no-write preflight, three repeats

**Changes:**

- Capture the committed full SHA (`git rev-parse HEAD`), one shared UTC cutoff
  (`YYYY-MM-DDTHH:MM:SSZ`), and run ID `forecast-v1-20260917-<shortsha>-04a`
  (adjust the date if executed later).
- Create a fresh evidence directory with `EVIDENCE_DIR="$(mktemp -d)"` and
  execute three identical invocations, writing stdout to
  `"$EVIDENCE_DIR"/forecast-v1-20260917-<shortsha>-04a-run<N>.json`:

  ```bash
  EVIDENCE_DIR="$(mktemp -d)"
  PYTHONPATH=.:src uv run python scripts/research/run_data_first_forecasts.py \
    --run-id forecast-v1-20260917-<shortsha>-04a \
    --expected-code-sha <full committed SHA> \
    --environment preview \
    --as-of <captured UTC cutoff> \
    --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json \
    --measurement-manifest-uri artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json \
    --repair-manifest-uri artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json \
    > "$EVIDENCE_DIR"/forecast-v1-20260917-<shortsha>-04a-run1.json
  ```

  (Redirect stderr separately only if heartbeat noise must be suppressed in
  captured logs; otherwise observe stderr live for liveness. Record the
  resolved `EVIDENCE_DIR` path in the implementation log.)
- Require byte-equivalence across all three runs (`cmp` or `shasum`):
  identity (including `parent_uris` and parent hashes), `offsets_sha256`,
  `head_metrics`, `selected_horizon`, `horizon_sha256`, `preflight_plans`,
  `row_counts`, `output_records_sha256`.
- Zero writes: dry run only; `--apply` stays fail-closed; no R2, Neon,
  catalog, V4, or production mutations; no `./data/`.

**Acceptance criteria:**

- Three byte-identical evidence files under one frozen identity/cutoff/SHA.

### Task 8 — Review, close 04A, rebase 04B

**Changes:**

- Review checklist (all must pass): equal per-horizon forecast populations;
  valid head gates with audited `inner_fallback`/`fallback_reason`; one shared
  selected horizon across both targets; complete required slices (2022–2025
  by-season for both targets/horizons; 2018/2019/2021 reporting present);
  zero warnings in all three runs.
- Any mismatch, warning, failed gate, or parent drift is a failed diagnostic
  identity: repair, new commit, fresh identity — never reuse or extend it.
- On pass — and only after all three reviewed preflights pass — set Contract
  04A status to **Implemented** with the reviewed evidence summary (run id,
  cutoff, code SHA, selected horizon, head recipes, key digests); mark this
  contract **Implemented** only after the closure documentation is committed.
  Both transitions gate on two conditions together: three passing reviewed
  preflights and the committed closure documentation. Also update
  `docs/plans/index.md`, note closure in the umbrella V5-04 contract, and
  write the implementation session log. User commits
  (`docs(v5): close V5-04A with reviewed preflight evidence`). None of these
  transitions approves 04B or implies its approval.
- Rebase 04B wording only, landing it as **Draft**: Current State/Entry Gate
  references the implemented 04A interfaces (`parent_uris`, expanded
  `head_metrics`, `reporting_seasons`, progress events) and the reviewed
  evidence identity. Tasks 4–5, scope, verifier independence, manifest-last
  ordering, and idempotency stay intact. User commits
  (`docs(v5): rebase V5-04B on implemented 04A evidence`). Moving 04B from
  Draft to **Approved** requires a separate, explicit user approval of the
  rebased draft after review; this contract never approves 04B automatically.
- 04B implementation happens in a fresh Terra task via `implement-plan` at the
  04B path only after that explicit approval; it generates a fresh complete
  04B preflight identity and never reuses the `forecast-v1-…-04a` diagnostic
  identity.

**Acceptance criteria:**

- 04A and this contract are Implemented only after three passing reviewed
  preflights and committed closure documentation (user-executed commits).
- 04B is rebased (wording only) and remains **Draft** with scope intact;
  its approval is a separate explicit user action outside this contract.

## Testing Strategy

- Unit/regression: the three Task 5 groups, run warnings-as-errors.
- Determinism: byte-equality of composed evidence (Task 5) and of the three
  Preview preflight runs (Task 7).
- Full warning-as-error suite plus the standard quality gates (Task 6).
- No integration writes: the preflight is read-only by construction and
  `--apply` is asserted blocked.

## Risks and Edge Cases

- Runtime: R6 streaming plus two horizons is the costliest program
  computation; the heartbeat is the liveness signal, repeats run sequentially,
  and an interrupted/expired run is simply re-run under the same identity (no
  writes exist).
- Byte-equivalence requires the same environment/packages across repeats
  within this session; do not upgrade dependencies between runs.
- Float serialization is stable only within the same interpreter/stack — all
  three repeats must execute in the same session/machine state.
- Reporting seasons must fail closed when slices are missing; never silently
  drop a required season.
- The `forecast_identity` payload change alters `identity_sha256` — expected
  and safe because no 04 identity was frozen; 04B consumes only the new shape.
- Week 3 production freeze (kickoff 2026-09-17 23:30Z) is outside this
  contract; confirm it is handled by the normal weekly runbook so the long
  preflight does not collide with production operations.

## Definition of Done

- [ ] Exact-URI binding rejects substitutions and passes exact parents.
- [ ] 2018/2019/2021 reported per horizon/target without touching selection.
- [ ] Expanded `head_metrics` and `horizon_populations` are complete and deterministic.
- [ ] Bounded stderr progress exists; stdout evidence stays pure.
- [ ] All Task 6 gates pass; user commits the hardening checkpoint.
- [ ] Three byte-equivalent committed-SHA preflight runs pass review.
- [ ] 04A and this contract are Implemented only after the preflights pass and closure docs are committed.
- [ ] 04B is rebased (wording only) as **Draft**; moving it to Approved requires a separate explicit user approval; implementation deferred to a fresh task.

## Amendments

### Amendment 1 — Completed-game counts come from `possession_rating_state`

**Reason:** The first committed no-write preflight (run 1 of
`forecast-v1-20260917-367b4a3-04a`, commit `367b4a3`) failed at feature
assembly: `_feature_frame` renamed a `completed_games` column that does not
exist in the 03 `possession_team_state` contract. The committed 04A path had
never executed end-to-end; this is exactly the defect class the preflight
exists to expose.

**Original approach:** Source home/away completed-game counts by renaming
`completed_games` from the streamed `possession_team_state` frame.

**Revised approach:** Also stream the 03 `possession_rating_state` output
(`RATING_STATE_COLUMNS`), take the retained candidate's `unit_role ==
"offense"` rows as the per-team-game `completed_games` source, and fail closed
if counts are not unique per (season, game_id, team). `_stream_partitioned`
gains a `columns` parameter. Two new regressions cover the sourcing and the
duplicate rejection; the previously untested `_feature_frame` path now has
direct unit coverage.

**Impact:** Mechanical repair only — no change to parents, mathematics,
gates, registry, folds, selection/reporting populations, schemas, or evidence
shape. The failed run 1 is a dead diagnostic identity under commit `367b4a3`;
after the repair commit, the preflight repeats under a fresh run ID derived
from the new commit's short SHA.

### Amendment 2 — Regime stage comes from the schedule, not rating states

**Reason:** Evidence review of the three byte-identical runs under
`forecast-v1-20260917-820bb1d-04a` (commit `820bb1d`) found
`by_completed_game_stage` collapsed to `{0, 1}`. Direct parent inspection
(17,870 retained-candidate offense rows) shows the counter is ~96% zeros with
maximum 3: `possession_rating_state.completed_games` counts assimilated
usable observations whose `boundary_cutoff` has passed — an exposure
credibility counter, not the program's completed-game regime (0/1/2/3/4+).
Stage slices 2–4 were therefore silently absent, so the evidence fails the
review gate ("no missing required slices") and the identity is dead.

**Original approach (Amendment 1):** Source `completed_games` from the
retained candidate's `possession_rating_state` offense rows.

**Revised approach:** Compute pregame per-team counts of earlier
forecast-eligible completed games within the season, ordered by
`(kickoff_utc, game_id)`, directly from the assembled `games` frame in
`_feature_frame` (self-excluded, strictly earlier). Drop the
`rating_states` stream entirely. `completed_game_stage =
min(home, away).clip(0..4)` then carries the regime meaning the stage
regression gates and reporting slices require. Regressions cover kickoff
ordering, pregame self-exclusion, and the stage-4 clip.

**Impact:** Selection/reporting populations, row counts, parents, gates math,
registry, and folds are unchanged; `completed_game_stage` values (and hence
per-stage gate partitions, `by_completed_game_stage` slices, and the
`forecast_prediction` record digests that include the column) change to the
correct semantics. Both `forecast-v1-20260917-367b4a3-04a` and
`forecast-v1-20260917-820bb1d-04a` are dead diagnostic identities; the
preflight repeats under a fresh run ID after a new commit.
