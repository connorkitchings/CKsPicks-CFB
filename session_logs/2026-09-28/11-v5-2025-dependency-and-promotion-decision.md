# Session: 2025 dependency and repaired-rating production decision

## TL;DR

- **Worked On:** Closed the 2025-lineage question and reviewed whether the 2026 repaired ratings should replace production V5.
- **Outcome:** 2025 repaired pregame ratings are already included in the full forecast-bridge refit. The 2026 preseason prior instead derives directly from 2025 terminal opponent-adjusted PPP and possessions; recomputing it matched all 276 certified prior rows exactly. Recommendation: keep V5 selected in production and continue the repair as a shadow candidate.
- **Plan Contract:** [V5 estimator review](../../docs/plans/2026-09-28/v5-estimator-three-way-review.md), 2026 counterfactual amendment.
- **Approval / Status:** User requested a final assessment. No production activation was requested or performed.
- **Blockers:** None for the decision. Prospective Week 5 paired outcomes are not yet available.
- **Next:** Verify the saved Week 5 research forecast timestamp, score the paired forecasts after certified finals, check full lineage and intervals, and use a separate exact release contract if a successor is selected.

## Context and Decisions

- The live prior builder reads the 2025 terminal *measurement*, not the 2025 final *rating*. Its mean is `0.60 × standardized 2025 terminal PPP`; its variance carries over from `1/(1+2025 possessions/8)`.
- The prior formula recomputed from the pinned 2025 terminal table matches the 276 certified 2026 mean and variance values with maximum absolute difference `0`.
- The full repaired counterfactual already replaced all 2015–2019 and 2021–2025 historical pregame rating states in the alpha-10 bridge training frame. Its 2025 rating repair therefore affects the 2026 forecast bridge, but not the certified 2026 preseason prior.
- Retrospective 2026 margin MAE gains support further testing; unscored Week 5 and no clear total gain do not support replacing production today. There is no fixed six-slate gate, but an exact release decision and independent verification remain required.

## Work Completed

- Checked the 2026 prior construction code against the pinned historical terminal and certified live priors.
- Added [2025 dependency and production decision](../../docs/research/2026-09-28-v5-2026-counterfactual.md#2025-dependency-and-production-decision) to the research report.

## Files Modified

- `docs/research/2026-09-28-v5-2026-counterfactual.md` — final lineage interpretation and production recommendation.
- `session_logs/2026-09-28/11-v5-2025-dependency-and-promotion-decision.md` — this handoff.

## Validation

- [x] All 276 certified prior means and variances exactly reproduced from the pinned 2025 terminal table.
- [x] `git diff --check`.

## Amendments and Blockers

- Rebuilding 2025 terminal measurements or changing the prior formula would be a separate experiment. No such change is required to test the current rating-update repair.
- Existing uncommitted research files were preserved; no git operation was performed. Proposed commit message: `docs: close V5 repair lineage and production decision`.

## Handoff Notes

- **Resume at:** Verify the saved pregame Week 5 research predictions and score them when final outcomes are certified; do not label them prospective until their timestamp and immutability are confirmed.
- **Watch out for:** The 215 completed 2026 games were reconstructed retrospectively. Keep production V5 selected unless a new, exact release decision is approved.

**tags:** ["ratings", "v5", "2025", "2026", "decision"]
