# CKsPicks-CFB Documentation

CKsPicks-CFB is a college-football prediction system with a Python pipeline,
an immutable Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## Current posture (2026-09-28)

[V5 model development is complete and accepted](modeling/v5_status.md), with four historical audit findings closed and 7,318 verified historical prediction rows. V5 replay serves Weeks 0–4, Week 4 is scored, and the authorized Week 5 live run is selected in production. Current ratings are verified through Week 4, with six public history tabs including preseason. V4 remains available for rollback. The weekly operator is manual; the broader product-transformation contract remains In Progress. Six prospective slates are not a prelaunch requirement. The [September 28 ratings audit](research/2026-09-28-current-v5-ratings-audit.md) documents actual prior weights, the South Carolina–Alabama ordering, and outstanding serving and estimator concerns.

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
- [2026 operations and historical roadmap](planning/roadmap.md) — current
  operations and the completed/superseded research record.
- [Rating-system requirements](modeling/rating_system_requirements.md) — the
  specified and amended V5 rating meaning, certification gates, and deferred challengers.
- [Measurement catalog](modeling/measurement_catalog.md) — football
  measurements, provenance, and rating eligibility.
- [Ratings laboratory v1](research/ratings-lab-v1.md) — isolated V6 candidate data,
  chronological replay, and historical comparison workflow.
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
