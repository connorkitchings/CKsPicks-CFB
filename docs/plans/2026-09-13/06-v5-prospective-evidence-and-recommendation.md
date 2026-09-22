# V5-06: Prospective Evidence and Promotion Recommendation

> **Current policy amendment (2026-09-22):** This contract's immutable attempt ledger, eligibility checks, outcome-versioned evaluations, and quote diagnostics remain active as prospective monitoring. Its six-slate count and three-category recommendation are no longer prerequisites for completing V5 development or reviewing a site cutover. The [current V5 status](../../modeling/v5_status.md) and [verified-cutover contract](../2026-09-22/04-v5-authority-simplification-and-site-cutover.md) govern those milestones. Diagnostic and retrospective records never count, and 2026 outcomes cannot refit this V5 identity.

- **Status:** In Progress — monitoring tooling ready; no qualifying live slate yet
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User approved the complete package with “Implement the proposed plan.” on 2026-09-13; collection starts only after the verified live-readiness dependency passes.
- **Implementation log:** Code-readiness implementation: `session_logs/2026-09-22/11-v5-live-research-tooling-completion.md`. Create a separate log for each evidence-collection session and the final `NN-v5-prospective-evidence-review.md`.
- **Commit policy:** Separate evidence/review checkpoints; user executes Git.

## Goal, current state, and entry gate

Collect and independently verify six normal-coverage paired slates, then recommend
retaining V4, continued shadowing, or a separate promotion contract. The
[common contract](../../archive/v5-contracts/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md) is binding.
Require a verified candidate from [04](../../archive/v5-contracts/2026-09-13/04-v5-forecast-bridge-and-fitting-window.md)
and **ready**, independently verified live inputs/tooling from
[05](../../archive/v5-contracts/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md). A blocked readiness report
or mere code completion is not sufficient.

There are no qualifying slates for this not-yet-built candidate at planning time.
Earlier V4/candidate-v1/feature-v5 evidence cannot be inherited. No calendar date,
historical gain, or completed development phase bypasses these gates.

**Historical-first deferral (2026-09-18):** Before any 06 implementation,
Contracts 10 and 11 must close, Contract 12 must report historical readiness,
and the user must explicitly accept that review. The subsequent live-application
contracts must be re-reviewed with the frozen design, eligible artifacts,
through-2025 final fit/calibration, prior inputs, and timestamp provenance.
Historical replay is not prospective evidence merely because a record uses a
`live` timing label.

**Conditional-results clarification (2026-09-20):** Implemented Contract 11A
and approved Contract 12A may produce `conditional_historical_results_only`
development evidence. That
status does not restore forecast eligibility, close Contracts 10-12, establish
prospective evidence, or satisfy this contract's final-readiness, explicit-user-
acceptance, and re-reviewed-application gate.

## Approach, scope, and interfaces

Execute the frozen 05 tooling against exact candidate, V4, schedule, input and
outcome refs. Preserve every attempt, exception, eligibility disposition and
correction. No production/Neon/web writes, candidate tuning, source acquisition,
new automation, betting strategy, staking or promotion execution is authorized.

Stage: `evidence`. Consume immutable 05 readiness/freezes/evaluations and output
versioned `evidence_ledger`, `evidence_report`, `quote_diagnostic`, and
`evidence_recommendation` records with exact parent roles and common envelopes.
Market comparison accepts explicit authentic quote refs after football
evaluation; it cannot alter the candidate or eligibility count.

## Implementation tasks

### Task 1 — Verify each pre-kickoff attempt

Before every slate, verify candidate identity, current readiness, permitted
prior-week state updates, schedule membership, source effective/capture times,
and exact V4 pairing. Execute freeze with T−2h target/T−1h hard limit and >=40
normal-coverage paired games as specified in 05. Confirm measured immutable
availability before kickoff, not just a user-supplied cutoff.

Keep late/incomplete/unverifiable slates with reasons and permanently exclude
them from the protected count. Never backdate, shrink a slate after kickoff to
evade a missed boundary, or reissue a changed candidate under an old identity.
Preserve broader candidate FBS-FCS coverage separately from the V4 paired set.

**Acceptance:** Every attempted slate has an auditable immutable disposition;
all qualifying freezes meet exact timing, source, population and identity rules.

### Task 2 — Score stabilized outcomes and maintain the counter

After >=24 hours from the last included game's completion, run artifact-only
scoring with exact final-outcome refs. Missing final times/outcomes remain
blockers. Independently verify forecast errors, uncertainty metrics, outcome
version, population and the updated evidence ledger. Corrected outcomes create
new evaluations linked to the original freeze and cannot increment a slate twice.

Report both target MAE/RMSE/bias, candidate Gaussian CRPS/coverage/width,
team-specific completed-game-stage diagnostics, FCS/missing-evidence usage,
and paired versus full candidate coverage. Mark unavailable V4 probabilistic
metrics explicitly. Separate descriptive weekly reports from frozen selection;
no accumulating 2026 outcomes may retune the protected candidate.

**Acceptance:** The count is independently derived from verified qualifying
freeze/evaluation pairs, not stored counters alone. Every exclusion/correction is
visible, and earlier missed windows are never recovered retrospectively.

### Task 3 — Run market diagnostics after football evaluation

First finalize the football report for the unchanged candidate. Then join
authentic prediction-time and closing quotes as separate roles, binding provider,
quote IDs/timestamps, cutoffs and coverage. Show sign conventions, forecast versus
market errors, disagreements and missing quotes on identical declared games.

Reconstructed/untimestamped historical lines cannot become authentic closing
evidence or prospective observations. Quote omissions do not invalidate an
otherwise eligible football slate or manufacture performance on a smaller
unreported subset. Markets cannot pick a football candidate, alter fitting, or
create betting/staking recommendations under this contract.

**Acceptance:** The football results and evidence count are invariant to the
presence, removal, or perturbation of market inputs. Quote-specific populations
and omissions remain explicit.

### Task 4 — Publish an evidence recommendation

At six qualifying slates, produce a versioned report containing the complete
attempt/eligibility ledger, paired errors and intervals, calibration/stage/coverage
results, operational reliability, immutable lineage, and separate market appendix.
Use the common paired bootstrap where its season/week block structure permits;
with one prospective season, explicitly report the limited independent season
replication rather than implying multi-season evidence. Do not introduce a new
post-result threshold to manufacture a promotion conclusion.

Use the existing 1% target parity and 5% season/stage regression limits as review
screens, not automatic promotion criteria. Document uncertainty and the effect
of sparse slices. Recommendation categories are:

- **Retain V4:** observed material predictive regression, failed validity, or
  operational problems make this candidate unsuitable to advance; retain the
  immutable evidence and propose a new design/window only through planning.
- **Continue shadowing:** fewer than six qualifying slates, unresolved evidence,
  uncertain comparison/calibration, or insufficient stable coverage; list exact
  missing slates or blockers. V4 remains production.
- **Prepare a separate promotion contract:** six valid slates and satisfactory
  football/calibration/coverage/operational review justify considering operational
  rehearsal and a promotion decision. The report is a review recommendation,
  never automatic activation. Any judgment beyond the declared numeric screens
  must be explicit and left for the separate promotion review, not encoded as an
  unapproved deployment rule.

A separate Phase 7 must settle operational rehearsal, rollback proof and exact
promotion acceptance criteria before activation can be considered. Market or
bankroll results cannot rescue a failed football/validity layer.

## Testing strategy

Use verified tooling from 05; do not add mirror tests for an evidence-only run.
Recompute input hashes, freeze timing, scoring stability, paired metrics,
population/exclusion membership, duplicate/corrected-slate counts and quote
chronology independently. If tooling changes are needed, apply the common
computational checks and candidate-change policy. Run strict MkDocs and
`git diff --check` for evidence documentation updates.

## Risks, definition of done, and amendments

Six slates are an entry gate to review, not a guarantee of statistical precision,
superiority, or deployment. A new candidate requires a new protected window.
Missing genuine live inputs cannot be replaced by reconstructed history.

- [ ] Each attempted slate has an immutable verified disposition.
- [ ] Six eligible paired slates and an independent final recommendation are complete.
- [ ] Football, market, and operational evidence are separated and limitations explicit.
- [ ] No tuning, production activation, publication, or betting-policy change occurred.
- [ ] Reports, runbook status, contract lifecycle, and session logs are current.

While fewer than six slates exist, issue a precise continued-shadow report and
leave this contract In Progress. Do not mark six-slate collection Implemented
because one execution session ended or tooling is finished. Follow the common
amendment process for design, timing, counting, calibration or source changes.

### Amendment 1 — Evidence tooling code-readiness (Sol, 2026-09-22)

**Reason:** The approved live-research tooling completion plan implements the
prospective ledger and report path before the Week 4 refresh. Implementation
must not be mistaken for readiness certification or prospective evidence.

**Revised approach:** Contract 06 evidence tooling may be implemented and
synthetically tested while its entry gate remains closed. Operational attempts
must bind the independently verified live forecast and `ready` Contract 05
report, and retain exact immutable freeze, outcome, evaluation, and optional
quote parents. The qualifying count is independently reconstructed from those
parents. No diagnostic or historical replay can qualify, and quote diagnostics
remain independent of football metrics and eligibility.

**Impact:** No evidence is admitted by this amendment, and the six-slate window
does not start. The contract remains Approved until verified readiness opens
collection; the six-slate recommendation remains future work. V4 remains the
production champion and activation is outside this contract.

### Amendment 2 — Preview evidence runner and independent verifier (2026-09-22)

**Reason:** The approved V5 live tooling plan completed the implementation
layer for immutable prospective attempts, outcome-versioned reports, separate
quote diagnostics, and recommendations before the Week 4 parent refresh.

**Revised approach:** `scripts/research/run_v5_prospective_evidence.py`
provides Preview preflight, immutable apply, idempotent repeat, and verification;
`scripts/research/verify_v5_prospective_evidence.py` independently reconstructs
attempt dispositions, qualifying counts, football metrics, corrections, quote
diagnostics, and recommendation. Inputs must carry independently verified
Contract 05 readiness, freeze, and score refs. Authentic quote diagnostics are
separate and cannot change football calculations or eligibility. Diagnostic,
late, incomplete, or unverifiable attempts are retained with reasons and
excluded from the protected count.

**Impact:** Synthetic tests establish code behavior only. The entry gate remains
closed until Contract 09 has independently verified live readiness. No slate
was attempted or counted, and the six-slate evidence program is not complete.
Contract 06 remains Approved; only collection sessions with eligible live
evidence may advance its evidence lifecycle.

### Amendment 3 — Monitoring replaces the prelaunch count gate (2026-09-22)

**Reason:** The user accepted historical V5 model completion and chose a
verified live cutover with Preview rehearsal and rollback proof. The original
six-slate wait conflated ongoing prospective measurement with model completion
and site readiness.

**Revised approach:** Preserve every immutable attempt, freeze, correction,
football report, and separate authentic-quote diagnostic. Continue deriving
the qualifying count independently, but use it as a monitoring statistic and
periodic review window. The three original recommendation categories may be
reported descriptively after six slates; they are not prerequisites for a site
cutover. Live readiness, exact lineage, pre-kickoff timing, and diagnostic
exclusions remain unchanged. The [current V5 guide](../../modeling/v5_status.md)
and [cutover contract](../2026-09-22/04-v5-authority-simplification-and-site-cutover.md)
govern activation review.

**Impact:** Contract 06 is now In Progress as an ongoing monitoring program.
No slate has been counted, no historical or diagnostic record becomes
prospective, and no 2026 outcome may refit V5. The earlier six-slate
definition of done is superseded for site promotion; it remains a descriptive
research milestone. Production activation still requires a separate decision.
