# Session: Early-Week Strength-Prior Research Implementation

## TL;DR

- **Worked On:** Implemented the approved offseason-context admission boundary
  and the direct/R2 research-runner integration.
- **Outcome:** Both research paths are code-complete and fail closed. V4,
  production state, and the published Week 1 artifact remain untouched.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-02. Contract remains `In Progress`: the required immutable source
  admission and R1 certificate have not yet been materialized.
- **Blockers:** No normalized historical offseason source refs exist, and R2
  remains blocked until R1 publishes `tournaments_permitted: true`.
- **Next:** Materialize family refs and run
  `build_offseason_context_admission.py` in Preview; use its admitted context
  ref/report to run direct reconstructed research and, after R1, R2.

## Context and Decisions

- The active V4 Alabama–East Carolina prediction was reproduced exactly from
  its immutable feature snapshot. This work deliberately does not change that
  run or use its market line as an input, gate, or override.
- A context family is strict only with complete pre-kickoff effective-time
  evidence, including an authentic pre-kickoff 2026 retrieval. Complete but
  insufficiently evidenced historic data is explicitly reconstructed.
- Reconstructed direct candidates are research-only: locked validation, refit,
  bundle creation, readiness, and publication remain unavailable.
- R2 context Ridge candidates remain opt-in through both an admission report
  and a context DatasetRef; the existing non-context roster is unchanged.

## Work Completed

- Added `src/cks_picks_cfb/ratings/offseason_context.py` with required
  source-family schemas, canonical mapping, market-field rejection, coverage
  and provenance classification, strict/reconstructed state, and explicit
  research-only opt-in.
- Added `scripts/pipeline/build_offseason_context_admission.py`, a
  Preview-only immutable context/ref/report publisher that writes a rejected
  diagnostic report when no family passes.
- Extended `build_r2_prior_tournament.py` to consume an admission
  report/ref pair, enable context Ridge candidates only when admitted, preserve
  the R1 permit check, and retain the context lineage in its manifest.
- Extended the direct candidate/evaluation CLIs to bind a context admission
  report, reject feature references that omit an admitted family, and emit
  reconstructed-only strength-gap diagnostics.
- Documented the strict/reconstructed boundary in
  `docs/modeling/early_season_regimes.md` and added admission tests.

## Files Modified

- `src/cks_picks_cfb/ratings/offseason_context.py` — new admission contract.
- `scripts/pipeline/build_offseason_context_admission.py` — new Preview CLI.
- `scripts/pipeline/build_r2_prior_tournament.py` — context-enabled R2.
- `scripts/pipeline/generate_game_ordinal_candidates.py` and
  `scripts/pipeline/evaluate_game_ordinal_predictions.py` — direct research
  integration and diagnostics.
- `tests/ratings/test_offseason_context.py` — strict/reconstructed,
  provenance, and rejection coverage.
- `docs/modeling/early_season_regimes.md` — permanent research boundary.

## Validation

- [x] Focused: `uv run pytest -q tests/ratings/test_offseason_context.py tests/ratings/test_priors.py tests/ratings/test_successor_tournaments.py tests/test_v4_feature_reference.py tests/test_game_ordinal_training.py` — 41 passed.
- [x] Full: `uv run pytest -q` — 632 passed, 2 skipped.
- [x] Scoped Ruff — all checks passed.
- [x] Python compilation for all changed modules/scripts.
- [x] `uv run mkdocs build --quiet`.
- [x] `git diff --check`.

## Amendments and Blockers

- No material amendment. The research-report execution is intentionally
  deferred: the configured Preview R2 credentials are incomplete and the
  catalog has no normalized historic family refs. This is an external-state
  dependency, not a reason to weaken the strict/reconstructed boundary.

## Handoff Notes

- **Resume at:** Build immutable, source-specific normalized refs for returning
  production, transfers, recruiting, coaching, and optional talent, then run:

  ```text
  CFB_STORAGE_BACKEND=r2 zsh scripts/ops/with_preview_env.sh \
    uv run python scripts/pipeline/build_offseason_context_admission.py \
    --environment preview --team-universe-ref-uri <REF> \
    --family-ref coaching=<REF> ... \
    --context-uri artifacts/research/rating-successor-v2/.../context.parquet \
    --context-ref-uri artifacts/research/rating-successor-v2/.../context-ref.json \
    --report-uri artifacts/research/rating-successor-v2/.../admission-report.json
  ```

- **Watch out for:** Add `--allow-reconstructed-context` only for the
  Preview R2 research runner. It must never appear in a strict V4/refit or
  publication command.

**tags:** ["modeling", "early-season", "ratings", "research"]
