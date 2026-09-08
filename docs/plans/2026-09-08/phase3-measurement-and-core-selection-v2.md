# Phase 3: Corrected Measurements and Core Selection v2

- **Status:** Approved
- **Created:** 2026-09-08
- **Planner:** Astra
- **Approval source:** User approved the full replacement plan on 2026-09-08.
- **Implementation log:** Pending repair handoff and separate Phase 3 task
- **Commit policy:** Separate code/evidence checkpoints; user executes Git.

## Goal and dependencies

Repeat the original bounded core selection on the repaired population, preserving
measurement definitions and separating postgame observations from pregame inputs.
The [common contract](transformation-review-and-authority-reset.md) applies.
Input: `--repair-manifest-uri`; require core-eligible repair output and exact refs.
No auxiliary prior fitting, context selection, or production operation occurs.

## Measurement interfaces

Build observations for every eligible schedule/team/role key. Missing or
unreconciled measurement evidence receives null value, zero usable exposure and
reason; never drop a completed valid-outcome forecast game for this reason.
Maintain existing EPA/PPA, success, 20-yard explosiveness, true scoring-opportunity
efficiency, field-position, plays-per-drive, turnover and pass/rush definitions.
Definition defects require a separately identified correction, not an unnoticed
redefinition during selection.

Pregame history is restricted to preceding canonical weeks **and** verified
availability before the week's first kickoff; persist the actual cutoff. This
preserves the original week-open scaffold and excludes earlier-numbered weeks
whose rescheduled games were not available. Later Phase 6 uses the same weekly
cadence with its actual freeze cutoff. Postgame observation and pregame snapshot
schemas are different and role-checked.

Preserve four league-centered additive opponent-adjustment iterations. At each
cutoff, expose per-source-game adjusted observations by applying the opponent
correction used in the final iteration (iteration-three opponent values) to
that source game's raw value. Keep opponent identities, correction, measurement
role, and numerator/denominator. Exposure-weighted per-game values must reproduce
iteration-four aggregate output; missing opponent treatment must match the
aggregate denominator exactly. Export no values after the cutoff.

This enables deterministic rating replay at each cutoff. Replaying with newly
available opponent evidence may re-express old observations, but each observation
enters a given replay once. Ratings never apply a second schedule correction.

## Frozen core registry and selection

Registry (unchanged): `epa_only`, `quality_core_equal`,
`without_success_rate`, `without_explosive_rate_20`,
`without_points_per_scoring_opportunity`, `without_epa_per_play`,
`epa_pass_rush`, `quality_core_epa_split`. Preserve the original component
definitions, weights, chronological standardization, defensive direction,
equivalent exposures, and missing-component/FCS fallbacks from the superseded
2026-09-07 Phase 3 contract and its sealed configuration. This is a repeat of
that registry, not a new component-weight search.

Primary scaffold: annual rho 0.60, exposure updater, fold-local Ridge alpha 10.
Sensitivity: same prior/head, recency half-life 4. Require >=0.5% primary pooled
improvement over EPA-only, 90% paired interval lower bound >0, equal population,
and no target-season MAE regression >5%. Sensitivity may not regress >0.5%
against its own EPA-only reference. Prefer the fewest components within 0.5% of
best eligible MAE; lexical candidate ID resolves remaining ties. If no challenger
passes, retain valid EPA-only. Original results remain reduced-population history.

## Outputs and validation

Stage `phase3/v2`; schemas: `phase3_observation`, `phase3_pregame_snapshot`,
`phase3_adjusted_history`, `phase3_terminal`, `phase3_prediction`,
`phase3_attribution`, `phase3_population`, `phase3_certification`,
`phase3_retained_core`. Snapshot keys include cutoff/game/team/role/measurement/
recency/iteration; adjusted-history keys additionally include source game ID.
Retained manifest binds the repair handoff, definitions, selected components,
both scaffolds, all output refs and full-population verification.

Verify independent numerator/denominator recomputation, symmetric offense/defense
accounting, source-time cutoffs, component fallback, the 33-record ledger,
iteration-four reconstruction from per-game adjustments, future/same-game
perturbation invariance, exact candidate populations, bootstrap and selection.
The common validation suite is required. Preserve the historical manifest.

Done: complete repaired-population outputs and one eligible retained core are
independently verified, with evidence/docs/log updated. Missing valid reference,
unresolved population loss, definition defect or invalid lineage blocks Phase 4A.
Registry/threshold/definition changes require the common amendment process.
