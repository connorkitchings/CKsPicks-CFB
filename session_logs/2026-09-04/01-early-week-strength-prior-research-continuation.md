# Session: Early-Week Strength-Prior Research Continuation

## TL;DR

- **Worked On:** Prepared the code-bound checkpoint for fresh offseason-context admission and aligned the active research authorities with certified R1 evidence.
- **Outcome:** The returning-production/materializer and R2-lineage repairs are validated. R1 permits tournaments and the context corpus is admitted. The direct path now has an approved reconstructed-only FBS-entry fallback policy; commit this code boundary before rebuilding its immutable references.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Approval / Status:** User explicitly authorized staged implementation on 2026-09-04. Contract remains `In Progress` pending the two user-executed checkpoint commits and Preview research artifacts.
- **Blockers:** A new user-executed repair commit must establish the code SHA before immutable direct-reference materialization. No production or V4 blocker exists.
- **Next:** User executes the repair commit, then build fresh Preview-only direct feature/model-ready refs bound to that SHA and run the direct selection report.

## Context and Decisions

- The certified R1 coverage report is `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/coverage.json`; it has `tournaments_permitted: true`.
- The first context admission remains immutable diagnostic evidence. Its returning-production failure was caused by CFBD generated-client camelCase fields, not provider coverage.
- The repair's read-only coverage is 91.9%–93.8% for every required season. A fresh artifact must retain reconstructed provenance, admit only returning production/recruiting/coaching when each passes the existing 90% gate, and record transfers/talent rejection reasons.
- V4, production artifacts, Neon state, web publication, 2026 outcomes, and market-derived inputs remain out of scope.
- The V4 core uses provider-facing aliases while admitted context uses canonical
  identities. Normalize both sides before joining; this resolves the broad
  apparent coverage gap without changing evidence.
- Eight returning-production absences are declared FBS-entry cases. Preserve
  them as `fbs_history_unavailable`; do not manufacture values from FCS data.

## Work Completed

- Updated `AGENTS.md`, the ratings roadmap, and the plans index to replace stale R1/R2 status with the certified R1 handoff and fresh-admission gate.
- Amended the active early-week contract with the R1 report URI, code-bound materialization requirement, expected family boundary, and reconstructed-only restrictions.
- Preserved and validated the existing repairs in `scripts/pipeline/materialize_offseason_context.py` and `scripts/pipeline/build_r2_prior_tournament.py`.
- Added the canonical-alias and declared FBS-entry boundary to the reconstructed
  V4 reference path. Direct research will record a base-variant fallback for
  entrant-involved games rather than omit the admitted family or impute it.

## Files Modified

- `AGENTS.md` — current ratings-research status.
- `docs/planning/roadmap.md` — R1 certification and R2 admission sequencing.
- `docs/plans/index.md` — current contract statuses.
- `docs/plans/2026-09-02/early-week-strength-prior-research.md` — current implementation log and certified-R1 amendment.
- `scripts/pipeline/build_r2_prior_tournament.py` — pending user-owned lineage/selection repair.
- `scripts/pipeline/materialize_offseason_context.py` — pending user-owned provenance and idempotency repair.
- `scripts/pipeline/build_v4_preseason_feature_reference.py` — canonical joins and declared FBS-entry availability.
- `contracts/teams.py` — canonical FIU alias.
- `tests/test_v4_feature_reference.py` — alias and FBS-entry regression coverage.

## Validation

- [x] `uv run ruff check scripts/pipeline/build_r2_prior_tournament.py scripts/pipeline/materialize_offseason_context.py`
- [x] `uv run pytest -q tests/test_v4_feature_reference.py tests/ratings/test_offseason_context.py` — 11 passed after the alias repair
- [x] `uv run mkdocs build --quiet`
- [ ] `git diff --check` — run immediately before the user commit

## Amendments and Blockers

- The approved FBS-entry exception changes only reconstructed direct research.
  It is checked in, fail-closed for every undeclared absence, and cannot affect
  strict/locked/refit/publication behavior.

## Handoff Notes

- **Resume at:** User executes the FBS-entry repair commit, then use its full
  `HEAD` SHA to materialize fresh direct references under the isolated Preview
  prefix.
- **Watch out for:** Do not use an FCS proxy, let an undeclared missing key
  pass, permit strict/locked/refit/publication behavior, or send output outside
  `artifacts/research/rating-successor-v2/`.

**tags:** ["modeling", "ratings", "preseason", "research", "context"]
