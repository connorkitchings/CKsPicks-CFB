# V5 Blitzkrieg: Current Status

> **Model development:** complete and accepted on 2026-09-22. **Live releases, week state and public record:** [Current Status](../status.md). **Weekly operations:** [weekly runbook](../ops/weekly_runbook.md).

## Accepted model

V5 estimates each team's offensive and defensive scoring efficiency per possession, adjusts for opponents, and updates one continuous season-long rating as games finish. The selected candidate is `ppp__rho_0_60__exposure`: true points per possession, a 0.60 carryover prior, and exposure-weighted updates. A fixed Ridge bridge converts pregame states and earlier-only non-offense offsets into home margin and total forecasts. The selected bridge uses expanding fitting history, alpha 10 reference heads and a verified through-2025 final fit. Bookmaker lines never enter model features; 2026 outcomes never refit the sealed model. See the [methodology](possession_rating_methodology.md).

Development uses 2015–2019 and 2021–2025, excluding 2020 throughout. Opponent adjustment belongs primarily to football measurement; ratings must not double-count schedule strength. V5 is distinct from the historical V4 feature-schema-v5 diagnostic. V4 is a documented historical benchmark, not the weekly operational path; see the [V4 retrospective](v4_retrospective.md).

## Evidence and limits

The acceptance lineage is Repair v2, r9 measurements, r9 certified ratings, the through-2025 bridge final fit and independent 11D forecast verification. The [historical review](../archive/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md) accepted 7,318 prediction rows across 2022–2025 with zero exclusions. For 2025, margin MAE was 14.160 and total MAE 13.356 across 934 games per target; 80% intervals covered 80.1% of margins and 82.0% of totals. The separate 762-game postseason-recorded market diagnostic had lower market error on both targets. No like-for-like point-in-time V4 backtest under this protocol exists, so these results do not establish superiority over V4.

The [ratings audit](../archive/research/2026-09-28-current-v5-ratings-audit.md), [intended-update repair experiment](../archive/research/2026-09-28-v5-intended-update-repair-experiment.md) and [counterfactual replay](../archive/research/2026-09-28-v5-2026-counterfactual.md) preserve the investigation history. Their dated references to a pending promotion do not describe current release state. The accepted repaired intended-update model and the October 14 atomic season-controller cutover are governed by the [season operations contract](../plans/2026-10-14/01-season-operations-and-week7-bridge.md).

## Operational and record policy

`run_season.py` prepares immutable season artifacts, verifies `season_verification_v2`, and stages and activates one atomic release for the website. The [weekly runbook](../ops/weekly_runbook.md) is the operating authority. The older leakage-audit receipt and per-slate publication instructions are historical evidence; they are not the controller's release gate. The first controller weekly update remains an acceptance requirement; Phase 1 review safeguards are committed, while Week 8 execution still needs Week 7 finals and refreshed controller inputs.

The public record is one cumulative V5 record from Week 0. Started and reconstructed games remain on Games without a retrospective label because forecasts use only observations available before their recorded forecast cutoffs. Build time can be later than kickoff; input cutoff must precede kickoff. A pre-kickoff freeze establishes prospective provenance only. Six slates are not a launch prerequisite; they are a useful monitoring window. See [record methodology](record_methodology.md) for market precedence, grading and limitations.

Early Week 6 games have forecasts and currently published grades. The owner-approved rebuilt-quote candidate instead leaves games `401871090`, `401871051` and `401871066` ungraded for both targets because their real quote captures are after kickoff. That candidate is pending activation; the active public record is unchanged. Other unregistered captures still require owner review. Live totals and release IDs belong only in [Current Status](../status.md).

Remaining EPA replacement, quality follow-ups, scoring recertification, non-monotonic running-score work and 2025 matchup backfill are deferred obligations in [Current Status](../status.md) and [known issues](../data/known_issues.md), not unfinished model development. Further model research remains isolated from public publication until separately approved.
