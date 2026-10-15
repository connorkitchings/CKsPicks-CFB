# CKsPicks-CFB Documentation

CKsPicks-CFB forecasts college-football spreads and totals with the V5 Blitzkrieg season engine, an immutable Cloudflare R2 lake, Neon serving projections and a Vercel web app.

## Current authority

[Current status](status.md) owns live release IDs, week state and the scoreboard. [V5 model development is complete and accepted](modeling/v5_status.md). The public record is one continuous point-in-time V5 record from Week 0; [record methodology](modeling/record_methodology.md) explains forecast cutoffs, market selection and grading. V4 is [historical evidence](modeling/v4_retrospective.md), no longer an operational model. Six slates are monitoring evidence, not a prelaunch gate.

The [weekly runbook](ops/weekly_runbook.md) is the sole operational guide: build a revision, commit pinned inputs, prepare from a clean tree, rehearse in Preview and activate the verified atomic release with owner approval. Rollback selects a prior verified V5 season release. Old publish/freeze/close runbooks are archived history.

## Start here

- [V5 status guide](modeling/v5_status.md) — accepted model and lineage boundaries.
- [Weekly runbook](ops/weekly_runbook.md) — environments, revision/prepare/release and rollback.
- [Repository boundaries](architecture/repository_boundaries.md) — dependency direction and compatibility rules.
- [Data platform](architecture/data_platform_2026.md) — immutable source lineage and derived serving data.
- [Rating requirements](modeling/rating_system_requirements.md) and [measurement catalog](modeling/measurement_catalog.md) — football meaning, provenance and eligibility.
- [Ratings laboratory](research/ratings-lab-v1.md) and [research capture](ops/data_first_capture.md) — isolated research workflows.
- [Research roadmap](planning/data-first-football-forecasting-roadmap.md) and [2026 roadmap](planning/roadmap.md) — research direction and historical execution record.
- [Evaluation policy](modeling/evaluation.md) — chronology and evidence boundaries.
- [Implementation contracts](plans/index.md) — task authorization and lifecycle.
- [Decision log](decisions/decision_log.md) — architectural and publication decisions.

Markets never inform football measurements, ratings or prediction selection. They enter after forecasting for line comparison and grading. Research requires separate promotion before changing serving behavior; betting decisions are deferred.

## Documentation policy

Current authority lives in the pages above. [Archived documentation](archive.md) preserves dated V2/V4 research, superseded operations and completed plans as evidence. Session logs under `session_logs/` are chronological records rather than current operating instructions.
