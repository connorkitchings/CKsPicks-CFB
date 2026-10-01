# Session: Week 0 Launch Execution Planning

## TL;DR

- **Worked On:** Investigated Week 0 readiness across ingestion, transformations, models, pipelines, and publishing; produced the Week 0 launch execution contract.
- **Outcome:** Contract approved by the user with four decisions: V4 timebox with V2 fallback, full production setup, Pick'em prep included, and no further CFBD talent rechecks.
- **Plan Contract:** `docs/plans/2026-08-18/week0-launch-execution.md` (Approved)
- **Approval / Status:** User approved the plan and authorized implementation on 2026-08-18.
- **Blockers:** None planning-side. External: `CFBD_PREDICTION_TOKEN` still needed before authenticated Pick'em reconciliation (Stage 4).
- **Next:** Stage 1 — apply migration `0008` to `preview-2026`, resolve frozen input refs, assemble strict V5 Gold, run the sealed V4 tournament.

## Context and Decisions

- All 8 Week 0 games route to `game_1`; the launch model decision is a
  game_1 spread/total decision, and the frozen V2 run
  `2026w0-a0edb9e72cb1` is the proven fallback.
- Local `artifacts/preview/` contains only working copies
  (`comparisons/`, `pickem/`, `training/`); durable refs and pipeline-run
  evidence live in Preview R2, so Stage 1 must resolve the core/baselines refs
  from the active run's frozen `input_refs.json` rather than local paths.
- CFBD talent remains empty; the user chose to launch with
  `prior_only_fallback` and stop rechecking.
- Production (Neon + Vercel) is fully in scope for this contract, staged after
  the V4 decision gate.

## Validation

- [x] Read-only investigation only; no implementation files changed in this
  planning step.

## Handoff Notes

- **Resume at:** Stage 1.1 (`with_preview_env.sh make migrate-db`) in the
  implementation session.
- **Watch out for:** Never mutate the frozen V2 run; Preview-only writes until
  Stage 3; locked 2025 requires the frozen selection SHA.

**tags:** ["week0", "planning", "modeling", "production", "launch"]
