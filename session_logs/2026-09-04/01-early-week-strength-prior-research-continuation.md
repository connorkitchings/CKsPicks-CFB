# Session: Early-Week Strength-Prior Research Continuation

## TL;DR

- **Worked On:** Prepared the code-bound checkpoint for fresh offseason-context admission and aligned the active research authorities with certified R1 evidence.
- **Outcome:** The returning-production/materializer and R2-lineage repairs are validated. R1 now permits tournaments; a fresh Preview context admission is the only gate before direct and R2 reconstructed research reports.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Approval / Status:** User explicitly authorized staged implementation on 2026-09-04. Contract remains `In Progress` pending the two user-executed checkpoint commits and Preview research artifacts.
- **Blockers:** Commit 1 must establish the code SHA before immutable context materialization. No production or V4 blocker exists.
- **Next:** User executes Commit 1, then materialize and admit a fresh Preview-only context prefix bound to that committed SHA.

## Context and Decisions

- The certified R1 coverage report is `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/coverage.json`; it has `tournaments_permitted: true`.
- The first context admission remains immutable diagnostic evidence. Its returning-production failure was caused by CFBD generated-client camelCase fields, not provider coverage.
- The repair's read-only coverage is 91.9%–93.8% for every required season. A fresh artifact must retain reconstructed provenance, admit only returning production/recruiting/coaching when each passes the existing 90% gate, and record transfers/talent rejection reasons.
- V4, production artifacts, Neon state, web publication, 2026 outcomes, and market-derived inputs remain out of scope.

## Work Completed

- Updated `AGENTS.md`, the ratings roadmap, and the plans index to replace stale R1/R2 status with the certified R1 handoff and fresh-admission gate.
- Amended the active early-week contract with the R1 report URI, code-bound materialization requirement, expected family boundary, and reconstructed-only restrictions.
- Preserved and validated the existing repairs in `scripts/pipeline/materialize_offseason_context.py` and `scripts/pipeline/build_r2_prior_tournament.py`.

## Files Modified

- `AGENTS.md` — current ratings-research status.
- `docs/planning/roadmap.md` — R1 certification and R2 admission sequencing.
- `docs/plans/index.md` — current contract statuses.
- `docs/plans/2026-09-02/early-week-strength-prior-research.md` — current implementation log and certified-R1 amendment.
- `scripts/pipeline/build_r2_prior_tournament.py` — pending user-owned lineage/selection repair.
- `scripts/pipeline/materialize_offseason_context.py` — pending user-owned provenance and idempotency repair.

## Validation

- [x] `uv run ruff check scripts/pipeline/build_r2_prior_tournament.py scripts/pipeline/materialize_offseason_context.py`
- [x] `uv run pytest -q tests/ratings/test_offseason_context.py tests/ratings/test_priors.py tests/ratings/test_successor_tournaments.py tests/test_v4_feature_reference.py tests/test_game_ordinal_training.py` — 44 passed
- [x] `uv run mkdocs build --quiet`
- [ ] `git diff --check` — run immediately before the user commit

## Amendments and Blockers

- None. The pending repair preserves the approved interfaces, provenance rules, research-only boundary, and R1/R2 sequencing.

## Handoff Notes

- **Resume at:** User executes Commit 1 with all files listed above, then use its full `HEAD` SHA to materialize a fresh Preview context prefix.
- **Watch out for:** Do not use the old failed prefix as a parent, permit strict/locked/refit/publication behavior, or send output outside `artifacts/research/rating-successor-v2/`.

**tags:** ["modeling", "ratings", "preseason", "research", "context"]
