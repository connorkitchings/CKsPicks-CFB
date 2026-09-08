# Phase 6: Prospective Evidence v2

- **Status:** Approved
- **Created:** 2026-09-08
- **Planner:** Astra
- **Approval source:** User approved the full replacement plan on 2026-09-08.
- **Implementation log:** Pending corrected Phase 5 and separate Phase 6 task
- **Commit policy:** Separate code/evidence checkpoints; user executes Git.

## Goal and dependencies

Collect six independently verifiable normal-coverage paired slates, then recommend
retaining V4, continued shadowing, or a separate Phase 7 plan. No activation or
publication occurs. The [common contract](transformation-review-and-authority-reset.md)
applies. Input: `--phase5-candidate-uri`; freeze/score additionally require
`--season`, `--week`, `--as-of`, explicit V4 prediction ref and authentic input
capture refs. Reject historical or original Phase 4B parents.

## Readiness and permitted updates

Before the first eligible freeze, verify real 2026 pregame source availability,
current capture operation, schedule coverage, reproducible state replay and
ability to build all required features. Reconstructed historical captures do
not prove live preseason availability. Missing live optional inputs follow the
candidate's predeclared fallback; unsupported mandatory inputs block readiness.

Freeze the full candidate algorithm: rating/core/context choices, fitted-model
specification, allowed fitting/updates, calibration rules and source policy.
Preseason priors, noise parameters, head coefficients, alpha choices and
calibration are fit through the preceding completed season and stay fixed during
the prospective season. Before each weekly freeze, update team states from
permitted finalized games in earlier canonical weeks available before that
freeze; update pregame context under the same rule. Do not refit forecast heads,
retune priors/noise or recalibrate on accumulating protected outcomes.

Executing these frozen updates yields new state identities under the same
candidate identity and does not reset the evidence window. Changing a feature,
design, fitting/calibration rule, cutoff policy or source semantics starts a new
candidate and a new window. The next season's refit must use the frozen
algorithm; do not combine evidence across changed candidate designs.

## Freeze, scoring and counting

- Target T−2h; require both candidate and V4 predictions frozen at least T−1h
  before the first kickoff of the declared slate. Do not backdate or construct
  a later subset to evade a missed first kickoff.
- Require at least 40 unique paired games with complete finite predictions on
  each qualifying normal-coverage slate. Preserve full candidate population and
  exclusions separately from paired counts. Week 0 and any pre-candidate slate
  are ineligible. Source quote omissions do not fabricate football eligibility.
- Bind immutable code/config/data/model/state lineage, game population, freeze
  timestamp, source-availability evidence, candidate identity and V4 ref.
- Late, incomplete, unverifiable or altered freezes are permanently ineligible
  for the six-slate counter. Missing inputs use only predeclared fallback.
- Score finalized outcomes no earlier than 24 hours after the last included
  game's completion; unavailable final timestamps/outcomes block scoring, not
  the prior immutable freeze. Persist later corrections as new outcome/evaluation
  versions with lineage; never rewrite the original evidence.
- Report paired target errors, CRPS/calibration where available, stage/coverage
  breakdowns, broader candidate coverage and every exclusion. Repeated scoring
  is idempotent; never count the same slate twice.

## Market comparison and recommendation

Run football evaluation first. Then compare authentic prediction-time and
closing quotes separately, binding provider/quote IDs, timestamps, paired
coverage and omissions. Reconstructed lines remain historical diagnostics;
they cannot create CLV or prospective evidence. Quote coverage does not select
football-model winners. Betting/staking optimization remains excluded.

After six qualifying slates publish an immutable evidence recommendation:
retain V4, continue shadow evidence, or draft Phase 7 operational-readiness and
promotion contract. Missing six slates produces a continued-shadow report with
specific blockers; it does not weaken the counter. A recommendation never
activates a model or publishes its predictions.

## Outputs, verification and done

Stage `phase6/v2`; schemas: `phase6_readiness`, `phase6_freeze`,
`phase6_prediction`, `phase6_evaluation`, `phase6_quote_diagnostic`,
`phase6_evidence_recommendation`. Freeze keys: candidate/season/week/run;
predictions additionally game/target; evaluations additionally outcome version;
quotes additionally provider/quote ID and quote role. Every counter entry refers
to exact verified freeze/evaluation versions.

Test T−2h/T−1h boundaries, no backdating, source-time violations, unchanged versus
changed update policy, prior-week gating, incomplete/cancelled/postponed games,
full/paired populations, 24-hour outcome delay, duplicate counts, outcome
corrections, authentic versus reconstructed quotes and immutable collision.
Independently replay a future-like historical rehearsal as diagnostic-only;
it cannot count prospectively. Run common validation and update docs/log.

Done: verified future evidence and a recommendation, or a precise continued-
shadow report explaining remaining slates/blockers; never an automatic promotion.
Counting/timing/refit/market/promotion changes require the common amendment process.
