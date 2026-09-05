# CKsPicks-CFB Documentation

CKsPicks-CFB is a college-football prediction system with a Python pipeline,
an immutable Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## Current posture

**V4 is the live 2026 production champion.** It publishes spread and total
predictions through the fail-closed weekly operations workflow. New research is
governed by the [data-first football forecasting roadmap](planning/data-first-football-forecasting-roadmap.md):
repository alignment, data audit/repair, measurement validation, simple ratings,
spread/total forecasting, then prospective evidence. The completed R1/R2 and
earlier candidate work remain historical evidence subject to audit. 2020 is
excluded globally; 2025 is development data only inside the new research
namespace; future frozen predictions provide independent evidence.

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
  approved successor’s initial requirements and deferred decisions.
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
