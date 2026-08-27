# Phase 5 — Protected Prospective Evidence Operations

- **Status:** In Progress
- **Created:** 2026-08-26
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact
  plan in Codex on 2026-08-26.
- **Implementation log:**
  `session_logs/2026-08-26/07-phase5-protected-prospective-evidence.md`
- **Commit policy:** Separate plan commit required before implementation.

## Goal

Operate frozen rating candidate v1 unchanged through protected 2026 evidence
windows. For every eligible slate, Phase 5 must create one timestamp-authentic
pregame freeze and one complete postgame score in the Preview-only research
lane, paired to the exact frozen production V4 run. After six eligible slates,
it must publish an immutable cumulative evidence manifest without making a
promotion decision.

Observable success means:

- every counted slate is a normal-coverage 2026 week at or after Week 1;
- the candidate, state equations, inputs, model refs, policy, and relevant code
  identity were frozen before outcomes began;
- both V4 and candidate predictions were frozen at least one measured hour
  before the slate's earliest kickoff;
- the candidate freeze contains exact schedule/V4 coverage, pregame states,
  predictive uncertainty, and complete lineage with no market inputs;
- postgame evidence contains authoritative outcomes and complete paired V4
  coverage, apart from verified cancellations;
- identical retries are byte-identical no-ops, while late, partial, stale, or
  conflicting attempts remain diagnostic-only; and
- six eligible scored slates exist under one unchanged prospective lane before
  Phase 5 is marked `Implemented` or a promotion review becomes plan-eligible.

## Current State

Phases 1–4 are implemented. Phase 1 v3 corrected PPSO to deterministic true
drive points; Phase 2 v2 rebuilt the unchanged rating equations; Phase 3 v3
froze `negative_binomial_scores` candidate v1; and Phase 4 implemented and
rehearsed the isolated weekly shadow lifecycle.

Frozen identities entering Phase 5:

- candidate design:
  `503d422c22bc357bfb25b7fe27f8f9c5e14098a1d2748e71d58b043d5a74e6fe`;
- final score-model version `071f4de17b4b351e74e0a670`, content SHA-256
  `b941a1737ced28543c939496012c742bbb37fe2bb2c3fda57cf45a5038f86d3b`;
- frozen prediction version `75e9a9cc7e942823bde56a2a`, content SHA-256
  `226931b625769f008e91458afb984026c9976efba323030d408838df56be69b3`;
- shadow-operations design
  `584f3f5cd43653745b4f3e4eed4f5437444fb5997366e574f22f3bf05ec4172e`;
- production V4 model `week0-2026-v4-strict-20260818-r2`, bundle SHA-256
  `72429375bfa8c434c7d6fcb455bb9e22333af8c929c0cc3e832f0b80787bf25c`;
  and
- Phase 4 rehearsal summary SHA-256
  `b755b585914d2f36b6ff93edba8eb520c500cd0e6ea416a58f47ee4fbdc33e31`
  covering all 15 historical weeks with a byte-identical rerun.

The existing Phase 4 CLIs already enforce Preview-only writes, explicit
production V4 run IDs, immutable canonical weekly paths, exact candidate
loading, pre-kickoff requested cutoffs, outcome/V4 completeness, cancellation
reasons, and collision rejection. Before live use, Phase 5 must close these
remaining operational gaps:

1. `prepare-week` builds byplay and drives internally but publishes only the
   reconciled team-game ref; the shadow freeze has no authoritative run-local
   byplay/drives ref set to consume.
2. Freeze eligibility uses caller-supplied `as_of`, not the measured wall-clock
   completion time, and parent validation checks manifest `as_of` but not
   object creation/source-capture time. A late command must never succeed by
   supplying an earlier timestamp.
3. The candidate slate is selected from schedule rows without proving exact
   equality to production V4's complete frozen eligible-game set.
4. Pregame measurement/team states are reconstructed in memory but are not
   persisted, so later rating-stability and responsiveness review lacks a
   first-class immutable state artifact.
5. Cancellation waivers require a missing outcome but are not checked against
   the latest authoritative schedule status.
6. No cumulative auditor currently proves that multiple weekly artifacts use
   one unchanged candidate/policy/code lane or counts the six eligible slates.

R2 remains authoritative. Preview Neon catalog registration is optional and
retriable. Production Neon and R2 are read-only dependencies for V4 proof;
Phase 5 has no production mutation path.

## Proposed Approach

Keep the Phase 4 shadow design and candidate config byte-for-byte unchanged.
Add a separate `prospective_evidence_v1` policy whose hash governs operational
eligibility without changing the candidate or shadow design identity. Extend
the existing Preview preparation and shadow CLIs only where live evidence
requires stronger lineage, clock, slate, state, and cancellation contracts.

The weekly sequence is manual and fail-closed:

1. the existing production workflow publishes and freezes V4 under its own
   authority;
2. Preview `prepare-week` materializes an immutable, run-local input ref set;
3. a read-only shadow preflight resolves exact refs, V4 proof, schedule keys,
   timing, and code/policy identity;
4. one candidate freeze completes at least 60 minutes before earliest kickoff;
5. after every non-cancelled game has an authoritative final, one score writes
   paired evidence; and
6. the cumulative auditor rebuilds the evidence count exclusively from
   canonical weekly manifests.

Target execution is two hours before earliest kickoff; the hard evidence gate
is 3,600 seconds measured from successful candidate-freeze completion. A miss
does not weaken the gate: that week is diagnostic-only and does not count.

Phase 5 has operational gates, not statistical promotion gates. It reports the
pre-specified rating, accuracy, bias, residual, and interval metrics after each
score, but no result may tune candidate v1, stop the lane early, or trigger
promotion. Promotion remains a separate approved contract after six slates.

## Scope

### Included

- A separate immutable prospective-evidence policy and policy hash.
- Run-local Preview refs for byplay, drives, reconciled team game, schedule,
  outcomes, and source reconciliation.
- Authentic wall-clock, source-capture, manifest-creation, and data-cutoff
  validation.
- Exact production V4/schedule/candidate key equality before canonical freeze.
- Preview-only immutable pregame measurement-state and team-state artifacts.
- Canonical prospective freeze, score, evidence, and cumulative audit schemas.
- Explicit verified cancellation handling and diagnostic-only failure paths.
- Manual Week 1-or-later execution and continued operation until six eligible
  slates are scored under one unchanged lane.
- Documentation, runbook, tests, validation, weekly session logs, and Phase 5
  completion evidence.

### Excluded

- Any model retraining, recalibration, feature change, prior change, state
  equation change, uncertainty change, or candidate selection.
- Phase 3 reruns or use of 2026 outcomes to change candidate v1.
- Production V4 publish/freeze implementation, production R2 writes, Neon
  production writes, schema changes, activation, public APIs, publication,
  markets, residual ML, betting decisions, or rollback selection.
- Automated schedulers. Every prospective freeze remains an explicit operator
  action with a recorded go/no-go preflight.
- Statistical promotion, market-value analysis, challenger research, or Phase
  6/7 implementation.
- Retrospective Week 0 or late Week 1 evidence.

## Affected Components and Contracts

- `conf/ratings/shadow_operations_v1.yaml` — read and checksum-pin only; it must
  not change.
- `conf/ratings/prospective_evidence_v1.yaml` — new operational policy, separate
  from the shadow design.
- `scripts/pipeline/build_team_game_dataset.py` — emit an immutable ref set for
  all preaggregation outputs while preserving the existing team-game ref.
- `src/cks_picks_cfb/ops/__main__.py` — expose that ref set from `prepare-week`.
- `src/cks_picks_cfb/ratings/prospective.py` — new policy, eligibility,
  cumulative-audit, and evidence-lane contracts.
- `src/cks_picks_cfb/ratings/shadow.py` — shared freeze/score validation
  additions only; candidate math remains unchanged.
- `scripts/pipeline/build_rating_shadow_freeze.py` — live preflight, authentic
  clock enforcement, exact slate pairing, and state materialization.
- `scripts/pipeline/build_rating_shadow_score.py` — authoritative cancellation
  status, scoring clock, and v2 evidence lineage.
- `scripts/pipeline/audit_rating_prospective_evidence.py` — new cumulative
  canonical evidence auditor.
- `tests/test_data_lake.py`, `tests/test_ops_state_machine.py`,
  `tests/ratings/test_shadow.py`, and a new
  `tests/ratings/test_prospective_evidence.py`.
- New Preview-only contracts:
  `rating_shadow_freeze_manifest_v2`,
  `rating_shadow_measurement_states_v1`,
  `rating_shadow_team_states_v1`,
  `rating_shadow_score_report_v2`,
  `rating_shadow_evidence_v2`, and
  `rating_prospective_evidence_summary_v1`.
- Canonical weekly prefix remains
  `artifacts/research/rating-successor/shadow-v1/<shadow-design>/ops/season=<season>/week=<week>/`.
- Cumulative summaries live under
  `artifacts/research/rating-successor/shadow-v1/<shadow-design>/prospective-evidence-v1/<policy-sha>/through-week=<week>/summary.json`.
- `docs/ops/rating_shadow_operations.md`, `docs/modeling/evaluation.md`,
  `docs/modeling/rating_system_requirements.md`, `docs/planning/roadmap.md`,
  `docs/plans/index.md`, and weekly session logs.

## Implementation Tasks

### Task 1 — Freeze the prospective evidence policy

**Files:**

- `conf/ratings/prospective_evidence_v1.yaml`
- `src/cks_picks_cfb/ratings/prospective.py`
- `tests/ratings/test_prospective_evidence.py`

**Changes:**

- Define and validate a policy containing exact shadow config/design, candidate
  refs/SHAs, V4 identity, season `2026`, first eligible week `1`, normal
  coverage minimum `40`, target lead `7,200` seconds, hard lead `3,600`
  seconds, and required eligible slate count `6`.
- Hash the canonical policy independently. Never add Phase 5 fields to
  `shadow_operations_v1.yaml`, because that would create a new shadow design.
- Freeze one relevant implementation identity before the first canonical
  prospective write. Its manifest must include the committed Git SHA and
  SHA-256 of the policy plus every source file that can change input
  validation, state construction, prediction, serialization, or scoring.
- Define lane-change rules before outcomes:
  - a candidate, state, feature, prediction, input-policy, or freeze-code change
    creates a new lane and resets the six-slate count;
  - a scorer/auditor-only mechanical change requires an approved amendment and
    versioned recomputation from immutable freezes, but does not reset the
    count when it provably cannot change frozen predictions; and
  - documentation-only changes do not alter the lane.

**Acceptance criteria:**

- The loaded policy reproduces every expected identity and rejects a changed
  shadow config, model/prediction ref, V4 bundle, threshold, season, or count.
- Policy hashing is deterministic and separate from the shadow design hash.
- The lane cannot start from dirty/untracked relevant code or an uncommitted
  implementation identity.

**Validation:**

- Unit tests for parsing, hashing, exact pins, relevant-file hashing, and each
  lane-reset class.

### Task 2 — Publish complete run-local rating input refs

**Files:**

- `scripts/pipeline/build_team_game_dataset.py`
- `src/cks_picks_cfb/ops/__main__.py`
- `tests/test_ops_state_machine.py`
- focused pipeline tests for `build_team_game_dataset.py`

**Changes:**

- Add an optional immutable output-ref-set URI to the existing preaggregation
  builder. It records exact `byplay`, `drives`, `reconciled_team_game`, and
  `source_reconciliation` refs and SHAs from the same build.
- Make `prepare-week` write this ref set beneath its run prefix alongside games
  and outcomes. Preserve the existing reconciled-team-game ref and every V4
  preparation behavior.
- Treat a partial ref set, a companion ref pointing to another build/as-of, or
  a changed immutable alias as a reconciliation failure. An identical retry
  verifies and returns the existing set.
- Require all inputs to use the same Preview environment, season, requested
  cutoff, source lineage, and schedule policy. Phase 5 never discovers a drive
  artifact by listing a mutable prefix or selecting “latest.”

**Acceptance criteria:**

- A successful Preview `prepare-week` exposes exact byplay and drives refs
  needed by true PPSO without querying the catalog for “latest.”
- Every ref-set member exists, checksum-verifies, and belongs to the same
  prepared run; missing or crossed refs fail before shadow writes.
- Existing production/V4 behavior and the original team-game ref remain
  backward compatible.

**Validation:**

- Fixture integration tests for complete, identical-retry, partial, crossed,
  wrong-environment, wrong-season, and wrong-cutoff ref sets.
- Existing prepare/publish state-machine tests remain green.

### Task 3 — Harden and materialize the authentic pregame freeze

**Files:**

- `src/cks_picks_cfb/ratings/prospective.py`
- `src/cks_picks_cfb/ratings/shadow.py`
- `scripts/pipeline/build_rating_shadow_freeze.py`
- `tests/ratings/test_shadow.py`
- `tests/ratings/test_prospective_evidence.py`

**Changes:**

- Add a read-only `--preflight-only` mode that resolves the exact prepared ref
  set, production V4 run, eligible schedule keys, earliest kickoff, current
  wall clock, code manifest, and policy hash without writing R2 or Neon.
- Record requested data `as_of`, preflight time, freeze start, freeze completion,
  V4 `frozen_at`, V4 `data_as_of`, earliest kickoff, and both requested and
  measured lead. Reject future/backdated `as_of`, any parent created after
  freeze start, any source capture or event after `as_of`, and any freeze that
  completes with less than 3,600 seconds of measured lead.
- Expand the production V4 read-only query to pin `expected_games`,
  `predicted_games`, validation metadata, and its exact frozen/scored state.
  Require both V4 `frozen_at` and `data_as_of` to precede earliest kickoff by
  at least the same 3,600-second hard lead required of candidate completion.
  Define the eligible candidate slate from the frozen V4 game IDs joined to
  authoritative schedule rows. Require V4 `expected_games == predicted_games`,
  exactly margin/total V4 rows per game, unique valid schedule keys, no unknown
  games, and complete candidate coverage of the identical keys.
- Build 2026 observations from completed games strictly before `as_of`; target
  slate actuals remain null. Prove that the target-slate cumulative snapshot
  produces the same target states as assembling all current-season pregame
  snapshot boundaries, because Phase 2 uses a fixed offseason prior plus
  cumulative measurement exposure rather than within-season recursive priors.
- Persist the exact target pregame component and team states as immutable
  Preview datasets. Pin them, the complete current raw ref set, historical
  snapshot/terminal refs, model ref, V4 proof, code manifest, and policy hash
  in `rating_shadow_freeze_manifest_v2`.
- Extend the canonical freeze artifact-set check to require the manifest,
  predictions ref, measurement-states ref, and team-states ref. Failed gates
  may write content-addressed diagnostics only; no canonical member may confer
  freeze status until the full set exists.
- Preserve positive finite uncertainty, interval ordering, score covariance,
  two targets per game, no market fields, and exact frozen candidate math.

**Acceptance criteria:**

- The preflight is side-effect free and produces a complete operator go/no-go
  packet with exact commands and identities.
- A canonical freeze is impossible after the hard lead deadline, even with a
  backdated requested cutoff.
- Candidate, V4, schedule, state, and prediction keys are exactly equal.
- State artifacts are reproducible, complete for both teams in every game,
  outcome-free, market-free, and fully lineage-pinned.
- The identical freeze invocation is a verified no-op; any changed input,
  timestamp, policy, code identity, or partial artifact set fails closed.

**Validation:**

- Clock-boundary tests using an injected clock, including preflight that
  crosses the deadline before completion.
- Parent creation/capture/cutoff, backdating, target-outcome, slate-equality,
  V4-count, state-equivalence, state-coverage, leakage, collision, and
  production-write-prohibition tests.
- A real read-only Week 1 preflight only after the prepared inputs and frozen
  production V4 run exist.

### Task 4 — Harden authoritative final scoring

**Files:**

- `src/cks_picks_cfb/ratings/prospective.py`
- `src/cks_picks_cfb/ratings/shadow.py`
- `scripts/pipeline/build_rating_shadow_score.py`
- `tests/ratings/test_shadow.py`
- `tests/ratings/test_prospective_evidence.py`

**Changes:**

- Require explicit authoritative games and outcomes refs from one postgame
  Preview preparation/close run. Validate their dataset identities, content
  SHAs, season, cutoff, creation times, and complete frozen-game coverage.
- Record outcome cutoff, source capture time, score start/completion time, and
  the exact freeze/state/prediction/V4 identities in every report and evidence
  row. Reject backdated scoring cutoffs or parents created after score start.
- Accept a cancellation waiver only when the game was in the frozen slate, has
  no completed outcome, and its latest authoritative schedule status is
  `cancelled`, `canceled`, or `postponed`. Preserve game ID, status, reason,
  schedule ref/SHA, and verification time. A fully cancelled slate remains
  diagnostic-only.
- Require exactly two paired V4/candidate targets for every non-cancelled game.
  Incomplete outcomes, missing V4 rows, duplicate keys, corrections, or partial
  artifacts produce diagnostics but no canonical evidence ref.
- Score only after all finals are present and a 24-hour stabilization interval
  has elapsed after the latest frozen scheduled kickoff. A later authoritative
  correction does not overwrite evidence: it emits a correction diagnostic and
  removes the week from the eligible count pending an approved amendment.
- Publish `rating_shadow_score_report_v2` and
  `rating_shadow_evidence_v2` under the existing canonical week prefix.

**Acceptance criteria:**

- Every canonical evidence row is traceable to an authentic pre-kickoff freeze,
  exact pregame states, one authoritative outcome, and the same frozen V4 run.
- Missing, provisional, cancelled-without-status, corrected, or cross-week data
  cannot produce successful evidence.
- Identical scoring retries are byte-identical no-ops.

**Validation:**

- Tests for completion/stabilization timing, authoritative cancellation
  statuses, schedule changes, duplicate/cross-week outcomes, late corrections,
  V4 checksum drift, row lineage, diagnostics, and idempotency.

### Task 5 — Build the cumulative canonical evidence auditor

**Files:**

- `src/cks_picks_cfb/ratings/prospective.py`
- `scripts/pipeline/audit_rating_prospective_evidence.py`
- `tests/ratings/test_prospective_evidence.py`

**Changes:**

- Discover evidence only from the fixed policy's canonical weekly paths for
  season 2026; never accept caller-selected freeze/evidence refs as successful
  weekly status.
- Re-read and checksum-verify manifests, datasets, state refs, V4 proof, outcome
  refs, policy/code manifests, measured timing, coverage, and cancellation
  evidence. Reject Week 0, late freezes, non-normal slates, mixed lanes,
  duplicates, partial sets, correction diagnostics, or unscored weeks.
- Publish an immutable through-week summary after every successful score. It
  records every weekly ref/SHA and pre-specified descriptive evidence:
  - state mean/SD/observed-weight distributions and week-to-week movement;
  - missing/fallback/quality-flag counts and completed-game exposure;
  - margin/total MAE, RMSE, bias, paired V4 error deltas, and paired bootstrap
    intervals;
  - standardized-residual mean/SD and 50/80/95% interval coverage; and
  - counts by week and target.
- Exclude markets, lines, edges, ROI, and betting results. Do not emit a
  promote/fail decision or alter execution based on observed metrics.
- When exactly six or more eligible canonical slates exist under one lane,
  publish one immutable Phase 5 completion manifest listing the first six
  eligible weeks and all evidence refs. Extra slates remain append-only
  evidence. Completion makes a separate promotion-review contract
  plan-eligible; it does not promote the candidate.

**Acceptance criteria:**

- The auditor independently reconstructs the eligible count and refuses mixed,
  late, corrected, partial, or caller-substituted evidence.
- Repeated audits at the same through-week cutoff are byte-identical.
- No result field can activate, publish, tune, or promote candidate v1.

**Validation:**

- Unit and fixture integration tests for eligibility counting, mixed lanes,
  missing weeks, skipped ineligible weeks, correction removal, metric algebra,
  deterministic bootstrap, and six-slate completion.

### Task 6 — Publish the manual operations runbook

**Files:**

- `docs/ops/rating_shadow_operations.md`
- `.codex/QUICKSTART.md`
- `docs/modeling/evaluation.md`
- `docs/modeling/rating_system_requirements.md`

**Changes:**

- Document one copy-ready weekly sequence: committed implementation check,
  production V4 dependency verification, Preview `prepare-week`, read-only
  preflight, go/no-go record, candidate freeze, postgame preparation, score,
  cumulative audit, and identical-retry verification.
- State that production V4 publish/freeze occurs under its existing production
  authority and is only an explicit read-only input to Phase 5.
- Require operators to record the exact prepared pipeline run, ref-set URI,
  V4 run ID, earliest kickoff, requested cutoff, measured lead, canonical
  manifest URI/SHA, score URI/SHA, cumulative summary URI/SHA, waivers, and
  diagnostics in that week's session log.
- Include recovery matrices for missing refs, late V4, late candidate freeze,
  schedule changes, cancellations, incomplete finals, partial canonical sets,
  catalog failure, R2 collision, and later outcome correction.
- Keep the run manual; do not add cron, GitHub Actions, or production scheduler
  integration during Phase 5.

**Acceptance criteria:**

- An operator can execute the lane without inventing a timestamp, ref, storage
  prefix, eligibility decision, or recovery action.
- The runbook clearly separates production V4 operations from Preview rating
  writes and states when a week does not count.

**Validation:**

- Command/help smoke tests and a fixture-based tabletop walkthrough of every
  recovery branch.
- Strict MkDocs build.

### Task 7 — Execute and close the six-slate evidence lane

**Files:**

- `docs/plans/2026-08-26/phase5-protected-prospective-evidence.md`
- `docs/planning/roadmap.md`
- `docs/modeling/rating_system_requirements.md`
- `docs/plans/index.md`
- weekly `session_logs/YYYY-MM-DD/NN-*.md`

**Changes:**

- Commit the implementation before any live preflight or Preview write. Run the
  full local validation and fixture lifecycle first.
- For each Week 1-or-later candidate slate, run the documented preflight. Make
  no canonical write unless every gate is green and measured time remains at
  least one hour before earliest kickoff.
- Freeze once, repeat the identical invocation to prove no-op determinism, and
  record exact refs/SHAs. Do not retry a failed eligibility gate under adjusted
  inputs after outcomes begin.
- After authoritative stabilized finals, score once, repeat identically, run
  the cumulative auditor, and record all evidence or diagnostics.
- Continue unchanged until six eligible scored slates exist. Missed, late,
  partial, corrected, Week 0, or sub-normal-coverage weeks remain visible but
  do not count; no calendar deadline weakens the requirement.
- Leave this contract `In Progress` after tooling implementation and during
  evidence collection. Mark it `Implemented` only when the six-slate completion
  manifest, deterministic weekly reruns, documentation, and validation all
  exist.

**Acceptance criteria:**

- Six eligible canonical slates under one policy/candidate/freeze-code lane are
  complete, scored, reproducible, and cumulatively audited.
- No candidate change, protected-outcome tuning, production write, market
  analysis, publication, or promotion occurred.
- The authority docs identify the next separate contract; Phase 5 completion
  itself does not authorize it.

**Validation:**

- Read-only preflight plus immutable Preview lifecycle checks for every week.
- Same-stamp/identity reruns for freeze, score, and cumulative summary.
- Final independent checksum audit of all six weekly artifact sets.

## Testing Strategy

- **Unit:** policy parsing/hashing; authentic clock boundaries; parent and
  source-capture cutoffs; slate equality; V4 counts; state completeness and
  equivalence; cancellation status; scoring stabilization; evidence metrics;
  lane changes; and eligible counting.
- **Integration:** complete Preview fixture flow from `prepare-week` ref set
  through preflight, freeze, score, cumulative audit, collisions, diagnostics,
  correction removal, and identical retries.
- **Regression:** all Phase 1–4 ratings, lake, preaggregation, prepare-week,
  V4 adapter, canonical lifecycle, model-oracle, and production-write-boundary
  tests.
- **Read-only live checks:** current Preview input refs and explicit production
  V4 frozen metadata/artifacts, only when available and before any canonical
  candidate write.
- **Full validation:** focused and complete ratings tests, full Python suite,
  scoped Ruff format/check, contracts validation and synchronization, strict
  MkDocs, CLI help/smoke checks, and `git diff --check`.

## Risks and Edge Cases

- **Missing run-local drives ref:** Phase 5 cannot freeze until Task 2 publishes
  and verifies it. Catalog discovery or mutable-prefix listing is prohibited.
- **Provider score-stream incompatibility:** true PPSO requires current plays to
  carry the certified score fields. A failed read-only readiness check makes
  the week ineligible; outcomes cannot be substituted into drive points.
- **Clock race:** a green preflight does not reserve eligibility. The canonical
  write must itself complete with 3,600 seconds of measured lead.
- **Late V4 freeze:** Phase 5 never freezes or mutates V4. If no complete
  production V4 run is frozen by the candidate deadline, the week cannot count.
- **Schedule drift:** additions after candidate freeze invalidate exact
  coverage; verified cancellations/postponements can be waived only at score
  time. A materially changed slate remains non-counting.
- **Small slate:** fewer than 40 exact frozen V4/candidate games is visible
  shadow evidence but cannot count toward six.
- **Outcome correction:** canonical evidence is never overwritten. A later
  authoritative correction removes the week from the eligible count pending an
  approved amendment.
- **Implementation change after lane start:** prediction-affecting changes reset
  the lane. Scorer/auditor-only corrections require proof, versioning, and an
  approved amendment.
- **Catalog outage:** R2 canonical artifacts remain authoritative. Optional
  Preview catalog registration can be retried only after connectivity and
  identity verification; it never creates success status.
- **Operational visibility:** weekly metrics are evidence, not tuning input.
  Candidate v1 remains frozen regardless of observed performance.
- **Calendar pressure:** missing Week 1 or any later week delays completion; it
  never permits retroactive evidence or weaker gates.

## Definition of Done

- [ ] The prospective policy is frozen separately from the unchanged shadow
      design and candidate identities.
- [ ] Complete run-local byplay/drives/team-game/source-reconciliation refs are
      available from Preview preparation.
- [ ] Authentic-clock, parent-cutoff, exact-slate, state-artifact, cancellation,
      and cumulative-audit contracts are implemented with focused tests.
- [ ] The implementation is committed and the complete local validation suite
      passes before live writes.
- [ ] Six Week 1-or-later normal-coverage slates have canonical pre-kickoff
      freezes and complete scores under one unchanged lane.
- [ ] Every weekly freeze, score, and cumulative summary has a byte-identical
      retry and exact refs/checksums recorded.
- [ ] The immutable Phase 5 completion manifest exists and independently
      verifies all six weekly artifact sets.
- [ ] No model/state/prediction tuning, production write, publication, market
      analysis, or promotion action occurred.
- [ ] Runbook, evaluation authority, roadmap, plan index, weekly logs, and this
      contract record exact results and the next gated contract.
- [ ] Full validation passes and this plan is marked `Implemented`.

## Implementation Record

- **2026-08-26:** Tooling Tasks 1–6 are implemented locally: the separately
  hashed prospective policy, immutable preparation ref set, measured-clock
  freeze, persisted target states, verified scoring, correction-aware cumulative
  auditor, and manual runbook are in place. Candidate v1, the Phase 4 shadow
  config, and all V4 production interfaces remain unchanged.
- **Validation:** Focused contracts plus Phase 1–4 regression coverage passed
  (`535 passed, 2 skipped`); scoped Ruff, contracts validation, strict MkDocs,
  CLI help smoke tests, and `git diff --check` passed.
- **Remaining:** Task 7 is intentionally ongoing. No live preflight, R2 write,
  or Preview/production Neon operation was attempted. The first live action is
  blocked until this implementation is committed and `PREVIEW_DATABASE_URL` is
  configured and distinct from production.

## Amendments

Any material conflict discovered before the first prospective freeze must be
recorded here and resolved under committed code before the lane begins. After
the first eligible freeze, no amendment may alter the candidate, state math,
prediction math, eligible-window policy, lead-time gate, coverage threshold, or
required slate count for that lane. Such a change creates a new policy/lane and
resets prospective accumulation.

Scorer/auditor-only mechanical corrections may preserve the lane only when an
approved amendment proves from immutable freeze artifacts that candidate
predictions and eligibility are unchanged. Failed or superseded artifacts
remain immutable history.
