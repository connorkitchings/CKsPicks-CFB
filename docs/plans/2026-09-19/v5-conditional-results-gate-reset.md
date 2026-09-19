# V5 Results-First Planning and Documentation Reset

- **Status:** Implemented
- **Created:** 2026-09-19
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation with “PLEASE IMPLEMENT THIS PLAN” on 2026-09-19.
- **Implementation log:** `session_logs/2026-09-19/01-v5-conditional-results-gate-reset.md`
- **Commit policy:** Documentation-only commit; user controls Git operations.

## Goal

Record a two-lane V5 execution order that reaches a verified conditional 2025
historical scorecard sooner while retaining the full foundation, readiness, and
2026 gates. This reset changes only plans, authority documentation, regression
tests, and a planning log. It does not run an audit, reconstruct forecasts,
calculate metrics, change model code/configuration, or read/write R2 artifacts.

## Binding decisions

- Contract 10 remains the full-foundation authority: 10A is Implemented; 10B
  remains In Progress and is required for foundation readiness, final artifact
  eligibility, and all 2026 work. Open Repair, measurement, rating, and lineage
  findings remain readiness blockers.
- Existing Contract 11 remains Draft full forecast-eligibility closure. New
  Draft Contract 11A independently verifies the frozen forecast artifact only
  for conditional historical-results use.
- New Draft Contract 12A publishes a conditional V5-only scorecard. Existing
  Draft Contract 12 remains the only historical-readiness review and starts
  only after 10B, 11A, and 12A complete with all required foundation blockers
  closed.
- `conditional_historical_results_only` permits a verified historical scorecard
  only. It never restores forecast eligibility or authorizes a 2025 final fit,
  2026 replay/live forecast, production promotion, market comparison, or V4
  change. It is not prospective evidence.

## Ordered future work

1. **11A — Conditional forecast verification:** after 10A lineage/preflight
   evidence, exact frozen parents, and recorded limitations, independently
   reconstruct every forecast output. A mismatch publishes failure evidence
   only; a pass publishes signed Preview evidence with
   `conditional_historical_results_only`. It does not alter 04/04B or start
   2026 work.
2. **12A — Conditional historical scorecard:** after a successful exact-hash
   11A record, publish V5-only 2025 headline, 2022–2024 context, and pooled
   2022–2025 MAE, RMSE, bias, Gaussian CRPS, 50/80/95 coverage/width, counts,
   exclusions, calibration fallback/residual counts, and stage slices. No V4
   comparison, readiness recommendation, retuning, refit, or 2026 action.
3. **10B — Full historical foundation audit:** continue independently; publish
   its four audit outputs, independent reread, findings/dispositions, and final
   foundation gate. Completion records blockers; it does not silently clear them.
4. **12 — Historical readiness review:** after 10B, successful 11A/12A, and
   required blocker closure, reconcile the scorecard and audit and issue the
   only readiness recommendation. Only explicit user acceptance may trigger a
   re-review of 06–09.
5. **06–09 — Deferred 2026 application:** stay deferred pending their existing
   final-readiness gate, exact eligible artifacts, and re-reviewed contracts.
   Conditional results alone cannot satisfy that gate.

## Documentation work and validation

Update the roadmap, documentation home, common V5 contract, rating requirements,
plan index, AGENTS current-focus summary, Contracts 10/10B/11/12/06–09, and
documentation-authority tests. Add a dated planning log. Tests must reject
treating 11A/12A as forecast eligibility or prospective evidence, treating a
2025 scorecard as 2026 authorization, or bypassing 10B/final Contract 12.

Run focused documentation-authority tests, strict MkDocs, scoped lint for
changed tests, and `git diff --check`. No implementation, model configuration,
production setting, or cloud artifact may change.

## Definition of done

- [x] Conditional contracts and all authority pages agree on both lanes.
- [x] 10B and final Contract 12 remain explicit readiness/2026 gates.
- [x] Regression tests cover the four prohibited interpretations.
- [x] Required documentation validation passes.
- [x] Planning log records the documentation-only boundary and user-controlled
  Git handoff.
