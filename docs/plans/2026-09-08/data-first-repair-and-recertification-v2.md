# Data-First Repair and Recertification v2

- **Status:** In Progress
- **Created:** 2026-09-08
- **Planner:** Astra
- **Approval source:** User approved the full pre–Phase 5 replacement plan on 2026-09-08; execution is deferred to a separate task.
- **Implementation log:** `session_logs/2026-09-09/01-data-first-repair-v2-implementation.md`
- **Commit policy:** Separate code and evidence checkpoints; user executes Git.

## Implementation record

The sealed local dry run reproduces the required `8,936 / 8,935 / 8,903 / 33 /
5,240` population and auxiliary invariants. Preview run
`repair-v2-20260909T1345Z` executed the two approved gap captures but its
independent verifier rejected a nullable-boolean serialization defect; it is
not certified evidence. The replacement implementation preserves nullable
booleans and reuses only the two exact, already registered reconstructed
captures. A clean committed checkpoint and a new immutable Preview run remain
required before this contract can be marked complete.

## Goal, parents, and boundary

Repair predictive-population and auxiliary semantics without changing immutable
history or production. The [review and common contract](transformation-review-and-authority-reset.md)
is binding. Input flags: `--core-eligibility-uri`, `--auxiliary-eligibility-uri`,
`--phase3-retained-uri`. Resolve the exact reviewed Phase 2d/2e and Phase 3 parents
from the roadmap's evidence records; they are audit/repair inputs, not proof of
correct predictive semantics. No rating/model tournament runs here.

## Ordered implementation

1. Reconcile the complete schedule and outcomes against observation and
   reconciliation keys. Persist all 33 omissions by game ID, status, outcome
   validity, actual exclusion branch and proposed disposition. One observed
   incomplete game is `401640992`; independently validate its status. Do not
   assume all 32 completed records have usable outcomes without checking.
2. Set `forecast_eligible` for completed, valid-outcome historical games
   independently of measurement eligibility. Missing/bad measurements have null
   values, zero usable exposure, and reasons; they cannot update ratings. No
   point scores are invented. If a completed game's outcome cannot be recovered,
   keep it in the schedule ledger as unscorable and block an all-games claim.
3. Rebuild coaching from stable coach/team identities across source captures;
   filter history to the target preseason cutoff before tenure calculation.
   Distinguish `coach_tenure`, `coach_tenure_lower_bound`, `coach_tenure_censored`,
   and `coach_new`. `coach_new=1` requires an established first year; censored or
   ambiguous history does not prove a new hire. Conflicting preseason assignments
   remain null with reasons. Postseason employment cannot establish preseason assignment.
4. Rebuild roster membership by `(season, team, player_id)`. Same-team retained
   players are the current/prior-year same-team intersection. Incoming experienced
   players are current players absent from that same-team intersection but present
   on another preceding-year roster. Separate shares/QB counts; preserve identity
   conflicts as exclusions. No 2019→2021 one-year continuity assumption. Current
   roster size can remain observed when predecessor continuity is unavailable.
5. Recruiting uses the target calendar four-class window, excluding 2020. Emit
   current value, available-class average/count/span, strict four-class average,
   and current-minus-available-average trend. Strict average is null unless all
   four allowed calendar classes exist. Empty windows stay missing. A short
   window is never labeled a complete four-year history.
6. Audit returning-production units and meaning against captured payloads and
   source metadata. Preserve the existing seven numeric field names only where
   they mean the stated preseason PPA/usage measures. No retrospective full-season
   statistic may be relabeled as preseason evidence.
7. Produce family/season coverage, distinct counts, constant-feature warnings,
   timing classes, and semantic examples. Validate designated new/continuing
   coaches and retained/transferred players against independent source records.
   A family can be rejected while the core remains eligible. Polls and markets
   receive diagnostic-only permitted roles.

## Bounded capture protocol

Reuse captured sources first. Permit existing-provider gap filling only for
documented repair records, including 2014 roster metadata for 2015 continuity
and earlier coach-tenure evidence. These are auxiliary history, not extra
development outcomes. No 2020 captures, new providers, subscriptions or purchases.

Before requests, persist a request inventory (entity, parameters, reason,
existing captures checked, request/retry ceiling) and available quota. Enforce
200 requests including retries across the entire corrective run and resumed
attempts, not 200 per invocation. Stop before quota/budget exhaustion; never
silently expand the inventory. Recovered data receives a new capture timestamp.
Over-budget/unrecoverable auxiliary gaps reject a family or use declared
fallback; core population/outcome blockers remain blockers.

## Output interfaces

Schemas: `repair_manifest`, `repair_population`, `repair_auxiliary`,
`repair_coverage`, `repair_issue`, `repair_capture_plan` (common prefix/suffix).
Stage directory: `repair/v2`. Table keys: population `(season, game_id)`;
auxiliary `(family, season, team)`; coverage `(family, season, slice)`;
issues `(issue_id, affected_key)`; capture plan `(request_id)`.

The manifest names exact inherited/replacement core and auxiliary DatasetRefs,
omission ledger, family-specific historical/live eligibility and permitted
consumer roles. Retain old Phase 2e refs as superseded semantic evidence. Supply
the schedule/outcome population digest and per-game measurement usability.
Phase 3 may proceed only if core correctness gates pass; rejected optional
families cannot be silently reintroduced by Phase 4A.

## Validation, failure, and done

In addition to common gates, test future coach history removal, censored tenure,
ambiguous employment, stable identities, same-team returns versus transfers,
missing predecessor seasons, 2020 recruiting windows, constant feature rejection,
completed games without plays, quota/retry/resume accounting, and no outcome
imputation. Independently reconcile every historical schedule row and handoff ref.

Done means the immutable report explains all 33 omissions, core blockers are
resolved or explicitly prevent advancement, family admissions are justified,
new captures are bounded, and artifacts/tests/docs/session log are complete.
Scope/budget/definition changes use the common amendment process.
