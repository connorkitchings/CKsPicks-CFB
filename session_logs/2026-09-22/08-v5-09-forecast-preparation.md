# Session: Contract 09 Forecast and Readiness Preparation

## TL;DR

- **Worked On:** Preparation of [Contract 09](../../docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md) for its required through-Week-4 execution.
- **Outcome:** In progress. This session may inspect and prepare isolated code and validation interfaces only; it must not generate, publish, or verify live forecasts or readiness from the stale Weeks 0–3 replay.
- **Plan Contract:** `docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md` — In Progress.
- **Approval / Status:** User said “Proceed” on 2026-09-22 after the Week 4 gate was explained; interpreted as authorization for preparation only.
- **Blockers:** Stabilized Week 4 finals and new immutable Contract 07/08 manifests are required before any forecast apply, independent verification, or Week 5 readiness verdict.
- **Next:** Inspect the frozen 11C bridge, existing forecast/readiness tooling, and their interfaces; implement only preparatory scaffolding compatible with the required refreshed parents.

## Context and Decisions

- Contract 08's immutable Weeks 0–3 replay is `possession-v1-rating-replay-20260922-fcaa571`; it is not eligible to bypass the mandatory Week 4 refresh.
- V4 production, Neon serving state, and public publication remain outside this work.
- Any Preview R2 write, live forecast prediction, or readiness verdict awaits the refreshed Week 4 lineage.

## Work Completed

- Marked Contract 09 In Progress for preparation only and recorded this session.
- Inspected the frozen 11C manifest and confirmed its final application recipe:
  `expanding`, reference heads, alpha 10.0, development seasons 2015–2019 and
  2021–2025, with carried 2025 calibration variances.
- Confirmed the historical `run_data_first_forecasts.py` runner is sealed to
  the 11B historical rating parent and recomputes selection from historical
  outcomes. It cannot consume a live Contract 08 parent without violating
  replay-only application.
- Confirmed `data_first_forecast_prediction_v1` requires non-null `actual`,
  `absolute_error`, and `gaussian_crps`, so it cannot represent a future,
  pre-kickoff Week 5 forecast. A separate immutable live-prediction contract
  is therefore required.

## Files Modified

- `docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md` — lifecycle and session-log reference.
- `session_logs/2026-09-22/08-v5-09-forecast-preparation.md` — preparation log.

## Validation

- [x] Read-only 11C manifest inspection — frozen expanding/reference alpha-10
  final-fit recipe and 2025 carried calibration variances confirmed.
- [x] Static runner/schema inspection — historical runner and outcome-required
  prediction schema are ineligible for live Week 5 application.
- [x] `uv run mkdocs build --strict --quiet` — passed.
- [x] `uv run pytest tests/test_data_first_documentation_authority.py -q` —
  38 passed.
- [x] `git diff --check` — passed.

## Amendments and Blockers

- The Week 4 refresh is an existing binding gate, not a change in scope.
- A material Contract 09 interface amendment is required before code changes:
  it must define a separate live forecast dataset and manifest, frozen final-fit
  model reconstruction, independent verifier boundary, and readiness handoff.
  The historical forecast runner and schema must remain sealed.
- Preparation checkpoint committed as `01b47b7`.

## Handoff Notes

- **Resume at:** Produce and obtain approval for the narrow live-forecast
  interface amendment; then implement it without any R2 apply. After stabilized
  Week 4 finals, execute 07/08 under new immutable identities before Contract 09
  apply.
- **Watch out for:** Do not use the Weeks 0–3 replay to generate a readiness
  verdict or open Contract 06. Do not alter the historical forecast runner,
  verifier, or outcome-required prediction schema.
- **Proposed Terra handoff after amendment approval:** `Use the repository-local
  implement-plan skill and implement the approved live-forecast application
  amendment. Treat it as authoritative, preserve the Week 4 immutable-parent
  gate, run its validation, and stop for any material conflict.`

**tags:** ["v5", "contract-09", "forecast", "readiness", "preparation"]
