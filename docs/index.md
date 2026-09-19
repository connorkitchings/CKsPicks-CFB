# CKsPicks-CFB Documentation

CKsPicks-CFB is a college-football prediction system with a Python pipeline,
an immutable Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## Current posture (2026-09-19)

**V4 remains the live production champion.** The **V5 ratings successor** is
isolated research, distinct from **feature schema v5**, the separate V4 diagnostic.
Repair v2, Phase 3 v2, R6 possession measurements, and the retained rating
artifact are historical evidence. The active V5 sequence is the full audit
through 2025, independent forecast verification, then historical results and
readiness review. The [data-first roadmap](planning/data-first-football-forecasting-roadmap.md)
is the canonical status and execution-queue authority.

The original Phase 4B retained manifest remains prohibited as a forecasting
parent. Earlier candidate results keep their historical audit limits. New research
uses 2015–2019 and 2021–2025 as development evidence, excludes 2020, and requires
future pre-kickoff freezes for independent evidence. Production operations remain
under their existing runbooks.

The current forecast artifact is not an eligible certified downstream parent
until its computations and output datasets are independently reconstructed.
2026 application is deferred pending historical readiness and explicit review.

The retained artifact includes scored historical prediction rows through 2025,
but **no V5 2025 accuracy scorecard is currently authoritative**. Contract 10B
has not published its audit evidence; Contract 11 has not independently
reconstructed the stored computations; and Contract 12 has not issued the
required MAE, bias, CRPS, interval-coverage, population, exclusion, and
comparison report. Stored results may be inspected only as unverified
historical-artifact diagnostics until those gates close.

The target flow is:

```text
source data → canonical Bronze/Silver/Gold → football measurements
→ measurement-level opponent adjustment → team ratings/state
→ structured game prediction → probabilistic output
→ prospective evaluation → timestamped line comparison
```

Markets never inform football measurements, ratings, or prediction selection.
They are joined only after football-model evaluation. Betting decisions are
deferred.

## Start here

- [Data-first forecasting roadmap](planning/data-first-football-forecasting-roadmap.md)
  — governing new research sequence and compatibility boundaries.
- [Repository boundaries](architecture/repository_boundaries.md) — current and
  target architecture, dependency direction, ownership, and versioning rules.
- [2026 operations and historical roadmap](planning/roadmap.md) — current V4
  operations and the completed/superseded research record.
- [Rating-system requirements](modeling/rating_system_requirements.md) — the
  specified and amended V5 rating meaning, certification gates, and deferred challengers.
- [Measurement catalog](modeling/measurement_catalog.md) — football
  measurements, provenance, and rating eligibility.
- [V4 regime contract](modeling/early_season_regimes.md) — live production
  benchmark and early-season routing.
- [Evaluation](modeling/evaluation.md) — historical validation and protected
  2026 shadow evidence policy.
- [Weekly pipeline](ops/weekly_pipeline.md) and
  [production runbook](ops/production_runbook.md) — live operations.
- [Historical successor-v2 compatibility runbook](ops/rating_successor_research.md)
  — reproduction guidance for completed R1/R2 evidence; its pending R3/R4
  sequence is superseded.
- [Implementation contracts](plans/index.md) — durable Sol-to-Terra handoffs.
- [Decision log](decisions/decision_log.md) — architectural decisions.

## Documentation policy

Current operating and architectural authority lives in the pages above.
Completed work, V2 documentation, prior rating research, and schema snapshots
are retained as [historical archive](archive.md) evidence. Session logs
are chronological records under `session_logs/`; see that directory’s README
for the active-window policy.
