# Session: V5-04A Hardening and Preflight Planning

## TL;DR
- **Worked On:** Planned the 04A completion checkpoint after static review of committed `d380765`.
- **Outcome:** Approved plan contract for exact three-URI parent binding, 2018–2019/2021 reported horizons, expanded head_metrics (MAE + Gaussian CRPS by season/stage), bounded stderr progress, regressions, the three-repeat committed no-write Preview preflight, 04A closure, and the 04B wording rebase.
- **Plan Contract:** `docs/plans/2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md` (Approved).
- **Approval / Status:** User approved the plan and both design decisions this session.
- **Blockers:** None for planning. Preflight identity selection is blocked until the user commits the hardening checkpoint.
- **Next:** Fresh Terra task with `implement-plan` at the exact plan path.

## Context and Decisions
- Static review of `d380765` (clean worktree, HEAD of `main`) found two open items: parent validation binds R6/Repair by raw SHA-256 only (`data_first_forecast_v1.py` `verify_rating_parent`), and no 2018/2019/2021 horizon reporting exists despite 04A Task 3.
- The retained rating manifest's `parents` block pins exact URIs; the 03B verifier already enforces URI equality — the fix mirrors `possession_rating_verification.py:2137-2142`.
- User decision: pin **all three** URIs — new `REQUIRED_RATING_MANIFEST_URI` constant plus pinned measurement/repair URI equality.
- User decision: record the work as a thin dated plan contract rather than an 04A-only amendment.
- Reported seasons are evaluated for both heads with the identical procedure but excluded from every gate, bootstrap, and planned output; 2022–2025 remains the sole selection population.
- Exact parent URIs verified from docs: rating `…ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json`; R6 `…measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json`; repair `…repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`.
- Preflight evidence writes to a freshly created `mktemp -d` directory (outside the repo); three identical runs must be byte-equivalent.
- Approval refinements (user, 2026-09-17): scoped-only `ruff format` (dirty-worktree guardrail); 04A + hardening contract reach Implemented only after three passing preflights and committed closure docs; 04B rebases as Draft with a separate explicit approval boundary; `mktemp -d` for evidence outputs; explicit sentence that reporting-only rows are excluded from selection, plan digests, and future 04B apply evidence; added a reporting-population-mismatch negative test.
- Flagged (out of scope): Week 3 production freeze is pending before tonight's 23:30Z kickoff and must be handled by the normal weekly runbook.

## Work Completed
- Investigated committed 04A code (runner, heads, horizons, offsets, contracts, config, tests), 03A/03B precedents, and the 04A/04B contracts.
- Verified `.env` carries the required R2 preview credential variable names (values unprinted).
- Authored and saved the Approved plan contract.

## Files Modified
- `docs/plans/2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md` — new, Approved.
- `session_logs/2026-09-17/03-v5-04a-hardening-planning.md` — this log.

## Validation
- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`

## Amendments and Blockers
- None. The six approval refinements were incorporated directly into the
  not-yet-committed contract body at approval time and are recorded above.

## Handoff Notes
- **Resume at:** Fresh Terra task with the repository-local `implement-plan` skill at `docs/plans/2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md`.
- **Watch out for:** No Preview identity before the user commits the hardening checkpoint; keep the three preflight repeats in one environment; `forecast_identity` payload changes `identity_sha256` (no frozen identity exists); never touch selection gates, registry, or populations; 04B stays Draft until separately and explicitly approved.

**tags:** ["v5", "forecasting", "planning", "preflight", "lineage"]
