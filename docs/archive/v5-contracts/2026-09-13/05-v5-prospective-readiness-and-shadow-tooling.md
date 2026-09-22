# V5-05: Prospective Readiness and Shadow-Operation Tooling

- **Status:** Implemented
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User approved the complete package with “Implement the proposed plan.” on 2026-09-13; execution requires verified forecast parents.
- **Implementation log:** `session_logs/2026-09-17/09-v5-05-execution-decomposition-planning.md`, `session_logs/2026-09-17/10-v5-05a-readiness-and-replay.md`, `session_logs/2026-09-17/12-v5-05b-freeze-score-ledger.md`, `session_logs/2026-09-18/02-v5-05c-rehearsal-verification-runbook.md`.
- **Commit policy:** Separate code and rehearsal/readiness checkpoints; user executes Git.

## Goal, current state, and entry gate

Make the candidate from [04](04-v5-forecast-bridge-and-fitting-window.md)
reproducibly operable in an isolated prospective lane, with honest live readiness.
The [common contract](v5-ratings-successor-roadmap-and-contracts.md) is binding.
Require independently verified candidate, rating, measurement and Repair refs.
The existing candidate-v1 shadow system is historical compatibility evidence,
not permission to reuse its six-slate counter or candidate identity.

This contract completes tooling and a diagnostic rehearsal. Actual prospective
slate collection and recommendations belong to [06](../../../plans/2026-09-13/06-v5-prospective-evidence-and-recommendation.md).

## Approach, scope, and interfaces

Implement isolated research `readiness`, `freeze`, `score`, and evidence-ledger
operations in the new possession namespace with CLIs under `scripts/research/`.
Do not alter production `publish-week`, `freeze-week`, or `close-week`, V4 bundles,
Neon activation, serving tables, or web publication. No catalog registration,
new provider acquisition, subscription, or recurring automation is authorized.
Use already permitted capture workflows and explicit immutable input refs.

Common CLI flags apply. Require `--candidate-manifest-uri`; live readiness/freeze
also require `--season`, `--week`, `--as-of`, `--v4-prediction-ref-uri`,
`--input-refs-uri`, and the declared slate/schedule ref. Score requires an exact
freeze manifest and outcome ref rather than a mutable current-week lookup.
Stage: `shadow`. Output records: `readiness`, `shadow_freeze`,
`shadow_prediction`, `shadow_evaluation`, `evidence_counter`, and
`shadow_rehearsal`. Use candidate/season/week/run keys; predictions add game/target;
evaluation adds outcome version. Diagnostic runs have an explicit permanently
ineligible evidence class.

## Implementation tasks

### Task 1 — Validate authentic source availability and candidate readiness

Resolve and independently verify every candidate parent. Check required live
season schedule, completed-game sources, score/possession semantics, priors and
auxiliary inputs, and the ability to reconstruct all team states at the cutoff.
Source-capture timestamps and effective times must substantiate availability
before the candidate freeze. A historically reconstructed preseason feature
does not become authentic simply because it can be queried today.

Use only the candidate's already declared optional-input fallbacks. Reject an
unavailable mandatory input; do not add a new fallback, reinterpret a roster
snapshot as preseason, or recapture and backdate data during readiness. Persist
per-source available/unavailable status, timing class, selected fallback, and
blocked reasons. The existing live capture path must be operationally usable.

**Acceptance:** Readiness is `ready` only with reproducible complete candidate
forecasts and authentic input evidence. A report can be technically verified
and still `blocked`; no freeze is eligible until ready.

### Task 2 — Replay only frozen algorithm updates

Freeze the full candidate algorithm and fitted prior/noise/head/calibration
parameters through the preceding completed season. Update ratings and non-offense
offsets only from permitted finalized games in earlier canonical weeks whose
source information was available before this freeze. The same rules apply to
both candidate replay and information-cutoff comparison with V4.

Do not refit priors, noise, heads, alpha choices or calibration on accumulating
prospective outcomes. New state identities under unchanged candidate rules do
not reset the window. A change to features, definitions, fitting/calibration,
cutoffs, source semantics or algorithm creates a new identity and a fresh window.
The next season may use the frozen annual fitting recipe; a changed design
cannot inherit earlier protected counts.

**Acceptance:** Replay proves one-use prior observations, no current-week outcome
updates, and identical forecasts from identical candidate/state/input refs.

### Task 3 — Implement measured immutable freezes

Use the first kickoff of the declared normal-coverage slate. Target T−2h and
require both V4 and candidate frozen at least T−1h before that kickoff. The
measured freeze completion/object-availability time is authoritative; a supplied
`--as-of` cannot backdate it. Bind the candidate identity, code/config/data/model/
state refs, slate membership digest, source-availability proofs, and exact V4 ref.

Require >=40 unique paired games with complete finite predictions for both
targets and normal schedule coverage. Preserve the candidate's complete broader
FBS-involving population, paired subset, and every exclusion separately; no
post-kickoff subset construction to evade an earlier kickoff. Week 0, pre-candidate
slates, diagnostic replays, late/incomplete/unverifiable/altered freezes never
qualify. Quote omissions do not determine football eligibility.

Preserve the declared population when schedule changes occur. A cancellation or
postponement remains visible with its disposition; it cannot create a new
retroactively convenient slate. Any scored paired count falling below 40 is
ineligible. Replacement/rescheduled fixtures require authentic future forecasts
under a separately declared slate, with no duplicate game evidence.

**Acceptance:** Fail closed on timing, identity, population, source or prediction
failure. Repeated freeze calls reuse the same immutable identity or reject an
incompatible collision; they never rewrite evidence.

### Task 4 — Implement outcome-versioned scoring and counting

Score only finalized paired games, no earlier than 24 hours after the last
included game's completion. Missing trustworthy completion timestamp or outcome
blocks scoring, not the already-recorded freeze. Do not substitute kickoff plus
an assumed game duration. Persist exact outcome versions and corrections as new
evaluation versions; never overwrite original freeze or scoring evidence.

Calculate MAE/RMSE/bias, candidate CRPS/interval coverage/width, stages, and
paired/broader coverage. V4 uncertainty may be unavailable; report it as such.
Maintain an explicit ledger of qualifying and nonqualifying slates with reasons.
Count a candidate/season/week slate once, and ensure corrected evaluations cannot
increment the counter again. Preserve old and current evaluation-version links.

**Acceptance:** Scoring and counters independently reproduce from immutable refs.
Outcome corrections retain history and never manufacture an earlier freeze.

### Task 5 — Rehearse, independently verify, and publish readiness

Run a full historical future-like rehearsal using exact source and model refs,
with `diagnostic_only` permanently preventing prospective counting. Exercise
readiness → forecast/state replay → freeze validation → stabilized scoring →
counter reconstruction, including deliberate negative cases. No public outputs
or serving writes. The verifier must recompute timing, source availability,
population, predictions, scores and ledger counts from source artifacts.

Then perform a read-only real-season readiness assessment using currently
available exact inputs. Produce a ready or blocked report with concrete reasons;
do not fix data/model semantics silently. Update a V5 shadow runbook with exact
commands, refs, cutoffs, failure recovery, counter rules and the contract 06 handoff.
This does not create a scheduler or start future slate collection automatically.

## Testing strategy

Run common computational gates plus exact T−2h/T−1h boundaries, 24-hour scoring
boundaries, source-time contradictions, current-week outcomes, unavailable
preseason inputs, failed mandatory versus optional fallback, missing scores,
cancellations/postponements, unknown final timestamps, duplicate counts,
corrections, immutable collision, and candidate-change reset tests. Independently
verify a complete diagnostic rehearsal and idempotent rerun.

## Risks, definition of done, and amendments

Live availability can fail despite excellent reconstructed historical coverage.
Do not mark live-ready based solely on engineering completion. This task is not
permission to change V4's freeze schedule to make a pairing qualify.

- [ ] Tooling, schemas, runbook and complete diagnostic rehearsal are independently verified.
- [ ] Real-season readiness report lists exact available inputs/fallbacks/blockers.
- [ ] No rehearsal contributes to prospective counts; zero production/serving writes.
- [ ] Required checks/docs/session log complete and engineering status recorded.

This contract may close its tooling work with a verified **blocked** readiness
report, but its live-readiness dependency remains unmet and 06 cannot collect
eligible evidence. A material source/model change requires a planning amendment;
mechanical readiness follow-up preserves this contract's rules.

## Execution decomposition (2026-09-17)

The implementation is split into three dependency-ordered phases without
changing this umbrella contract's goal, tasks, gates, or definition of done:

1. [V5-05A: Readiness validation and frozen replay](../2026-09-17/04-v5-05a-readiness-and-replay.md)
   implements Tasks 1–2: all six shadow schema contracts, `shadow_v1.yaml`,
   source-availability validation with a verified ready/blocked report, and
   frozen-algorithm replay proof, certified with its own Preview
   preflight/apply/verify cycle.
2. [V5-05B: Shadow freeze, scoring, and evidence ledger](../2026-09-17/05-v5-05b-freeze-score-ledger.md)
   implements Tasks 3–4: measured immutable freezes, outcome-versioned
   scoring, and the evidence ledger/counter, certified with its own Preview
   preflight/apply/verify cycle. Blocked on Implemented 05A.
3. [V5-05C: Diagnostic rehearsal, verification, and runbook](../2026-09-17/06-v5-05c-rehearsal-verification-runbook.md)
   implements Task 5: independent shadow verifier, full historical diagnostic
   rehearsal, refreshed real-season readiness report, and the V5 shadow
   runbook with Contract 06 handoff. Blocked on Implemented 05B.

All three phases are Draft pending approval. The user approved the
decomposition on 2026-09-17, authorizing 05A execution on approval of its
contract; 05B remains Draft until 05A has a clean committed SHA and reviewed
deterministic preflight evidence, and 05C remains Draft until 05B certifies.
V5-05 remains Approved and is not complete until 05C certifies.

## Umbrella closure (2026-09-18)

All three phases are Implemented and Preview-certified:
05A (`shadow-v1-20260917-cd07d8b-05a`), 05B freeze/score
(`shadow-v1-20260918-73e8e9b-05b-freeze`,
`shadow-v1-20260918-7aec1c8-05b-score`), 05C rehearsal
(`shadow-v1-20260918-6dc87e0-05c`, 7/7 cases, qualifying 0). The independent
verifier confirms every artifact end-to-end from source datasets. The verified
real-season readiness remains `blocked` (no 2026 measurement/team-state
parents): tooling is complete, Contract 06 cannot yet collect eligible
evidence. Umbrella V5-05 is **Implemented**.

## Historical-first eligibility clarification (2026-09-18)

This implemented contract certifies tooling behavior only. The 05C rehearsal's
predictions are permanently `diagnostic_only`, so neither that rehearsal nor a
retrospective replay establishes forecast quality, live readiness, or
prospective evidence. Contract 04/04B is reopened pending independent
computational verification; therefore 05 cannot establish a certified forecast
parent. Contract 06 is deferred behind Contracts 10-12, explicit user acceptance
of historical readiness, and a later re-reviewed live-application path.

## Amendment 2 — Versioned 2026 live candidate interface (2026-09-22)

**Reason:** Contract 09's outcome-free 2026 forecasts use a distinct manifest
and row schema. The original Contract 05 source loader and independent verifier
were sealed to the historical candidate identity and a fixed historical
population.

**Revised approach:** Contract 05 now accepts the explicit
`data_first_live_forecast_manifest_v1` through a versioned adapter in readiness,
freeze, scoring, and independent verification. Live readiness checks the exact
Contract 07/08 ancestry, requested 2026 schedule coverage, outcome-free
prediction schema, and pre-kickoff timing. A blocked report retains its precise
missing dependency. Freeze and score continue to require verified readiness,
measured pre-kickoff availability, complete paired coverage, and stabilized
outcomes; `diagnostic_only` remains permanently excluded.

**Impact:** The historical Contract 05 path and certified diagnostic artifacts
remain unchanged. The adapter is code-ready only: no Week 4 readiness or
certification was performed. Contract 09 still requires stabilized Week 4
finals and fresh, independently verified 07/08 Preview manifests. Contract 06
remains gated on verified `ready`.
