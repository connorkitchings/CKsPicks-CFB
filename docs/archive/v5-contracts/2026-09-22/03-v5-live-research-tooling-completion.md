# V5 Live Research Tooling Completion

- **Status:** Implemented — code readiness only; live certification remains gated
- **Created:** 2026-09-22
- **Planner:** Sol
- **Approval source:** User explicitly authorized this plan with “PLEASE IMPLEMENT THIS PLAN” and “proceed” on 2026-09-22.
- **Implementation log:** `session_logs/2026-09-22/11-v5-live-research-tooling-completion.md`
- **Commit policy:** May be committed with implementation; user executes Git operations manually.

## Goal

Make the V5 research program code-ready for the remaining 2026 live forecast,
readiness, shadow, and prospective-evidence sequence. Provide a separately
verifiable live forecast interface, carry that identity through the existing
shadow gates, and implement the Contract 06 evidence operations. The work is
complete when the code and tests can process the exact refreshed parents and
future slates without changing V4 or using 2026 outcomes to tune V5.

This is a code-readiness contract. It does not claim Week 4 finals have
stabilized, certify a refreshed 07/08 lineage, or imply that six prospective
slates can be collected in one session.

## Current State

- V4 is the 2026 production champion. V5 remains Preview-only and
  `production_activation_authorized: false`.
- Contracts 07 and 08 are implemented through Week 3. The Week 4 refresh under
  new run identities is required before Contract 09 may generate current-state
  forecasts or readiness for Week 5.
- Contract 09's historical runner and `data_first_forecast_prediction_v1`
  require outcomes. The historical runner is sealed to historical parents and
  recomputes selection, so it cannot represent future live predictions.
- Contract 05 readiness and shadow code pins the old forecast and rating
  manifests. It must accept the new live forecast through a versioned interface
  without changing the historical boundary or timing/population rules.
- Contract 06 defines the evidence requirements, but the prospective evidence
  execution/reporting layer is incomplete. Reusable policy code exists in
  `src/cks_picks_cfb/ratings/prospective.py`.
- The worktree was clean on `main` at `3013e28` during planning. The task needs
  Preview R2 only for later certified runs. No live forecast/readiness/evidence
  apply is included in this code-readiness implementation.

## Proposed Approach

Implement an additive, versioned live lane. Add a live forecast contract,
producer, and independent verifier. Let the existing shadow operations consume
either their sealed historical identity or the explicit new live contract via a
versioned adapter; preserve historical behavior and all freeze, scoring, source
timing, and minimum-coverage gates. Add Preview-only Contract 06 evidence
operations that bind immutable forecast/readiness/freeze/evaluation/quote
parents and derive eligibility independently.

Keep certification separate from coding. The later operator sequence remains:
stabilized Week 4 finals → fresh 07/08 identities through Week 4 → Contract 09
forecast and Week 5 readiness preflight/apply/verify/repeat → Contract 06
pre-kickoff freeze and prospective weekly cadence.

## Scope

### Included

- Contract 09 amendment and a separate outcome-free live forecast dataset and
  manifest interface.
- Preview-only live forecast producer and independent verifier.
- Versioned Contract 05 integration for readiness, frozen replay, freeze, and
  scoring with live forecast identities.
- Contract 06 prospective attempt ledger, eligibility derivation, report,
  authentic-quote diagnostic, and recommendation operations.
- Focused tests and current documentation/runbook updates for the interfaces
  and code-readiness boundary.

### Excluded

- Week 4 parent refresh or any R2 apply/verification run in this implementation
  task; those require stabilized finals and fresh immutable identities.
- Actual Week 5 certification before its refreshed parents exist, and future
  prospective freezes or a six-slate recommendation before eligible slates
  exist.
- Refitting, reselecting, or tuning any V5 quantity on 2026 outcomes.
- V4 model/bundle, Neon, serving schema, production publication, web app,
  betting, staking, new provider acquisition, or recurring automation changes.

## Affected Components and Contracts

- [Contract 09](../../../plans/2026-09-18/09-v5-2026-forecast-and-readiness.md): amendment
  for the live prediction interface, exact parent roles, and future execution
  gate.
- `src/cks_picks_cfb/data/` and `src/cks_picks_cfb/forecast/`: live forecast
  record contract, application logic, and verifier-owned reconstruction.
- `scripts/research/` and `conf/research/data_first_football_v1/`: Preview
  preflight/apply/verify CLI and frozen live configuration.
- `src/cks_picks_cfb/data/data_first_shadow_v1.py`, forecast shadow logic, and
  `scripts/research/run_v5_shadow_*.py`: versioned live candidate adapter while
  preserving sealed historical defaults.
- `src/cks_picks_cfb/ratings/prospective.py` and new research evidence modules
  and runners: immutable attempt/evaluation ledger, independent count, reports,
  authentic-quote diagnostic, and recommendation.
- Contract 06 and current roadmap/runbook documentation: code-ready versus
  certified evidence status.

No public serving API, database schema, catalog registration, or migration is
introduced.

## Implementation Tasks

### Task 1 — Amend Contract 09 and define the live forecast interface

**Files:** Contract 09; new live forecast schema/contract module under
`src/cks_picks_cfb/data/`; live forecast configuration under
`conf/research/data_first_football_v1/`.

**Changes:**

- Add an additive outcome-free `data_first_live_forecast_prediction_v1` record
  keyed by run, season, week, game, and target. Store forecast mean, variance,
  interval, offset, completed-game stage, timing class, and model/state/source
  references. Do not add `actual`, absolute error, or CRPS fields.
- Define a signed `data_first_live_forecast_manifest_v1` binding code/config,
  exact refreshed 07 and 08 manifest URIs and raw checksums, the frozen 11C
  final-fit model/calibration identity, complete schedule population, source
  cutoff/timing evidence, immutable schedule source URI and raw checksum,
  output refs/counts/digests, and
  `production_activation_authorized: false`.
- Bind the bridge to `forecast-v1-20260921-5afd577-11c`, the shared expanding
  horizon, reference alpha 10.0, through-2025 final-fit heads, and final
  calibration variances. Do not load 2026 actuals into application or fitting.
- Amend Contract 09 to name the live schema and verifier and retain Week 4
  stabilized finals plus fresh 07/08 verification as the apply gate.

**Acceptance criteria:** The live schema accepts complete pregame predictions
without outcome fields; rejects 2020 and historical selection roles; and binds
all required model, state, schedule, and source identities. Historical forecast
schemas and manifests validate unchanged.

**Validation:** Focused contract/schema tests for missing, mismatched, or
tampered parents; absence of outcome fields; fixed bridge identity; full FBS
schedule membership; and activation flag false.

### Task 2 — Implement live forecast preflight/apply and independent verification

**Files:** New live forecast producer/verifier modules under
`src/cks_picks_cfb/forecast/`; runner and verifier CLIs under
`scripts/research/`; focused forecast tests.

**Changes:**

- Reconstruct application features from certified 08 team states, completed
  game counts, scoring events, and schedule. Use the existing earlier-only
  non-offense offset procedure without reading the target game's outcome.
- Add default dry-run preflight and explicit Preview apply. Apply requires the
  common committed-code/clean-tracked-worktree gate, exact parent manifests,
  and identical preflight membership/partition digests. Write immutable output
  partitions and publish the terminal manifest last.
- Add verifier-owned reconstruction that does not import the producer or
  historical model fitting/selection path. Verify raw parent bytes, checksums,
  bridge parameters, timing, population, partitions, predictions, signatures,
  and output digests. Repeated apply/verify returns `already_applied` with no
  writes when identity and bytes match; identity collisions fail closed.
- Require the refreshed 07/08 parents at apply time. Code tests may use
  synthetic parents, but must not create or certify operational artifacts.

**Acceptance criteria:** Forecasts are deterministic, complete for the declared
2026 population, generated without 2026 outcome fitting, and independently
reconstructed. Historical runner and 11C artifacts remain unchanged.

**Validation:** Focused tests for frozen parameter fidelity, offsets and
pregame cutoff, parent rejection, synthetic tampering, deterministic outputs,
verifier import boundary, CLI help, and non-mutating dry-run. Do not run R2
apply in this task.

### Task 3 — Add versioned live forecast support to Contract 05 shadow operations

**Files:** Shadow data contract and forecast readiness/replay modules; relevant
`run_v5_shadow_*` runners/verifier; shadow tests; Contract 05/09 interface docs.

**Changes:**

- Preserve the existing historical candidate contract and defaults. Add a
  distinct live-candidate schema/version that verifies the live forecast
  manifest plus its exact refreshed 07/08 ancestry.
- Thread that candidate adapter through readiness, frozen replay, freeze, and
  score parent validation. Preserve strict as-of/source availability, earlier
  completed-week updates, first-kickoff timing, measured object availability,
  paired population, 40-game minimum, 24-hour outcome stabilization, and
  diagnostic-only exclusion rules.
- Readiness records must identify each required source, timing class, and
  blocked reason. A valid `blocked` report names its exact missing dependency;
  only independently verified `ready` satisfies Contract 09/06 handoff.
- Do not allow live forecast rows with outcomes, diagnostic rehearsals, or
  reconstructed untimestamped sources to count as prospective evidence.

**Acceptance criteria:** Historical candidate paths remain regression
identical. Live candidates pass only with exact eligible parents. Existing
timing and population gates reject late, incomplete, or unverifiable freezes;
diagnostic runs never qualify.

**Validation:** Historical regression tests plus focused live-parent,
readiness-blocker, source timing, freeze timing, coverage, score stabilization,
and diagnostic classification tests.

### Task 4 — Implement Contract 06 evidence operations

**Files:** New evidence contract/calculation modules under
`src/cks_picks_cfb/ratings/`; Preview research runners/verifier under
`scripts/research/`; evidence configuration; Contract 06 documentation.

**Changes:**

- Implement immutable attempt dispositions and an append-only correction link
  for freezes/evaluations. Independently derive the protected qualifying count
  from verified candidate identity, ready report, pre-kickoff freeze,
  population, paired coverage, and stabilized outcome evaluation. Each
  candidate/season/week counts at most once; diagnostic, late, incomplete, or
  unverifiable attempts remain recorded but excluded.
- Produce outcome-versioned football reports for both targets, candidate
  calibration and coverage, completed-game stages, paired and broader
  populations, exclusions, and operational reliability. Corrections create new
  linked evaluation versions and cannot increment the count twice.
- Add a separate authentic-quote diagnostic after football evaluation. Bind
  provider, quote IDs, capture/effective timestamps, cutoff, and declared
  population. Report omissions explicitly; quote presence/removal cannot change
  football results or slate eligibility. Do not acquire a provider or create a
  betting recommendation.
- At six qualifying slates, issue exactly one existing Contract 06 category:
  `retain_v4`, `continue_shadowing`, or `prepare_phase7`. Before six, issue a
  precise continued-shadow status. Include paired metrics/intervals,
  calibration, stage/coverage and limitations; a Phase 7 plan is conditional on
  `prepare_phase7` and activation remains out of scope.
- Publish only to the Preview research namespace with immutable manifests,
  exact parent roles, digests, eligibility and activation false.

**Acceptance criteria:** Eligibility is reconstructed rather than trusted from
a stored counter; quote diagnostics cannot influence football counts/results;
outcome corrections preserve prior evidence; recommendation categories follow
Contract 06 and do not create new thresholds.

**Validation:** Synthetic evidence tests for duplicates, late freezes, paired
coverage below 40, missing final timestamps, <24-hour stabilization, corrected
outcomes, missing/untimestamped quotes, quote perturbation invariance,
diagnostic-only exclusions, and all three recommendation branches.

### Task 5 — Close documentation and implementation record

**Files:** Contract 09 and 06; canonical data-first roadmap; focused authority
tests if current-status wording requires them; implementation session log.

**Changes:**

- Record this code-ready interface and its test evidence. State that live apply
  and readiness remain gated on Week 4 finals and fresh verified 07/08 parents;
  six-slate evidence remains future prospective work.
- Keep Contract 09 In Progress until live forecast and readiness are certified.
  Keep Contract 06 Approved/In Progress according to its actual evidence
  lifecycle; code completion alone never counts a slate.
- Update this contract status only when all scoped code and checks pass. Do not
  claim Preview certification or change artifact identities from synthetic
  testing.

**Acceptance criteria:** Active documentation accurately separates code
readiness, live certification, prospective collection, and conditional
promotion review. User-controlled Git operations remain unstaged/uncommitted.

**Validation:** Repository tests relevant to changed components, Ruff checks,
`uv run python contracts/validation.py`, `uv run mkdocs build --strict --quiet`,
and `git diff --check`.

## Testing Strategy

Use focused unit tests for schemas, lineage, timing, feature construction,
forecast determinism, independent reconstruction, eligibility, reporting, and
quote invariance. Add regression tests demonstrating historical 04/05 parent
paths remain stable. Run CLI help and synthetic no-R2 preflight tests. Run
required repository contract/docs checks at the end. Never add tests that
require external data or write `./data/`; any operational data run must use
the configured Preview R2 backend and is outside this code-readiness contract.

## Risks and Edge Cases

- Week 4 finals can lag. No new forecast apply may proceed on Weeks 0–3 parents
  as a substitute for the required refresh.
- The live candidate needs an outcome-free row interface. Reusing the historical
  prediction schema would admit null/outcome ambiguity and is prohibited.
- Contract 05 parent checks are intentionally sealed to historical refs; live
  support must be versioned so existing artifacts and verifier boundaries do
  not change silently.
- Forecast correctness can be established with synthetic parents and tests,
  but operational certification still requires exact Preview manifests,
  committed code, independent verification, and idempotent repeat.
- Quote absence cannot invalidate football evidence or shrink its declared
  population. Future outcomes and quotes are unavailable during this session.

## Definition of Done

- [x] Contract 09 has an approved live-interface amendment and a code-readiness implementation amendment.
- [x] Outcome-free live forecast schema, Preview producer, independent verifier, and idempotent repeat path are implemented and tested.
- [x] Contract 05 readiness/replay/freeze/score accept the versioned live candidate while preserving historical behavior and timing, coverage, stabilization, and diagnostic gates.
- [x] Contract 06 attempt ledger, eligibility derivation, correction-linked reports, independent verifier, quote diagnostic, and recommendation operations are implemented and tested.
- [x] Docs distinguish code readiness from the Week 4 refresh, live certification, and six-slate prospective evidence.
- [x] Focused tests, Ruff checks, contract validation, strict MkDocs, and `git diff --check` pass.
- [x] Implementation log is complete; Contract 09 remains In Progress pending operational certification, and Contract 06 remains Approved pending verified `ready`.
- [x] No live apply, production/Neon/web write, V4 modification, or 2026-outcome tuning occurred.

## Implementation result (2026-09-22)

The scoped implementation is complete for code readiness. The live forecast and
Contract 06 runners have synthetic immutable publication/repeat tests, and the
independent verifiers reconstruct outputs without importing their producers.
The live Contract 05 adapter reconstructs exact `blocked` candidate coverage
reasons as well as valid `ready` coverage. Focused and documentation regressions
pass, as do Ruff, contract validation, strict MkDocs, and `git diff --check`.
Follow-up review also bound every 2026 schedule fact to the certified 07
population, rejected forecast verification identity drift, and required apply
to match the complete reviewed partition plan before writing output. It also
removed the stale Weeks 0–3 Contract 07 run-ID pin from the Contract 08 runner
and verifier, so a refreshed Week 4 measurement identity can flow through the
approved replay while remaining bound by exact URI and raw checksum.

No live preflight or apply was run. Contract 09 certification still requires
stabilized Week 4 finals and newly refreshed, independently verified Contract
07/08 manifests. Contract 06 has no qualifying slates and cannot start until
Contract 09's exact forecast and Contract 05 readiness verify `ready`. V4
remains production champion.

## Amendments

### Amendment 1 — Contract 08 refreshed-parent compatibility (Terra, 2026-09-22)

**Reason:** Follow-up review found that the Contract 08 runner and verifier
still pinned the earlier Weeks 0–3 Contract 07 run ID, which blocked the new
immutable Week 4 parent required by this plan.

**Revised implementation:** Admit a signed Preview Contract 07 2026 measurement
manifest with its certification digest and complete output set under its new
immutable run ID. Contract 08 continues
to bind the exact manifest URI and raw checksum into its replay identity and
independently verified terminal lineage. Contract 09 retains the Week 4
stabilized-finals gate before any live forecast.

**Impact:** This closes an implementation compatibility gap without changing
the rating candidate, replay mathematics, historical artifacts, or future
operational gates. Contract 08 records the interface amendment in its own
contract.
