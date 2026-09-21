# V5-08: 2026 Rating-State Replay

- **Status:** Approved
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the three-contract 2026 extension plan on 2026-09-18 with decisions: Repair extension (not V4-Silver-direct), three layered contracts, full season from Week 0. Implementation explicitly deferred.
- **Implementation log:** Pending; create one log per execution session (priors assembly, replay, verification).
- **Commit policy:** Separate code and certified-evidence checkpoints; user executes Git.

## Goal, current state, and entry gate

Replay the **frozen** Contract 03 winner `ppp__rho_0_60__exposure`
(carryover prior + exposure updater) forward through the live 2026 season,
from Week 0 through the latest completed week, producing certified 2026
`team_states` so readiness resolves and Contract 09 can forecast. No
re-selection, no candidate comparison, no tuning: 2026 is replay, not a new
validation season. The [common contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
is binding.

**Entry gate:** Contract 07 Implemented with a certified 2026 measurement
manifest recorded as the sole eligible 08 parent. This contract starts only
when that manifest exists in Preview R2. The historical 03 retained manifest
(`possession-v1-ratings-20260917-d029526-cert`) and its selection stay
frozen and untouched.

**Historical-first deferral (2026-09-18):** Do not execute this approved
contract until Contracts 10-12 close, the user explicitly accepts historical
readiness, and 07/08 are re-reviewed with the frozen design, exact eligible
artifacts, through-2025 final fit/calibration, selected-prior inputs, and
timestamp provenance. Replaying 2026 results never creates prospective evidence.

**Conditional-results clarification (2026-09-20):** Implemented Contract 11A
and approved Contract 12A may produce `conditional_historical_results_only`
development evidence only.
They do not close Contracts 10-12, restore forecast eligibility, establish
prospective evidence, or satisfy this contract's explicit-user-acceptance and
re-reviewed-application gate.

There are no 2026 team states at planning time. Historical rating states are
not modified, re-selected, or inherited as 2026 evidence.

## Approach, scope, and interfaces

Assemble 2026 preseason priors from the existing preseason ingestion path,
then run a state-replay (not a tournament) that applies the frozen winner's
prior family and updater to the certified 2026 measurements week by week,
emitting 2026 `rating_states` and `team_states` with `live` timing. New
run-ID; full preflight/apply/independent-verify/idempotent-repeat cycle in
Preview.

Stage: `rating-replay`. Consume the certified 07 measurement manifest plus
2026 preseason context (returning production, recruiting, coaching via the
existing `ingest_preseason.py` path). Output versioned 2026 `priors`,
`rating_states`, `team_states`, and a terminal `retained-rating-manifest.json`
marked as a replay (not a selection) with
`production_activation_authorized: false`. No Neon/production/web writes.

The 2026 rating manifest becomes the sole eligible rating parent for
Contract 09. The historical 03 retained manifest remains the sole eligible
parent for historical replay; neither substitutes for the other.

## Implementation tasks

### Task 1 — 2026 preseason prior assembly

Assemble 2026 preseason context blocks (returning production, recruiting,
coaching continuity) through the existing preseason ingestion path for the
2026 season, bound to exact immutable input refs. Apply the frozen winner's
prior family (`rho_0_60` carryover structure with 2026 context where the
family requires it) without refitting any learned quantity on 2026 outcomes.
Persist 2026 `priors` with `live` timing and exact source refs.

**Acceptance:** 2026 priors present in Preview with exact input refs; no
learned quantity fitted on any 2026 outcome; frozen family structure
byte-comparable to the certified 03 definition.

**Validation:** Focused prior-assembly unit tests; input-ref binding checks;
`git diff --check`.

### Task 2 — Week-by-week state replay (Week 0 through latest completed)

Execute the replay runner: for each 2026 week from 0 through the latest
completed week, advance every team's offense/defense states using the frozen
carryover prior and exposure updater applied to that week's certified 2026
observations, with strict pre-kickoff cutoff semantics (a week's games enter
states only after finals stabilize, mirroring the historical replay
discipline). Emit 2026 `rating_states` and `team_states` partitions;
terminal replay manifest published last.

**Acceptance:** Continuous 2026 state history with no gaps from Week 0;
every state row traceable to pre-cutoff certified measurements; replay is
deterministic (byte-identical rerun).

**Validation:** Replay preflight + apply + idempotent repeat; continuity and
cutoff unit tests; `uv run ruff check .`.

### Task 3 — Independent verification of the 2026 replay

Independently reconstruct the 2026 priors, states, and replay manifest from
the certified 07 measurement parent and exact preseason input refs using
verifier-owned code that never imports the replay producer. Confirm parent
identity, timing classes, cutoff discipline, and manifest signature;
idempotent repeat returns `already_applied` with zero writes.

**Acceptance:** Signed verifier confirmation of the 2026 replay end-to-end
from source artifacts; readiness `team_states` source resolves against 2026
rows; manifest recorded as the sole eligible 09 rating parent.

**Validation:** Verifier CLI run + signed verifier manifest; R2 inventory
confined to the Preview research prefix; strict MkDocs and `git diff --check`
for documentation updates.

## Testing strategy

Focused unit tests for 2026 prior assembly (no 2026-outcome fitting),
replay continuity from Week 0, and pre-kickoff cutoff discipline. Full
certification cycle (preflight/apply/verify/repeat) for the replay run.
Reuse the existing rating-verifier patterns; do not add mirror tests for
certification-only runs. Strict MkDocs and `git diff --check` for
documentation updates.

## Risks, definition of done, and amendments

Any refit of priors, updater parameters, or selection on 2026 outcomes is
tuning and is prohibited — this contract is replay-only. Incomplete 2026
weeks (CFBD finals lag) block replay advancement for that week; never
advance states on partial outcomes. Sealed 03 code (candidate registry,
`OUTER_SEASONS`, parent run-IDs) requires explicit amendment to admit the
2026 replay parent.

- [ ] 2026 priors assembled with exact input refs; nothing fitted on 2026 outcomes.
- [ ] Certified 2026 rating replay manifest in Preview (preflight/apply/verify/repeat).
- [ ] Continuous 2026 state history from Week 0; readiness `team_states` source resolvable.
- [ ] Historical 03 retained manifest and selection byte-identical and untouched.
- [ ] No production/Neon/web writes; manifest carries `production_activation_authorized: false`.
- [ ] Reports, plan index, roadmap status, contract lifecycle, and session logs are current.

Follow the common amendment process for prior, updater, timing, or replay
changes. While 2026 replay certification is incomplete, leave this contract
In Progress and Contract 09 unstarted.
