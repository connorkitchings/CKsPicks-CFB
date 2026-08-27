# CKsPicks-CFB Documentation

CKsPicks-CFB is a college-football prediction system with a Python pipeline,
an immutable Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## Current posture

**V4 is the live 2026 production champion.** It publishes spread and total
predictions through the fail-closed weekly operations workflow. The successor
is a rating-centric hybrid architecture on a separate research track: R1
certifies 2015–2019 and 2021–2025 history, R2–R4 select its methodology, and a
fresh candidate-v2 evidence lane follows only after a committed freeze. 2020
is excluded globally; 2026 outcomes are protected prospective evidence.

The target flow is:

```text
source data → canonical Bronze/Silver/Gold → football measurements
→ measurement-level opponent adjustment → team ratings/state
→ structured game prediction → optional ML residual → probabilistic output
→ market decision
```

Markets never inform football measurements, ratings, or prediction selection.
They are joined only after a football prediction exists.

## Start here

- [2026 roadmap](planning/roadmap.md) — current work, milestones, and the
  explicit R1–R4 research / O1–O3 operations split.
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
- [Successor-v2 research runbook](ops/rating_successor_research.md) —
  Preview-only R1 capture/certification and staged tournament procedure.
- [Implementation contracts](plans/index.md) — durable Sol-to-Terra handoffs.
- [Decision log](decisions/decision_log.md) — architectural decisions.

## Documentation policy

Current operating and architectural authority lives in the pages above.
Completed work, V2 documentation, prior rating research, and schema snapshots
are retained as [historical archive](archive.md) evidence. Session logs
are chronological records under `session_logs/`; see that directory’s README
for the active-window policy.
