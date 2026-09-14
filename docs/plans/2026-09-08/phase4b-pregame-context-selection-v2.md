# Phase 4B: Pregame Context Selection v2

- **Status:** Superseded
- **Created:** 2026-09-08
- **Planner:** Astra
- **Approval source:** User approved the full replacement plan on 2026-09-08.
- **Implementation log:** Pending repaired Phase 4A and separate Phase 4B task
- **Commit policy:** Separate code/evidence checkpoints; user executes Git.

> **Superseded (2026-09-13):** Execution authority is [04: forecast bridge and fitting-window selection](../2026-09-13/04-v5-forecast-bridge-and-fitting-window.md).
> Preserve the original approval, historical hold notice, and mathematical record
> below. Only sections explicitly inherited by the
> [V5 common contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
> carry forward. This does not authorize executing old runners or consuming the
> original Phase 4B retained manifest as a forecasting parent.

> **Execution hold (2026-09-10):** This remains an Approved historical record
> with its original approval source. Do not execute it until the rating-methodology
> review produces a replacement or explicit reaffirmation.

## Goal, scope and parents

Select at most one legitimate pregame context family per target outside the
frozen rating. The [common contract](transformation-review-and-authority-reset.md)
applies. Inputs: `--phase4-rating-uri`, `--phase3-retained-uri`; both must share
the repaired population and lineage. The original Phase 4B retained manifest is
prohibited as a parent. No auxiliary-prior reselection, polls, markets or
production writes occur.

## Exact candidate and feature registry

Compare `no_context`, `field_position`, `drive_length`, and `turnovers` using:

| Family | Per-side features |
| --- | --- |
| field_position | average_start_field_position_offense, average_start_field_position_defense |
| drive_length | plays_per_drive_offense |
| turnovers | turnover_rate_offense, turnover_rate_defense |

Use both home and away values, including both teams for drive length. Plays per
drive measures drive length; do not call it clock tempo. Use certified raw
pregame aggregate values (no opponent adjustment for these context families),
never postgame observations joined by the predicted game ID. The join must
require the pregame schema/role and exact forecast cutoff.

Use exposure-weighted prior-week current-season context. With zero usable
current-season exposure, use preceding available season-terminal context and
record the actual source season/gap; 2019 context before 2021 is a two-year-old
football fallback, not roster continuity. With neither source, use the training-
fold mean and a missingness indicator. Every context feature also records its
source/cutoff and fallback reason. All imputations and scaling use training only;
scale floor 0.05. A feature with no training observations rejects that family for
the comparison instead of dropping rows. Missingness columns are included for
all declared features consistently, not selected from validation missingness.

Recruiting, returning production and continuity remain inside the frozen prior
comparison this cycle. Do not reuse them as extra forecast-head candidates.

## Bridge, selection and outputs

Re-fit no-context through the same code path as every candidate. Use the exact
Phase 4A fixed Ridge alpha-10 bridge, venue indicators, populations and folds,
plus the family's expanded columns. Margin and total are independent decisions.

Require >=0.5% target MAE improvement over no-context, paired 90% lower bound >0,
equal game populations and no season regression >5%. Among passing candidates
within 0.5% of best, prefer the fewest actual expanded columns (both sides and
missingness included), then lexical family ID. Otherwise retain no-context.
Do not grant a prior-stage early-season advancement exception to this stage.

Stage `phase4b/v2`; schemas: `phase4b_pregame_feature`, `phase4b_prediction`,
`phase4b_coverage`, `phase4b_attribution`, `phase4b_retained_baseline`. Feature
keys: candidate/season/game/side/feature/cutoff; prediction keys:
candidate/target/season/game/cutoff. Manifest binds rating/core, frozen per-target
context and feature definitions, bridge, population, selection and lineage refs.

## Validation, failure and completion

Mutate the predicted game's field position/plays/turnovers and require unchanged
features and forecasts; repeat with future games. Mutating a permitted prior
observation must affect only later eligible states. Reconstruct features from
source games independently. Test no-history/preseason fallbacks, both teams'
drive length, two-year context gaps, missing indicators, venue, correct expanded
feature counts, exact populations and bootstrap ties. The verifier recomputes
predictions and selection, not merely stored selected flags.

Common validation applies. Done means one valid baseline per target is sealed
with independently verified pregame provenance, complete coverage and docs/log.
Invalid no-context reference blocks Phase 5. Family, cutoff, context or bridge
changes require the common amendment process.
