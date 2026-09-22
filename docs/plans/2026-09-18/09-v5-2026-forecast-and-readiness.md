# V5-09: 2026 Forecast Generation and Live Readiness

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
application, not selection. The [common contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
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
[`docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`](../2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md):
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
[`docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`](../2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md).
