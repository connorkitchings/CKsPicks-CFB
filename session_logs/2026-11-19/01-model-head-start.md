# Session: Two-week preparation for the 2027 model

## TL;DR

- **Worked on:** Historical totals features, P3 replay, and the weather and near-kickoff captures.
- **Plan contract:** [Two-week model preparation](../../docs/plans/2026-11-19/model-head-start.md)
- **Approval and status:** Owner authorized implementation in the November 19 session. The upcoming slate captures and final close remain open.

## Weather capture

- Week 12 rehearsal queried the CFBD schedule and venue catalog and saved ten raw NWS hourly forecasts and a receipt. Five games had already started. The ten forecasts matched kickoff hours and all arrived after the certified cutoff.
- The two dated captures are scheduled at 11:45 a.m. Eastern through the local Codex automation. Receipts and raw evidence are stored outside the tracked tree in `.worktrees/model-head-start-evidence/weather/`. The capture uses the existing CFBD key and publicly available NWS forecasts.
- The Ohio Stadium ECMWF archive check returned the kickoff hour at six-day lead. The pilot contract records archive coverage and timing limits.

## Validation

- The live weather rehearsal exercised the CFBD and NWS clients and the cutoff report.
- The weather fixture covers cutoff equality, delayed retrieval, missing or invalid issue timestamps, and missing forecast or venue metadata.

## P3 replay and capture checks

- The offline P3 replay matches both prediction arms on 3,483 historical game keys. Early-stage FBS-vs-FBS margin MAE improves by 0.933537 points over 886 games. The original scripts and replay predictions are retained beside the weather evidence. Replaying the 2026 updater from logged inputs reproduced 1,316 pregame role means to floating-point precision. The [baseline audit](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md) records differences in prior and measurement lineage.
- The [near-kickoff report](../../docs/plans/2026-11-12/01-near-kickoff-line-capture.md) verified both eligible November 18 games had spreads and totals, with lead times of about 511 and 541 minutes. Run the same report for the next eligible slots once the captures exist.
- The [holdout preflight](../../docs/plans/2026-11-12/05-holdout-replay-readiness.md) passed eleven existing manifests. All 610 pinned Week 7 quote rows were received after the forecast cutoff, including four at or after game kickoff. The exporter rejects the manifest. The holdout contract records the proposed remedy for owner approval before the final export.
- Contracts and the quality registry passed. The full Python run reported one chart golden-digest failure. The same digest failure reproduced on clean `dev` at the starting commit.

## Totals

- The [totals experiment report](../../docs/modeling/offseason_totals_drive_sample.md) records 8,520 historical games and 194,657 eligible drives, with audited examples for an ordinary game, no opportunities, and excluded scoring.
- Across 2,998 headline FBS-vs-FBS games, opportunity creation is available for all four team/unit inputs in 2,706 games, finishing in 975, and starting field position in 2,806. The experiment declaration records the coverage constraint for December.
- The sample, coverage tables, drive and scoring audits, and input hashes are in `.worktrees/model-head-start-evidence/totals/output/`.

## Final checks

- Ruff format and lint, strict MkDocs, contracts validation, quality registry, and Git whitespace checks passed.
- The Python suite passed with 2,550 tests and 24 skips after excluding the single chart golden-digest test that independently failed on clean `dev`.
