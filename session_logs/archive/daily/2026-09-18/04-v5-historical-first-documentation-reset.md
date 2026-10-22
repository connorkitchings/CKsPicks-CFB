# Session: V5 Historical-First Documentation Reset

## TL;DR

- **Worked On:** Implemented the approved V5 historical-first documentation and contract reset.
- **Outcome:** Historical validation through 2025 is now the active V5 priority. Contract 04/04B is reopened pending independent computational forecast verification; 05 remains tooling-only; 06-09 are approved but deferred behind Contracts 10-12 and explicit historical-readiness acceptance.
- **Plan Contract:** `docs/plans/2026-09-18/v5-historical-first-documentation-reset.md`
- **Approval / Status:** User explicitly authorized implementation on 2026-09-18; contract is Implemented.
- **Blockers:** None for this documentation reset. Contract 10 is the next Draft research contract and requires separate approval.
- **Next:** Review and approve Contract 10 before starting any historical audit. Do not execute 07-09 unless 10-12 close, historical readiness is accepted, and the 2026 contracts are re-reviewed.

## Context and Decisions

- V5 development remains 2015-2019 and 2021-2025; 2020 remains excluded.
- 2025 is development evidence, not an untouched holdout. All historical fits,
  transforms, priors, adjustments, predictions, and calibration remain subject
  to chronological cutoff requirements.
- The current forecast verifier validates signed-manifest metadata and declared
  references, but does not independently reconstruct forecast outputs or their
  computations. This limitation reopens 04/04B eligibility without changing
  historical artifacts or session records.
- Diagnostic rehearsal and retrospective replay remain permanently distinct from
  predictive-quality and prospective evidence.

## Work Completed

- Added the implementation contract and Draft Contracts 10 (foundation audit),
  11 (forecast verification closure), and 12 (historical results/readiness review).
- Aligned the canonical roadmap, contract index, V5 common contract, onboarding
  summaries, requirements, methodology, evaluation policy, and shadow runbook.
- Reopened 04/04B as In Progress with a dated amendment; preserved 04A history
  and 05 tooling completion while correcting their eligibility claims.
- Deferred 06-09 behind historical review, explicit user acceptance, and later
  application-contract re-review.
- Extended the documentation-authority regression suite to enforce the new
  sequence and reject stale 04B, replay, and prospective-evidence claims.

## Files Modified

- `docs/plans/2026-09-18/v5-historical-first-documentation-reset.md` — implementation record and completion status.
- `docs/plans/2026-09-18/10-v5-historical-foundation-audit.md`, `11-v5-forecast-verification-closure.md`, and `12-v5-historical-results-and-readiness-review.md` — new Draft follow-on contracts.
- `docs/planning/data-first-football-forecasting-roadmap.md`, `docs/plans/index.md`, and V5 04-09 contracts — lifecycle, eligibility, and deferral authority.
- `tests/test_data_first_documentation_authority.py` — historical-first authority protections.

## Validation

- [x] `uv run pytest -q tests/test_data_first_documentation_authority.py` — 36 passed.
- [x] `uv run ruff check tests/test_data_first_documentation_authority.py` — passed.
- [x] `uv run mkdocs build --quiet` — passed.
- [x] `git diff --check` — passed.

## Amendments and Blockers

- None. The reset preserves artifact bytes and dated session records; it only
  corrects current authority, lifecycle, and downstream eligibility.

## Handoff Notes

- **Resume at:** Open a fresh implementation task only after approving
  `docs/plans/2026-09-18/10-v5-historical-foundation-audit.md`.
- **Watch out for:** Do not call the current forecast artifact certified or an
  eligible forecast parent until Contract 11 succeeds. Do not treat a 2026
  replay or `live` timing label as prospective evidence.

**tags:** ["v5", "documentation", "historical-validation", "forecast-verification", "contracts"]
