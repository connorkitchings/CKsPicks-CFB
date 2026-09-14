# V5-02: Possession Measurement Certification

- **Status:** Approved
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User approved the complete package with “Implement the proposed plan.” on 2026-09-13; execution requires the dependencies below.
- **Implementation log:** Pending; create `session_logs/<execution-date>/NN-v5-possession-measurement-certification.md`.
- **Commit policy:** Separate code and certified-evidence checkpoints; user executes Git.

## Goal, current state, and entry gate

Produce independently certified possession measurements and replayable evidence
for rating estimation. [Contract 00](00-v5-documentation-and-methodology-alignment.md)
must be complete. The [common contract](v5-ratings-successor-roadmap-and-contracts.md)
is binding, including constants, chronology, source roles, validation, and failure
behavior.

Consume the exact verified Repair v2 manifest from
`repair-v2-20260909T1417Z` and its declared source refs. Check its raw SHA against
the common contract and rerun its independent eligibility checks before use.
The repaired population contains 8,936 schedule games, including the documented
incomplete game; do not reinterpret all schedule rows as scoreable observations.
The producer and verifier must independently reconcile membership and statuses.
The Phase 3 v2 winner is a comparison reference, never the possession definition.

Existing reusable primitives include score-stream reconstruction in
`ratings/observations.py`, the adjustment/replay machinery in
`ratings/phase3_v2.py`, preceding-season scaling in `ratings/states.py`, and
immutable partitioned writers. Existing drive `points`/`points_on_opps` columns
are not trustworthy score numerators. Existing certification does not prove the
new event attribution, overtime filter, or denominator semantics.

## Approach, scope, and affected interfaces

Implement new possession-specific modules in `src/cks_picks_cfb/ratings/`,
schema/validation support in `src/cks_picks_cfb/data/`, a research runner and
independent verifier in `scripts/research/`, configuration in the existing
data-first research directory, and focused possession tests.

Runner parent flag: `--repair-manifest-uri`; standard flags and default dry-run
come from the common contract. Stage: `measurements`. No provider acquisition,
catalog registration, serving writes, V4 changes, estimator tournament, or
data-dependent constant tuning. Reuse exact captured sources; an acquisition need
is a blocker for a separate bounded plan, not permission to call an API.

## Implementation tasks

### Task 1 — Declare population, ledger, and measurement contracts

Create these versioned record families with common lineage fields:

| Record | Key / required meaning |
| --- | --- |
| `population` | season/game; both teams, week, kickoff/status, scoreability, measurement dispositions |
| `possession` | season/game/drive/offense; defense, period class, eligible-play count, possession eligibility, source identities |
| `scoring_event` | season/game/source-event/team; nonnegative score increment, scoring category, associated possession/conversion event, quality reason |
| `observation` | season/game/team/role/measurement; native numerator/denominator/value, usable exposure, timing and quality |
| `snapshot` | season/game/team/role/measurement/cutoff/iteration; prior-only aggregate and exposure |
| `adjusted_history` | target cutoff/source game/team/role/measurement/iteration; replayable per-game adjusted observation |
| `terminal` | season/team/role/measurement/iteration; explicitly terminal-only measurement state |
| `coverage` | season/slice/measurement; schedule, scoreable, usable and quarantined counts and reasons |
| `measurement_manifest` | Exact source/derived refs, replay configuration and verification eligibility |

Use the common schema prefix/suffix. Record source IDs rather than relying on row
position across changing files. Keep scoreability, usable measurement population,
and forecast population independent. Missing data never removes a forecast row.
Zero *usable* exposure with a reason is distinct from an observed zero numerator.

**Acceptance:** Duplicate keys, cross-season/2020 contamination, invalid roles,
incompatible refs, and same-game data supplied as a pregame snapshot are rejected.

### Task 2 — Certify possession eligibility and scoring attribution

A rating possession is a regulation drive with at least one eligible scrimmage
play: `st == 0`, `penalty == 0`, `twopoint == 0`, not an existing dead-ball marker,
and `garbage == 0`. Quarter >=5 is overtime. Missing/contradictory period evidence
cannot be assumed to be regulation. Include one-play drives; exclude kickoff-only
and special-teams-only drives. Preserve the existing absence of a clock-ending
special case. Record eligibility at play and possession levels so the numerator
policy is auditable.

Reconstruct score increments from canonical chronological play score streams,
matching home/away team identity, not whichever team happens to occupy the
offense column. Verify the provider's observed score timing with fixtures and
source examples. Attribute offensive scores and attached conversions to their
originating possession; assign defensive/return scores and attached conversions
to the scoring unit category. Field goals ending eligible offensive possessions
are offensive possession points. Defensive two-point returns and safeties are
non-offense points. An ambiguous event remains unresolved, not guessed.

Partition each team's scoring into disjoint categories:

1. Eligible regulation offensive possession points.
2. Regulation offensive points from excluded possessions.
3. Regulation non-offense points.
4. Overtime points, with the underlying unit category retained diagnostically.
5. Unresolved scoring increments.

The category sums must equal the score-stream team total, which is independently
reconciled to the final outcome. Never fabricate a missing event as a balancing
residual or derive offense points from the final score. Preserve the integral,
nonnegative and [0,8] offensive-drive checks, >=94% season final-score
reconciliation gate, and paired offense/defense quarantine. A team-game with
unresolved attribution cannot supply certified PPP/non-offense evidence; record
its opposing-defense effect. This can coexist with separately valid EPA evidence.

**Acceptance:** Tests explicitly cover touchdowns/conversions, field goals,
interception/fumble returns, kick/punt/blocked-kick returns, safety, defensive
two-point return, garbage-only drives, a drive partly crossing garbage eligibility,
OT, unknown period, repeated score snapshots, regressions, and malformed streams.
For a possession that qualifies through at least one eligible play, PPP uses its
full attributable offensive drive points; EPA uses only eligible-play PPA. Report
mixed-eligibility drives so that difference is not hidden.

### Task 3 — Produce measurements and honest missingness

For each team-game, produce both role versions of eligible possession count,
true offensive drive-point sum, PPP, eligible EPA sum, EPA/possession, eligible
scrimmage-play count, and plays/possession. Both efficiency definitions use the
same eligible possession set. Defense inherits the corresponding opposing
offense's attributed numerator/denominator; higher allowed values are not yet
reversed until the rating standardization layer.

Any missing/nonfinite PPA among the eligible plays makes that team-game EPA
measurement unusable; do not zero-fill or silently change its denominator.
Preserve actual possession counts separately from measurement usable exposure.
Zero possessions yields null efficiency and a reason. Retain non-offense points
for/against, excluded scoring, overtime, and unresolved amounts as separate
team-game ledger outputs; missing attribution is not an observed zero.

**Acceptance:** Offense/paired-defense quantities reconcile exactly. Schedule
omissions, invalid source rows, and zero exposure do not reduce the retained
population. Coverage reports distinguish FBS-FBS/FBS-FCS, seasons, and each quality
reason. Both definitions have valid reference measurement paths before 03 may run;
an unusable definition requires a planning amendment, not silent registry removal.

### Task 4 — Replay opponent adjustment and certify output membership

Apply the inherited four-pass league-centered adjustment to PPP and EPA per
possession for each role using strictly prior source observations at each cutoff.
Retain iterations 0 and 4. Keep non-offense/volume measurements unadjusted context.
Reuse the established adjustment exposure and chronological policy; do not copy
Phase 3 component weights or its hardcoded output row counts into the new schema.

Write raw observations, cutoff-specific adjusted history, snapshots, and terminal
states as distinct consumer roles. Freeze constants from the common contract;
do not estimate them across 2015–2019. Produce preceding-season scale diagnostics
without fitting transforms on validation. Null/fallback treatment follows the
existing validated replay contract with explicit reasons and zero information.

Derive all expected rows and partitions from declared population, roles,
measurements, iterations and cutoff membership. Preflight records counts,
digests, excluded keys and expected output parts. The apply writer must match
that plan, including any logical-only partitions. Do not fix a failed count gate
by substituting the observed count without an independently derived invariant.

**Acceptance:** Future/same-game changes cannot affect an earlier snapshot.
Terminal rows cannot enter pregame consumers. Missing measurements do not alter
completed-game counts. Memory stays bounded by season/cutoff partitions.

### Task 5 — Independent verification and certified handoff

The verifier rereads exact raw source refs and reconstructs possession membership,
scoring attribution, measurement sums, population dispositions, adjustment,
counts/digests and schema meaning. Merely reusing the producer's report or checking
hashes is insufficient. Stage outputs in Preview research only. Publish an
eligible manifest only after all gates pass; preserve failed attempts as
ineligible immutable evidence. A second identical apply must be idempotent.

**Acceptance:** Verified manifest exposes the exact inputs needed by 03 and the
scoring ledger needed by 04, with `production_activation_authorized: false`.

## Testing strategy

Run the common computational gates plus focused ledger, possession, replay,
population and independent-verifier tests. Include asymmetric team history,
unscorable/incomplete games, FCS gaps, missing PPA/periods, 2019→2021, altered
future outcomes, raw/canonical hash mismatch, output-part disagreement, and
idempotency. Use small deterministic event fixtures plus bounded source-backed
semantic examples before full Preview apply.

## Risks, definition of done, and amendments

The old score stream may reconcile finals while still misattributing unit points.
Certify those separately. If the stronger eligibility rules materially reduce
coverage, report the actual loss and block the affected reference; never lower
gates or redefine possession semantics during execution.

- [ ] Population and both measurement definitions are independently certified.
- [ ] Ledger, replay, coverage and scale/fallback diagnostics are complete.
- [ ] Committed-code preflight, Preview apply, independent verifier and idempotent rerun pass.
- [ ] Scoped/full required checks, docs, plan status and implementation log updated.

Use the common amendment process. No estimator execution is part of this task.
