# V5-09: 2026 Forecast Generation and Live Readiness

> **Current completion boundary (2026-09-22):** [V5 model development is complete](../../modeling/v5_status.md). This contract certifies a current operational forecast after stabilized Week 4 finals and fresh independently verified 07/08 parents. The [site cutover contract](../2026-09-22/04-v5-authority-simplification-and-site-cutover.md) requires a Preview serving rehearsal and V4 rollback proof, then a separate activation decision; six prospective slates are not its entry gate.

- **Status:** In Progress — preparation only pending the required Week 4 refresh
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the three-contract 2026 extension plan on 2026-09-18 with decisions: Repair extension (not V4-Silver-direct), three layered contracts, full season from Week 0. Implementation explicitly deferred.
- **Implementation log:** `session_logs/2026-09-22/08-v5-09-forecast-preparation.md`
- **Commit policy:** Separate code and certified-evidence checkpoints; user explicitly authorized Git add and commit.

## Goal, current state, and entry gate

Apply the **frozen** Contract 11C bridge (shared `expanding` horizon,
alpha-10 reference heads, per-season calibration variances, and the
through-2025 final fit) to the certified
2026 team states to produce 2026 V5 predictions, then re-verify live
readiness to `ready` — satisfying the Contract 06 entry gate so prospective
slate collection can begin. No bridge refitting on 2026 outcomes: 2026 is
application, not selection. The [common contract](../../archive/v5-contracts/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
is binding.

**Entry gate:** Contracts 07 and 08 Implemented, with certified 2026
measurement and rating manifests recorded as the sole eligible 09 parents.
This contract starts only when both manifests exist in Preview R2. The
historical certified forecast identity is `forecast-v1-20260921-5afd577-11c`
(Amendment 1; supersedes `forecast-v1-20260917-4600ddd-04b`; independently
verified with `final_fit_verified: true`, verifier manifest SHA
`4cfe5ef86e4e7145d6dfe3d4e2f1ea85e54475c439fce04a1ce41ec21dfa363b`); its
selection stays frozen and untouched.

**Historical-first deferral (2026-09-18):** Do not execute this approved
contract until Contracts 10-12 close, the user explicitly accepts historical
readiness, and 07-09 are re-reviewed with the frozen design, exact eligible
artifacts, through-2025 final fit/calibration, selected-prior inputs, and
timestamp provenance. A retrospective 2026 forecast or `live` timing label does
not establish prospective evidence or satisfy Contract 06.

**Conditional-results clarification (2026-09-20):** Implemented Contract 11A
and approved Contract 12A may produce `conditional_historical_results_only`
development evidence only.
They do not close Contracts 10-12, restore forecast eligibility, establish
prospective evidence, or satisfy this contract's explicit-user-acceptance and
re-reviewed-application gate.

**Re-review record (2026-09-22):** The deferral gates are satisfied — Contracts
10, 11, and 12 are Implemented, and the user explicitly accepted the Contract 12
historical readiness recommendation on 2026-09-22
(`docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`;
scorecard run `readiness-v1-20260921-scorecard`, manifest SHA
`a8351fb3cabd7edbd1f78c961aa563a110b585db6c410e2b3f5973c8a2278b29`).
Contracts 07–09 were re-reviewed under
[`docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`](../../archive/v5-contracts/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md):
the historical-first deferral is **lifted** and execution is authorized against
the corrected certified lineage (Amendment 1). 2026 forecasts apply the
through-2025 final-fit heads and final calibration — nothing is fitted on 2026
outcomes. **First readiness target: the Week 5 slate (~Thu Oct 1 first
kickoff); readiness for Week 4 is explicitly not required, and a skipped
Week 4 slate is expected, not a failure.**

There are no 2026 V5 predictions at planning time, and live readiness is
verified `blocked`. Historical forecast predictions are not modified,
re-selected, or inherited as 2026 evidence.

## Approach, scope, and interfaces

Generate 2026 forecast predictions by applying the frozen bridge to 2026
team states with the frozen non-offense offsets procedure, then execute the
certified 05 shadow tooling (readiness + frozen replay) against the next
live 2026 slate to produce a `ready` readiness report. New run-IDs
throughout; full preflight/apply/independent-verify/idempotent-repeat cycle
in Preview.

Stage: `forecast-2026` then `shadow`. Consume the certified 08 rating
manifest (and its 07 measurement parent) plus the frozen 11C bridge
definition (through-2025 final fit). Output versioned 2026 `forecast_prediction` records and a
terminal 2026 forecast manifest with `production_activation_authorized: false`,
followed by a `ready` 05A-style readiness report for the next live slate.
No Neon/production/web writes, no market-driven changes.

The `ready` readiness report satisfies the Contract 06 entry gate ("verified
candidate from 04 and ready, independently verified live inputs/tooling from
05"). Slate collection itself belongs to Contract 06, not this contract.

## Implementation tasks

### Task 1 — 2026 forecast generation with the frozen bridge

Build 2026 feature frames by joining certified 2026 team states with pregame
completed-game counts and non-offense offsets (same offsets procedure as the
certified bridge, applied to 2026 scoring events). Apply the **through-2025
final-fit bridge heads** (alpha-10, shared `expanding` horizon, training
through 2025) and the **final calibration variances** from
`forecast-v1-20260921-5afd577-11c` — not the 2024-max fold heads — without
refitting anything on 2026 outcomes. Emit
2026 `forecast_prediction` partitions and a terminal 2026 forecast manifest
published last, marked as an application (not a selection).

**Acceptance:** 2026 predictions present for completed 2026 weeks in Preview;
bridge parameters byte-comparable to the frozen 11C final-fit definition; no
quantity fitted on any 2026 outcome; deterministic (byte-identical rerun).

**Validation:** Forecast preflight + apply + idempotent repeat; focused
bridge-fidelity unit tests (frozen alpha/horizon/variances); `uv run ruff check .`.

### Task 2 — Independent verification of the 2026 forecasts

Independently reconstruct the 2026 feature frames, predictions, and manifest
from the certified 08/07 parents and the frozen 11C final-fit definition using
verifier-owned code that never imports the forecast producer. Confirm parent
identity, bridge fidelity, timing classes, and manifest signature;
idempotent repeat returns `already_applied` with zero writes.

**Acceptance:** Signed verifier confirmation of the 2026 forecasts
end-to-end from source artifacts; manifest recorded as the 2026 forecast
identity for readiness and Contract 06.

**Validation:** Verifier CLI run + signed verifier manifest; R2 inventory
confined to the Preview research prefix.

### Task 3 — Live readiness re-verification to `ready`

Execute the certified 05 readiness tooling against the next live 2026 slate
using the 2026 forecast identity from Task 1: all six sources re-resolved
(candidate, schedule, completed_games, scoring, priors, team_states) with
`pre_cutoff` timing evidence. Produce a `ready` readiness report plus frozen
replay proof; refresh the live-readiness assessment doc preserving history.
On `ready`, record the Contract 06 handoff: the next slate may proceed under
Contract 06 Task 1 (freeze at T-2h target / T-1h hard limit, ≥40 paired games).

**Acceptance:** Readiness report with overall verdict `ready` for a live 2026
slate, independently verified; live-readiness assessment doc refreshed;
Contract 06 entry gate documented as met.

**Validation:** Readiness preflight (+ replay proof) + apply + independent
verify + idempotent repeat; strict MkDocs and `git diff --check` for
documentation updates.

## Testing strategy

Focused unit tests for bridge fidelity (frozen alpha/horizon/variances on
2026 frames) and the 2026 offsets application. Full certification cycles
(preflight/apply/verify/repeat) for forecast generation and readiness.
Reuse the existing forecast-verifier and shadow-verifier patterns; do not
add mirror tests for certification-only runs. Strict MkDocs and
`git diff --check` for documentation updates.

## Risks, definition of done, and amendments

Any refit of bridge alphas, horizons, offsets, or calibration on 2026
outcomes is tuning and is prohibited — this contract is application-only.
A `blocked` readiness re-verdict is contractually complete evidence (not a
failure) but leaves Contract 06 gated; its missing sources must name the
exact unmet dependency. Sealed 04/05 code (bridge definition, parent
run-IDs, readiness sources) requires explicit amendment to admit the 2026
parents.

- [ ] 2026 forecast manifest certified in Preview (preflight/apply/verify/repeat); nothing fitted on 2026 outcomes.
- [ ] Live readiness re-verified `ready` for a 2026 slate with frozen replay proof.
- [ ] Contract 06 entry gate documented as met; handoff to 06 collection recorded.
- [ ] Historical forecast artifacts (`forecast-v1-20260921-5afd577-11c` certified; superseded `forecast-v1-20260917-4600ddd-04b`) byte-identical, selection untouched.
- [ ] No production/Neon/web writes; manifest carries `production_activation_authorized: false`.
- [ ] Reports, runbook status, plan index, roadmap status, contract lifecycle, and session logs are current.

Follow the common amendment process for bridge, timing, counting,
calibration, or source changes. Slate collection, scoring, market
diagnostics, and the promotion recommendation belong to Contract 06, never
to this contract. While 2026 forecast/readiness certification is incomplete,
leave this contract In Progress and Contract 06 unstarted.

## Amendments

### Amendment 1 — Re-reviewed lineage, final-fit application, lifted deferral (Sol, 2026-09-22)

**Reason:** The historical-first lane completed 2026-09-21 and the user
explicitly accepted the Contract 12 recommendation on 2026-09-22. The
2026-09-18 deferral required re-review against the corrected certified
artifacts — frozen design, exact eligible artifacts, through-2025 final
fit/calibration, selected-prior inputs, and timestamp provenance — before any
execution. Finding 004's closure created the through-2025 final fit that 2026
application must use.

**Original approach:** This contract bound the frozen bridge to
`forecast-v1-20260917-4600ddd-04b` (2024-max fold heads, no through-2025
final fit at deferral time) and deferred all execution behind Contracts
10–12, explicit user acceptance, and re-review.

**Revised approach:** The frozen bridge is re-pointed to
`forecast-v1-20260921-5afd577-11c` — independently verified by 11D (verifier
manifest SHA
`4cfe5ef86e4e7145d6dfe3d4e2f1ea85e54475c439fce04a1ce41ec21dfa363b`,
`final_fit_verified: true`) — and 2026 forecasts explicitly apply the
**through-2025 final-fit heads (alpha-10, expanding horizon) and final
calibration variances**, not the 2024-max fold heads. Nothing is fitted on
2026 outcomes. First readiness target: the **Week 5** slate (~Thu Oct 1 first
kickoff); readiness for Week 4 is explicitly not required, and a skipped
Week 4 slate is expected, not a failure. The historical-first deferral is
lifted; execution is authorized. All application-only guarantees are
unchanged: no refit of bridge alphas, horizons, offsets, or calibration on
2026 outcomes; a `blocked` readiness re-verdict is contractually complete
evidence naming its exact unmet dependency; sealed 04/05/11C code admits the
2026 parents only by explicit amendment; `production_activation_authorized:
false`; no Neon/production/web writes.

**Impact:** No design or scope change; the certified bridge identity is
re-pointed and the final-fit application is made explicit (this is what
closing Finding 004 unlocked). Re-review authority and the authorized
execution sequence:
[`docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`](../../archive/v5-contracts/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md).

### Amendment 2 — Outcome-free live forecast application (Sol, 2026-09-22)

**Reason:** The certified 11C historical prediction dataset requires actuals,
absolute error, and CRPS. It cannot represent future pre-kickoff forecasts.
Contract 05 also pins its historical candidate manifest. A distinct live
interface is required to make the approved 2026 application and prospective
readiness executable while preserving the historical artifacts.

**Original approach:** Contract 09 referred to 2026 `forecast_prediction`
records and the Contract 05 readiness tooling, without defining an outcome-free
live record or a live candidate identity accepted by the shadow contracts.

**Revised approach:** The 2026 application uses the additive
`data_first_live_forecast_prediction_v1` and
`data_first_live_forecast_manifest_v1`. Rows contain finite mean, variance,
95% interval, offset, completed-game stage, `live` timing, and exact model,
state, and source refs; they contain no actual, absolute error, or CRPS. The
terminal signed manifest binds exact refreshed Contract 07 measurement and
Contract 08 replay URIs/raw checksums, the certified 11C bridge manifest
`forecast-v1-20260921-5afd577-11c`, source cutoff, complete 2026 schedule
population, output digest, and `production_activation_authorized: false`.

Apply reconstructs and applies the frozen `expanding` design and target recipes
from 11C through-2025 evidence. Any fitted Ridge coefficients are deterministically
reconstructed using the fixed 11C development population and retained recipe;
there is no selection, calibration, or fitting on 2026 outcomes. The
independent verifier owns its reconstruction and does not import the producer
or historical selection runner. Contract 05 support is versioned to accept this
live identity while preserving the old historical identity and all readiness,
freeze, scoring, and eligibility gates.

**Entry and apply gate:** Code implementation and synthetic tests may proceed
now. Operational preflight/apply/verification must use stabilized Week 4
finals and fresh, independently verified Contract 07 and 08 manifests through
Week 4, under new run identities. The Weeks 0–3 replay cannot substitute for
these parents. The forecast identity also binds an explicit immutable 2026
schedule source URI and raw checksum because the measurement population records
completed games while the forecast population must include future scheduled
games. Only games strictly after the forecast cutoff receive live prediction
rows. This amendment does not authorize a live apply during code-readiness work.

**Impact:** No historical 11C output/schema, V4 behavior, database/serving
interface, or production activation path changes. Contract 09 remains In
Progress until its future Preview forecast and Week 5 readiness cycles are
certified. Only verified `ready` opens Contract 06; a verified `blocked`
result records the exact missing dependency.

### Amendment 3 — Code-ready Preview runner (2026-09-22)

**Reason:** Amendment 2 defined the permitted live data interface and future
execution gate. Its implementation was completed under the approved
[V5 live research tooling completion plan](../../archive/v5-contracts/2026-09-22/03-v5-live-research-tooling-completion.md).

**Revised approach:** `scripts/research/run_v5_live_forecast.py` now provides
the Contract 09 Preview preflight, evidence-bound apply, independent verify,
and idempotent repeat path. The runner requires exact measurement, rating, and
schedule refs; validates the stabilized Week 4 gate; applies the frozen 11C
final-fit bridge; and writes the outcome-free live prediction manifest last.
Contract 05's versioned live adapter carries that identity through readiness,
freeze, scoring, and verification. Synthetic tests exercise these paths without
publishing operational artifacts.

**Impact:** This amendment records code readiness only. No Preview preflight,
apply, readiness certification, or Contract 06 slate count was run. Execution
still requires stabilized Week 4 finals and new independently verified 07/08
manifests under fresh IDs. Contract 09 remains In Progress until the live
forecast and Week 5 readiness cycles are certified; a verified `blocked`
readiness remains valid output but does not open Contract 06.
