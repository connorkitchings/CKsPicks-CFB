# V5-12A: Conditional Historical Scorecard

- **Status:** Draft
- **Created:** 2026-09-19
- **Planner:** Sol
- **Approval source:** Pending; this contract records future conditional work and is not authorized for execution by the documentation reset.
- **Implementation log:** Pending; create `session_logs/YYYY-MM-DD/NN-v5-12a-conditional-historical-scorecard.md` when separately authorized.
- **Commit policy:** Separate scorecard-code and Preview-evidence/report checkpoints; user controls Git operations.

## Goal and entry gate

Publish a transparent V5-only historical scorecard after a successful Contract
11A verification record proves the exact frozen forecast artifact can be
reconstructed. The entry record must carry exact Repair, measurement, rating,
and forecast parent/output hashes and `permitted_use:
conditional_historical_results_only`.

This contract has no entry if 11A records a mismatch, failed comparison, missing
evidence, or a different identity. In that case it publishes no scorecard values.
Development evidence remains 2015–2019 and 2021–2025; reject 2020 and 2026.

## Conditional-use boundary

Outputs are conditional historical development evidence with permitted use
exactly `conditional_historical_results_only`. This status never restores
forecast eligibility; it never authorizes a 2025 final fit, 2026 replay, live forecast,
production promotion, market comparison, or V4 change; create prospective
evidence; or satisfy the final-readiness or Contract 06–09 gates.

Every evidence output and readable report must name the frozen Repair
`repair-v2-20260909T1417Z`, measurement
`possession-v1-measurements-20260915-18fb0aa-r6`, rating
`possession-v1-ratings-20260917-d029526-cert`, and forecast
`forecast-v1-20260917-4600ddd-04b` identities, exact verified hashes, and all
unresolved foundation limitations.

## Scope, metrics, and allowed writes

Calculate V5-only results from the exact 11A-verified output population. Report
2025 as the headline, 2022–2024 as context, and pooled 2022–2025 results.
For margin and total separately, report MAE, RMSE, bias, Gaussian CRPS, central
50/80/95% interval coverage and width, sample counts, exclusions, calibration
fallback/residual counts, and completed-game-stage slices.

Write a signed Preview scorecard and terminal manifest under:

```text
artifacts/research/data-first-football-v1/historical-scorecards/conditional-v1/runs/<run-id>/
```

Publish a readable report under `docs/research/`. Both outputs carry
`permitted_use: conditional_historical_results_only` and
`production_activation_authorized: false`. Do not compare V4, recommend
readiness, retune, refit, change artifacts/configuration, access markets, or
write to catalog, Neon, production, web, or V4.

## Tasks and acceptance criteria

1. Revalidate the successful 11A manifest, its signatures, hashes, population,
   and the four frozen parent identities before scoring.
2. Compute and test every declared metric, population/exclusion count, fallback
   count, residual count, and completed-game-stage slice under the frozen
   chronology.
3. Publish signed, Preview-only scorecard evidence and a readable V5-only
   report; independently re-read both and require an idempotent repeat.
4. State that the results are conditional historical development evidence and
   list all unresolved limitations. The report makes no readiness recommendation.

The completed scorecard answers the 2025 historical question only. It cannot
clear any blocker or replace the full audit and final review.

## Definition of done and amendments

- [ ] A successful, exact-hash Contract 11A record is independently re-read.
- [ ] Required V5-only metrics are present for 2025, 2022–2024, and 2022–2025.
- [ ] Signed Preview evidence and readable report name all frozen identities and
  limitations.
- [ ] No V4 comparison, readiness recommendation, 2026 action, or scorecard is
  emitted after a failed 11A verification.

Contract 12 remains the only historical-readiness review. Changes to metrics,
populations, conditional-use status, or downstream scope require an approved
amendment before execution.
