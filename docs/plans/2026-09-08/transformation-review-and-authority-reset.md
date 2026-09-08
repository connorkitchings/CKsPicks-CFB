# Pre–Phase 5 Review and Authority Reset

- **Status:** Implemented
- **Created:** 2026-09-08
- **Planner:** Astra, explicitly requested by the user
- **Approval source:** User approved the complete replacement plan with “PLEASE IMPLEMENT THIS PLAN” on 2026-09-08. This session is authorized for contracts and documentation only.
- **Implementation log:** `session_logs/2026-09-08/07-transformation-review-and-contract-reset.md`
- **Commit policy:** Separate documentation/plan commit; user executes Git operations.

## Goal and execution boundary

Keep an interpretable, uncertainty-bearing team rating as the mandatory foundation
for forecasts. Restore research on learned preseason priors, add one bounded
Kalman challenger, and compare rating-based Ridge and NB2 forecasts. Direct-core
models and polls are diagnostic benchmarks only.

This contract implements the review record, six replacement contracts, and active
documentation corrections. It does **not** execute repairs, acquire data, train,
rebuild phases, publish artifacts, modify production, or alter existing weekly
operations changes. Each subsequent contract requires its own implementation task.

## Review evidence and dispositions

The review inspected original/resequenced plans, recent session logs and commits,
measurement/rating/context code and verifiers, and exact sealed Preview R2
manifests, attribution tables, auxiliary datasets, and schedule/observation keys.
Read-only in-memory reproductions established same-game feature dependence and
coaching-history sensitivity to future rows. This is a targeted review, not a
fresh exhaustive certification of every predecessor artifact.

All abbreviated artifact paths below are relative to
`artifacts/research/data-first-football-v1/` in Preview R2. Checksums are integrity
checks, not cryptographic attestations of modeling validity.

| Evidence | Verified finding | Current disposition |
| --- | --- | --- |
| Phase 0 alignment and corrected Phase 1 audit v3 | Existing boundary and historical-result dispositions remain in force | Retain; no claim of a new full compatibility audit |
| Phase 2c/d schedule versus Phase 3 observations | 8,936 schedule keys; 8,903 observation keys; 33 omitted, including 32 marked completed and one incomplete App State–Liberty game (`401640992`) | Reconcile individually; completed forecast population must not depend on measurement success |
| Phase 3 `phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json` | EPA-only pooled margin/total MAE 13.702131853 on 6,314 validation games; `without_points_per_scoring_opportunity` improved 0.6535%, split-EPA quality core 0.5123%, but both 90% intervals included zero | Historical reduced-population comparison; repeat original bounded registry after repair |
| Phase 4A `phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json` | `rho_0_60__exposure` pooled MAE 13.682341353; all seven alternatives worse | Useful historical reference; descendants require repaired population and renewed selection |
| Phase 4B `phase4b/runs/phase4b-v1-20260908T1600Z/retained-baseline-manifest.json` | Margin baseline 13.9491303898, field position 12.3647506432 (11.3583% apparent gain), turnovers 12.5122766247; total retained no context at 13.4155523161 | Same-game field-position/drive-length/turnover inputs invalidate pregame comparisons. Entire retained manifest is prohibited as a new forecasting parent; unaffected rows remain diagnostic pending recertification |
| Phase 2e coaching | 1,310 rows; every nonmissing tenure/new value is 1; 9.3% missing | Semantically defective, not evidence that coaching has no value |
| Phase 2e roster continuity | Prior player membership is tested across all teams; 19.7% feature missingness | Same-team continuity is not established; repair and distinguish incoming experience |
| Phase 2e recruiting | Four-class average/trend missing for about 30.5%; current class about 0.1% missing | Incomplete-window limitation, including the 2020 exclusion; retain explicit coverage, revise representations |
| Phase 2e returning production | About 0.9% missing in inspected fields | Available reconstructed evidence; meaning/timing must still pass recertification |
| Original versus resequenced Phase 4 | Original learned context prior removed; auxiliary families tested only after freezing ratings | Restore bounded learned priors; existing context-head outcomes do not test prior usefulness |

The 6,314 validation games are unique games, not 113,652 Phase 4B candidate/target
prediction rows. Pooled Phase 3/4A MAE combines margin and total; it is not a
single-target score. Acquisition, semantic admission, and predictive usefulness
are separate milestones. No historical result through 2025 is untouched evidence.

| Manifest | Raw-object SHA-256 | Canonical manifest checksum (`manifest_sha256`) |
| --- | --- | --- |
| Phase 3 above | `c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234` | `25219c6f5cce932531a1f4f3eed7f17c1842c1966444f4e7956d342ae03cbf44` |
| Phase 4A above | `235ea0ce0cace3a65209ffe9d4fb9dfe9d74208d4b2269967021f5b50c509a6b` | `af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612` |
| Phase 4B above | `3f9829aa6119daf5e09d1eecae7b1ab2f6cb929f95563161d72661f2de18deab` | `dee8a668115af4f426d6080d8b139575ba35859fea9e7212cfd613b364779b4a` |

Sealed code bindings are respectively `6addf437e7d76f5e39f198c41acd47c4e9b2c5b4`,
`3547844111c90f71c85760cbf841ae11787591a8`, and
`f611575d195780b678eab12322fe5fde6b1e8ea7`. Later source corrections do not
retroactively change the computations bound into these artifacts.

## Approved replacement sequence

1. [Repair and recertification v2](data-first-repair-and-recertification-v2.md).
2. [Phase 3 measurement/core selection v2](phase3-measurement-and-core-selection-v2.md).
3. [Phase 4A prior/dynamic rating selection v2](phase4a-prior-and-dynamic-rating-selection-v2.md).
4. [Phase 4B pregame context selection v2](phase4b-pregame-context-selection-v2.md).
5. [Phase 5 rating-based forecast selection v2](phase5-rating-based-forecast-selection-v2.md).
6. [Phase 6 prospective evidence v2](phase6-prospective-evidence-v2.md).

Phase 7 is a future, separate promotion contract only if prospective evidence
supports review. Approving these documents does not execute any phase.

## Binding common execution contract

Each linked contract incorporates this section. Reusable research logic belongs
under `src/cks_picks_cfb/`, research entry points under `scripts/research/`, and
configuration under `conf/research/data_first_football_v1/`. Version corrected
code paths when shared changes could affect V4. Never create repository `./data/`.

- Use development outcome seasons 2015–2019 and 2021–2025; reject 2020 in every
  input, label, state, and fold. Already allowed earlier recruiting metadata and
  explicitly named predecessor metadata are auxiliary-only, never extra outcome folds.
- Outer validation seasons: 2018, 2019, 2021–2025. A feature for season S may
  only use information effective before its cutoff; seasonal learned parameters
  use years before S. Inner validation uses eligible earlier seasons, beginning
  with 2017, with at least two preceding training seasons. Fit no transforms on
  validation data. Persist inner-fold choices and every fallback.
- All CLI runners accept `--run-id`, `--expected-code-sha`, `--environment preview`,
  `--as-of`, `--config`, and named predecessor URI arguments. Default to dry-run;
  `--apply` requires a clean tracked worktree and matching committed code SHA.
  Independent verifiers accept `--manifest-uri`, `--expected-code-sha`, and
  `--environment preview`. Existing v1 interfaces remain historical compatibility.
- Write under `artifacts/research/data-first-football-v1/<stage>/v2/runs/<run-id>/`.
  Each schema name below receives prefix `data_first_` and suffix `_v2`.
  Manifest envelope: schema version, run/code/config identities, cutoff, explicit
  predecessor roles/URIs, raw-object hashes, canonical manifest checksums, output
  DatasetRefs, row counts, population digest, eligibility, and
  `production_activation_authorized: false`. Verify raw bytes before decoding and
  recompute the canonical checksum excluding its own checksum field.
- Unknown future refs are runtime outputs, not invented constants. Enforce role,
  version, membership, checksums, and eligibility; hashes alone never confer validity.
- Predictive rows bind season/week/game/team or side, target/candidate, forecast
  cutoff, source IDs and availability through an immutable lineage-ref URI/hash,
  training seasons, code/config/model identities, and explicit fallback reasons.
  Keys must be unique. Schedule/outcome population is independent of successful joins.
- Historical repaired sources remain reconstructed-only. Live use additionally
  requires authentic availability before the freeze. No backdating captures.
- Bootstrap: 2,000 replicates, seed 20260908, seasons then week blocks, keeping
  paired game predictions together. Use common resamples across candidates,
  baseline-minus-challenger absolute error, and 5th/95th percentiles. Improvement
  percent is 100 × (reference MAE − candidate MAE) / reference MAE.
- Shared-rating pooled score is the equal-weight mean of the two target MAEs.
  Single-target comparisons use that target only. A 0.5% tie means MAE at most
  1.005 × the best eligible MAE. No post-result grid/gate expansion.
- Artifact/numerical/chronology/population failures block the affected candidate
  or phase. Numerical optimizer failure may disqualify a challenger, but missing
  populations never become a smaller comparison set. A valid reference is a
  legitimate outcome. Invalid references block advancement.
- Independent verification reconstructs features, predictions, metrics, bootstrap
  and selection from exact parents, rather than trusting stored selected flags.
  Test same-game/future perturbations, missing evidence, asymmetric experience,
  sparse/FCS teams, neutral sites, 2019→2021, and immutable identity/collision.
- Every execution requires focused tests, full warning-as-error Python/coverage,
  scoped Ruff, contract/schema validation, V4/boundary regression checks, strict
  MkDocs, and `git diff --check`. Preserve unrelated changes and user Git control.

## Documentation implementation and acceptance

Save the seven approved records; replace active advancement claims in onboarding,
roadmaps, measurement/evaluation guidance and the index. Add dated supersession
banners without rewriting historical findings or session logs. Preserve Phase 0,
corrected Phase 1 dispositions, and unaffected Phase 2 engineering evidence.

Acceptance: one unambiguous corrective queue; no active permission to consume the
old Phase 4B forecast parent; all six contracts linked and approval/dependency
states explicit; checksum types and evidence limits named; documentation build,
authority checks and diff checks pass. No phase code or cloud state changed.

### Documentation closure (2026-09-08)

The review, six approved/unexecuted contracts, active authority corrections,
supersession notices and session log are saved. Existing documentation-authority
tests passed (3 tests); strict MkDocs, contract metadata/link/queue checks and
`git diff --check` passed. This lifecycle completion applies only to this
documentation reset, not to any replacement research phase.

## Risks and amendments

The expanded grid adds selection uncertainty; these are exploratory comparisons
until prospective evaluation. Captured historical metadata may not prove a live
preseason snapshot. Missing or ambiguous inputs must not silently become neutral
claims. Material changes to families, equations, candidate grids, cutoffs,
uncertainty, thresholds, budgets, or production boundaries require a recorded,
user-approved amendment before inspecting affected new results.
