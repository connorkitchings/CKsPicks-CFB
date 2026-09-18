# V5 Ratings Successor: Roadmap and Common Contract

- **Status:** Approved
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User approved the complete proposed package with “Implement the proposed plan.” on 2026-09-13. The agreed persistence boundary saves contracts and the planning log in this task; documentation and research implementation use separate Terra tasks.
- **Planning log:** `session_logs/2026-09-13/02-v5-ratings-roadmap-planning.md`
- **Implementation log:** Per-phase logs; no computational implementation in this planning task.
- **Commit policy:** Separate plan-package commit; user controls staging, commits, and pushes. Each computational phase subsequently separates code and certified-evidence checkpoints.

## Goal and current state

Continue the ratings-first transformation with targeted methodology corrections
and a complete queue of bounded implementation contracts. The first release is
a verified, uncertainty-bearing ratings-to-margin/total shadow candidate, not a
production replacement. One offense and one defense rating express team quality
continuously throughout a season.

The repository was clean on `main` at `ca2adee` during planning. The reviewed
September 9–13 records establish the following checkpoint; this session did not
repeat cloud certification:

| Area | Recorded state | Permitted use |
| --- | --- | --- |
| V4 production | Week 2 scored; Week 3 `2026w3-68fe6a815bd6` published, freeze pending | Unchanged production champion and rollback authority |
| Repair v2 | `repair-v2-20260909T1417Z`, independently verified; manifest raw SHA `b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4` | Repaired source and population parent, reverified at consumption |
| Phase 3 v2 | `phase3-v2-compact-state-20260910-r2`, certified September 11; selected `quality_core_epa_split` | Historical reconstructed benchmark, not the possession definition |
| Possession methodology | Specified September 11; Contract 02 implemented 2026-09-15 | R6 Preview measurements independently certified; eligible parent for Contract 03 only |
| Feature-v5 diagnostic | Week 0/1 scored; formal pooled verdict awaiting Week 2 scoring | Separate V4 diagnostic; the finals dependency is now recorded as available, subject to fresh verification |

Use **V5 ratings successor** as the human-facing research name. Preserve existing
artifact identities. **Feature schema v5** and the V4 shadow rebuild diagnostic
are not the V5 ratings model.

The investigation found stale current-state claims in README, the documentation
home, onboarding context, the production/historical roadmap, and evaluation
guidance. The existing five authority tests and strict MkDocs build passed despite
that semantic drift. Repair those assertions in contract 00, not by rewriting
historical session records.

## Approved approach and phase queue

The user selected: evidence-led methodology review; all phase contracts now;
bridge-first forecasts; separate diagnostic closure; the V5 research name;
a bounded fitting-history comparison; and arithmetic forecasts as an optional
later challenger rather than a first-shadow prerequisite.

| Order | Contract | Entry gate | Exit product |
| --- | --- | --- | --- |
| 00 | [Documentation alignment and methodology amendment](00-v5-documentation-and-methodology-alignment.md) | This approved package | Consistent authority pages, replacement links, and authority tests |
| 01 | [V4 feature-v5 diagnostic closure](01-v4-feature-v5-diagnostic-closure.md) | Existing shadow refs and reverified Week 2 finals | Paired diagnostic verdict; independent of rating progress |
| 02 | [Possession measurement certification](02-v5-possession-measurement-certification.md) | 00 complete; exact verified Repair v2 sources | Certified possession/scoring ledger, measurements, replay and quality evidence |
| 03 | [Possession rating estimation](03-v5-possession-rating-estimation.md) | 02 independently verified | Selected definition/prior/updater design and state evidence |
| 04 | [Forecast bridge and fitting-window selection](04-v5-forecast-bridge-and-fitting-window.md) | 03 independently verified | Historical forecast artifact; downstream forecast eligibility remains open pending 11 |
| 05 | [Prospective readiness and shadow tooling](05-v5-prospective-readiness-and-shadow-tooling.md) | Tooling implementation | Diagnostic rehearsal and readiness tooling only; it does not certify forecast quality |
| 06 | [Prospective evidence and recommendation](06-v5-prospective-evidence-and-recommendation.md) | 10, 11, and 12 accepted; then live readiness | Six-slate evidence recommendation, or precise continued-shadow status |

Contract 01 is a side task; its result neither blocks nor chooses the ratings
candidate. Every phase requires its own implementation session. Approval of a
downstream contract does not satisfy its prerequisites. Unknown manifest URIs
are runtime outputs, never invented planning constants.

## Historical-first correction (2026-09-18)

The historical V5 foundation through 2025 is the active priority. Contracts
02 and 03 remain implemented historical evidence, and 04A retains its completed
implementation/preflight record. Contract 04B and umbrella 04 are reopened
because the current forecast verifier validates the signed manifest, identities,
and reference labels but does not independently reconstruct forecast outputs,
offsets, bridge fits, calibration, or horizon selection. The stored forecast
artifact remains inspectable historical evidence but is not an eligible certified
forecast parent until [11](../2026-09-18/11-v5-forecast-verification-closure.md)
closes that gap.

Contract 05 remains implemented as shadow-tooling work. Its historical rehearsal
uses permanently diagnostic predictions and therefore establishes neither
forecast quality, prospective evidence, nor live readiness. Contracts 10-12
audit the complete foundation, close forecast verification, and report historical
results before any 2026 application is reconsidered. A future frozen algorithm
may update state from preceding finalized games, but 2026 outcomes cannot choose
or tune its design. Retrospective replay, pre-kickoff prospective evidence, and
production promotion are separate milestones.

## Binding methodology amendments

### Quantities, accounting, and first-release forecasting

Compare true points per possession (PPP) with EPA per possession, using the
same approved eligible regulation possession set. One offense and one defense
state per definition carry uncertainty. Passing/rushing/finishing and other
components remain diagnostics rather than additional rating states.

Opponent adjustment remains the upstream four-pass, league-centered procedure.
Do not adjust for schedule strength again inside the rating filter. PPP measures
scoring; EPA measures added expected value, not literal scoring. Preserve native
units, provider/version metadata when available, and reconstructed/live timing
classifications. CFBD warns that its outputs are not interchangeable and model
changes can affect historical comparisons ([CFBD methodology](https://apinext.collegefootballdata.com/methodology-overview)).

Maintain a scoring ledger that accounts separately for eligible regulation
offense, excluded regulation offense, regulation non-offense, overtime, and
unresolved scoring. Defensive scores cannot be inferred to be outside an
offensive drive merely because the drive had an eligible scrimmage play. Verify
event attribution explicitly before reusing the old reconstruction for PPP.

Use the existing four-role-rating Ridge bridge to margin/total for the first
release. Full-game labels include overtime and scoring excluded from rating
evidence. A declared prior-only non-offense expectation is a translation offset,
not a third rating. Volume diagnostics remain separate. Possession arithmetic,
EPA-to-points conversion, clock tempo, field-position normalization, NB2, residual
ML, and additional context families require a separately frozen later challenger.
They do not block a verified first bridge candidate.

### Chronology and fixed constants

Develop on 2015–2019 and 2021–2025. Reject 2020 in inputs, labels, folds, priors,
and outcomes. Already admitted explicitly named earlier auxiliary metadata is
not an extra outcome season. Outer validation seasons are 2018, 2019,
2021–2025. Inner validation begins in 2017 with at least two preceding fitting
seasons. Fitted preprocessing, priors, noise, heads, and calibration must precede
the season being predicted. Historical 2025 is development evidence; V4's sealed
evaluation contract is unchanged. No 2026 outcome enters this development search.

Remove the proposed 2015–2019 global constant-estimation step: it overlaps outer
2018/2019 and inner validation. Retain the already published provisional values
as **fixed first-generation settings**, not values empirically certified by this
planning session:

| Setting | PPP | EPA/possession |
| --- | --- | --- |
| Standardization scale floor | 0.30 | 0.50 |
| Fallback scale | 1.00 | 1.50 |
| Equivalent prior exposure k, possessions | 8 | 20 |

Reuse the existing neutral fallback center and preceding-season team-equal
centering/scaling policy. Compute empirical seasonal scales only from preceding
terminal measurements; preserve the explicit 2019→2021 predecessor relationship.
Report floors, fallbacks, and sensitivity concerns; do not tune these constants
after looking at errors. Any later tuning needs an earlier-only fitting rule and
a new version. This preserves the earlier-observations-only principle of
[rolling-origin evaluation](https://otexts.com/fpp3/tscv.html).

### Analytic and dynamic uncertainty

For usable exposure n, equivalent exposure k, prior mean m0 and variance P0:

```text
I = n / k
P = 1 / (1/P0 + I)
m = P * (m0/P0 + I*z)
evidence_weight = I / (1/P0 + I)
```

With no usable observation, I is zero. `n/(n+k)` describes the evidence weight
only when P0 equals one. Recency applies the declared half-life weights to
numerator and denominator before the same posterior; do not substitute a new
effective-sample-size definition. Kalman is the separate specified local-level
challenger with possession information and preceding-season q/r fitting.
Posterior rating variance is not outcome-error variance.

### Fitting-history experiment

After structural rating selection, compare expanding fitting history with the
latest five eligible completed seasons available at **each** fit. Do not truncate
continuous state carryover. Refit priors/noise/heads/calibration chronologically
under each policy and compare identical 2022–2025 validation games. Retain
expanding history unless the bounded challenger clears contract 04's gates.
Report 2018–2019, 2021, and 2022–2025 separately; pooled history alone cannot hide
recent-era regressions. This is development selection, not independent evidence.

## Shared interfaces and implementation constraints

Reusable code belongs in the isolated `src/cks_picks_cfb/ratings/` namespace;
schemas/validators in `src/cks_picks_cfb/data/`; runners/verifiers in
`scripts/research/`; config in `conf/research/data_first_football_v1/`.
Introduce new possession-specific modules rather than change V4 behavior.

Research runners accept `--run-id`, `--expected-code-sha`, `--environment preview`,
`--as-of`, `--config`, and the phase's named parent URI flags. Default to dry-run.
`--apply` requires matching committed code, clean tracked worktree, and a passing
same-code preflight. Verifiers accept `--manifest-uri`, `--expected-code-sha`, and
`--environment preview`. Freeze/score also use explicit season/week/V4/input refs.

Use the new stage root
`artifacts/research/data-first-football-v1/possession-v1/<stage>/runs/<run-id>/`.
Schema names use `data_first_possession_<record>_v1`. Never overwrite existing
Phase 3/4 or historical artifacts. Research DatasetRefs and schema validation do
not authorize catalog registration or serving writes. No database migration,
new subscription, provider acquisition, or repository `./data/` is in scope.

Every manifest includes code/config/schema identities, explicit parent roles and
URIs, raw-object SHA-256 and canonical checksums, output DatasetRefs, counts,
population digest, source cutoff/timing class, eligibility, verification refs,
and `production_activation_authorized: false`. Verify bytes before decoding and
canonical checksums excluding their own checksum field. Use prior verified
consumer roles, not checksum validity alone, to decide eligibility.

Use stable season/week/game/team/role keys, candidate and cutoff where relevant,
unique output keys, nulls with reasons, and no successful-join-derived forecast
population. Scoreable population remains separate from measurement and market
coverage. Bind every prediction to exact model/state/data lineage. Independently
verify each manifest and its raw sources at consumption; old approval or a stored
`selected` flag is insufficient.

Bound memory and writes by season/cutoff partitions. Cache shared measurement
replays and fit prerequisites across candidates with complete code/config/parent
identity keys. Persist checkpoints and replay counts. Apply must agree with its
preflight membership and part plan; a failed partial run cannot become eligible.

## Shared evaluation and validation

Unless explicitly replaced here, inherit the mathematical bootstrap, population,
stage, fallback, and validation rules from the September 8 [common contract](../2026-09-08/transformation-review-and-authority-reset.md#binding-common-execution-contract).
This inheritance does not authorize running its execution-held scripts.

- Paired hierarchical season/week bootstrap: 2,000 replicates, seed 20260908,
  common resamples, baseline-minus-candidate absolute error, 5th/95th percentiles.
- Shared-rating pooled score is the equal-weight mean of margin and total MAE;
  target-specific tests use their own target. Early union counts a game once
  when either team has 0–3 completed games. Stage diagnostics use 0/1/2/3/4+ and
  preserve asymmetric experience. Count completed games from finalized schedule
  history, independently of usable observations.
- Preserve the existing 0.5% gain/tie convention and positive paired lower-bound
  rule. State whether a gain is overall or early-only. Do not expand a registry
  or relax gates after inspection. Reference validity is mandatory; a valid
  simple reference may be the retained result.
- Mandatory tests cover same-game/future perturbations, missing/invalid sources,
  entire schedule population, FCS fallback, neutral/unknown venues, side signs,
  2020 exclusion, the 2019→2021 gap, cold starts, uncertainty, immutable collision,
  retries, and idempotency. Verifiers independently rebuild calculations rather
  than merely call the producer and compare its selected flag.
- Computational phases require focused tests, full warning-as-error Python and
  configured coverage checks, scoped Ruff, affected schema/contract checks,
  production-boundary regression, strict MkDocs, and `git diff --check`.
  Preserve unrelated worktree changes; never broad-format a dirty tree.
- Record implementation, certification, downstream eligibility, and prospective
  status separately. Do not label code completion as model validation.

Markets remain excluded from football fitting, selection, and ratings. Historical
reconstructed data cannot establish authentic live availability. The existing
$15/month subscription ceiling remains; no purchases are authorized here.

## Persistence, handoff, and definition of done

This task saves this common contract, contracts 00–06, and the planning log only.
Contract 00 performs canonical roadmap and documentation/test edits in a fresh
Terra task. Do not silently execute a computational phase while persisting plans.

- [x] Approved strategy and all seven dependent contracts persisted together.
- [x] Contract 00 aligns canonical documentation and authority checks (2026-09-13; implementation log `session_logs/2026-09-13/03-v5-documentation-alignment.md`).
- [ ] Contract 01 closes the independent operational diagnostic.
- [ ] Contracts 02–04 produce independently verified measurement, rating, and forecast parents.
- [ ] Contract 05 verifies tooling and authentic live readiness.
- [ ] Contract 06 records protected evidence and a recommendation.

Only after six qualifying paired slates may a separate promotion contract be
proposed. Neither six slates nor a recommendation activates a model. There is no
deadline-driven replacement. V4 remains production and rollback authority.

## Risks and amendment process

The full grid and fitting-window comparison reuse development outcomes; their
confidence intervals do not make the selected result an untouched test. Sparse
FCS evidence, missing score attribution, source model-version gaps, or weak
calibration can block advancement. Describe blockers honestly rather than reduce
the population or invent zero observations.

Mechanical amendments may be logged in the implementing contract. Changes to
measurement meaning, architecture, public interfaces, families/grids, chronology,
source semantics, fitting rules, thresholds, budget, or production boundaries
require a user-approved planning amendment before affected new results are
inspected. Preserve historical approval sources and immutable evidence.
