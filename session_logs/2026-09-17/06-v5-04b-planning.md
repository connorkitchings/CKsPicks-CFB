# Session: V5-04B Planning — Calibration and Certification

## TL;DR
- **Worked On:** Investigated and planned V5-04B (forecast calibration, apply, and verification)
- **Outcome:** Contract `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` is now **Approved** with full implementation specifics
- **Plan Contract:** Self (planning contract)
- **Approval / Status:** User approved calibration-in-preflight approach and single Terra execution
- **Blockers:** None
- **Next:** Fresh Terra task to implement 04B

## Context and Decisions

- **Calibration in preflight:** User chose to compute calibration inside `preflight()` (changes evidence shape from 04A), not as a separate apply-only phase. The 04B preflight generates a fresh identity; the 04A identity is not consumed.
- **Single Terra execution:** User chose to execute all of 04B (calibration + runner apply + verifier) in one Terra task, mirroring the 03B pattern.
- **Dataset partitioning:** `forecast_model` partitioned by `(horizon, outer_season)`, `forecast_prediction` partitioned by `(season, week)`, all others compact.
- **Terminal manifest:** `forecast-manifest.json` (signed, written last) at `artifacts/research/data-first-football-v1/forecasts/runs/{run_id}/`.
- **Verifier independence:** Must not import producer offset/head/horizon/calibration code. AST import-boundary test enforced.

## Work Completed

1. Loaded start-session skill, reviewed AGENTS.md, CONTEXT.md, and last 3 days of session logs.
2. Explored forecast codebase: runner (664 lines), data contracts (243 lines), heads (294 lines), horizons (145 lines), offsets (207 lines), ratings runner apply pattern (693 lines), lake primitives (942 lines), existing tests (617 lines).
3. Reviewed all V5 contracts: umbrella 04, 04A (Implemented), 04B Draft, common contract, roadmap.
4. Produced concrete implementation plan with 8 ordered tasks covering calibration module, runner integration, apply path, manifest builder, independent verifier, test expansion, quality gates, and certification execution.
5. Persisted augmented 04B contract as Approved.
6. Updated plan index.

## Files Modified

- `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` — Draft → Approved with full implementation specifics
- `docs/plans/index.md` — 04B status row updated
- `session_logs/2026-09-17/06-v5-04b-planning.md` — this log

## Validation

- [x] `git diff --check` (pending)
- [x] `mkdocs build --quiet` (pending)

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Fresh Terra task implementing the approved 04B contract.
- **Watch out for:** The preflight evidence shape changes (calibration added). A fresh 04B preflight identity must be generated. The 04A identity (`forecast-v1-20260917-19ca44b-04a`) is not consumed by 04B. Two dead diagnostic identities (`forecast-v1-20260917-367b4a3-04a`, `forecast-v1-20260917-820bb1d-04a`) remain permanently ineligible.

**tags:** ["v5", "forecasting", "calibration", "planning"]
