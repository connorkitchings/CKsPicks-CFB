# Session: V5-04B Certification Execution

## TL;DR
- **Worked On:** Executed the V5-04B certification sequence (preflight → apply → verify → idempotent repeat)
- **Outcome:** Certified Preview artifact `forecast-v1-20260917-4600ddd-04b` at commit `4600dddd3e97373880d29a549f4447367940cf37`
- **Plan Contract:** `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` (Implemented)
- **Approval / Status:** User authorized certification execution after code commit
- **Blockers:** None
- **Next:** Contract 05 prospective readiness and shadow tooling

## Context and Decisions
- Initial apply attempt failed with partition key mismatch error
- Fixed by iterating over partition groups and calling sink with correct partition dict
- Committed fix as `4600ddd` and re-ran certification sequence
- All steps passed: preflight, apply, verify, idempotent repeat

## Work Completed

### Preflight (dry run)
- Run ID: `forecast-v1-20260917-4600ddd-04b`
- Commit: `4600dddd3e97373880d29a549f4447367940cf37`
- Cutoff: `2026-09-17T16:40:02Z`
- Selected horizon: `expanding` (matches 04A)
- Row counts: registry 4, model 16, prediction 7318, calibration 8, comparison 4, selection 2
- Calibration variances: margin 361-375, total 311-326 across 2022-2025
- Evidence SHA: `5777b71e6be32ee95bb32b0f2ebc6ad74ff0fc8e3fc8a2ff3ba1077f53633329`
- Zero warnings, all 6 dataset plans present

### Apply (evidence-bound write)
- All 7 datasets written to R2 Preview
- Manifest written last at `artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast-manifest.json`
- `already_applied: false`, `state: applied`
- Selected horizon: `expanding`

### Independent verification
- Verifier confirmed `verified: true`
- Identity SHA: `ce2c2a2d47bc81225f8f1d04fb17f3114f7b6e3ecf61fd3bfea1ef30dc0ad137`
- Output count: 6 (all datasets verified)
- Selected horizon: `expanding`

### Idempotent repeat
- Second apply returned `state: already_applied`
- No recomputation, no writes
- Manifest URI unchanged

## Files Modified

### Code fix
- `scripts/research/run_data_first_forecasts.py` — fixed partitioned dataset handling in apply sink

### Documentation
- `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` — marked all DoD items complete, added certified artifact section
- `docs/plans/index.md` — updated 04B status to Implemented with certification details
- `docs/planning/data-first-football-forecasting-roadmap.md` — updated current checkpoint and contract 04 status

## Validation
- [x] Preflight evidence reviewed: zero warnings, all 6 dataset plans, calibration variances reasonable
- [x] Apply succeeded: all 7 datasets written, manifest last
- [x] Verifier confirmed: `verified: true`, all outputs match
- [x] Idempotent repeat: `already_applied`, no writes
- [x] Documentation updated: contract, index, roadmap

## Amendments and Blockers
- **Amendment 1 (partitioned dataset handling):** Initial apply failed with `StorageError: forecast_model partition keys must be ('horizon', 'outer_season')`. The sink was being called with empty partition dict for all outputs. Fixed by checking if dataset is partitioned and iterating over partition groups, calling sink with correct partition dict for each group. Committed as `4600ddd`.

## Handoff Notes
- **Resume at:** Contract 05 prospective readiness and shadow tooling
- **Watch out for:** The certified artifact is a frozen shadow candidate. It is development evidence, not prospective evidence. Contract 05 will evaluate live readiness.

**tags:** ["v5", "forecasting", "certification", "preview"]
