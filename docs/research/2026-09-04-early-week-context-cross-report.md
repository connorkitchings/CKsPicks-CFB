# Early-Week Context Cross-Report — Direct and R2 Research Tracks

- **Date:** 2026-09-04
- **Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Feature track:** reconstructed (research-only, activation-ineligible)
- **Code binding:** R2 tournament at commit `4c6e6103ca7d8bbe8820a46c34432055f86e85a9`; context corpus bound to `786580ec58b76ade6489251f4c2b18af80e0430e`
- **Production impact:** none. V4 (`week0-2026-v4-strict-20260818-r2`) remains the unchanged champion; no bundle, readiness, Neon, or publication state was touched.

## Evidence base

| Artifact | URI |
|---|---|
| R1 foundation (certified) | `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/` |
| Context admission (reconstructed) | `artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/admission-report.json` |
| Direct selection report | `artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/direct/reconstructed-selection-report-v1.json` |
| R2 fold metrics | `artifacts/research/rating-successor-v2/r2-prior-20260904-4c6e610/fold-metrics/combined.parquet` |
| R2 selection report | `artifacts/research/rating-successor-v2/r2-prior-20260904-4c6e610/selection-report.json` (SHA `d617f576…`) |
| R2 manifest | `artifacts/research/rating-successor-v2/r2-prior-20260904-4c6e610/manifest.json` |

Admitted families: `returning_production`, `recruiting`, `coaching` (all reconstructed; ≥98.46% season coverage). Rejected: `transfer_portal` (no 2015 data), `talent` (no authentic 2026 capture).

## Direct track findings (Games 1–4, 2022–2024 folds, 522,198 stacked rows)

- **Game 1 spread:** context variants produce a meaningful, bootstrap-significant MAE lift over the 17.447 baseline across all four direct/points designs; the selected variant is `recruiting_complete`. This directly addresses the strength-gap blind spot exposed by Alabama–East Carolina.
- **Game 1 total:** `returning_production_complete` lifts via direct CatBoost (baseline 15.081).
- **Later routes are mixed:** Game 3 spread passes on two designs (`recruiting_complete`); totals pass on blends at Games 2–4 (`coaching`, `recruiting_complete`, `returning_production_complete`); **Game 4 spread shows no passing design**.
- Strength-gap diagnostics (pregame-baseline top decile): high-gap cohort MAE 15.139 over 52,386 rows — the gap cohort remains the hardest segment even with context.

## R2 rating-track findings (between-season priors, folds 2018/2019/2022/2023/2024)

- **Winner: `continuity_ridge_alpha_0_1`** — all checks passed; selected under the 0.5% simplicity tie rule (raw-best was `alpha_100` at 26.8026 primary MAE; the four alpha variants span 26.803–26.843, a 0.15% spread, all complexity 4).
- Context candidates beat every non-context candidate on full-season margin MAE **in every fold**; aggregate 13.142 vs 13.164 (best non-context, `terminal_ewma_half_life_2`, ≈0.17% better) and 14.196 (`neutral_population` baseline, ≈7.4% better). The neutral baseline is the only gate-ineligible candidate.
- Total MAE is flat (~13.26) across all candidates — the prior family choice moves margin, not totals.
- **Interpretation caution:** the four alpha variants are nearly indistinguishable, so the observed lift is attributable mostly to the continuity (prior-season terminal state) structure rather than to strong context coefficients. The context signal is real but weak at the rating-prior layer; it is stronger and better-isolated in the direct Game 1 path.

## Cross-report decision

1. **Convergent conclusion:** reconstructed offseason context (recruiting, returning production, coaching) carries genuine early-week signal — largest and most statistically isolated at Game 1 spread (`recruiting_complete`) and Game 1 total (`returning_production_complete`) in the direct track, and directionally positive as rating priors (`continuity_ridge`) in R2.
2. **No activation:** every artifact here is reconstructed-track and activation-ineligible. No locked-2025 evaluation, refit, bundle, readiness, or publication may consume these reports. A strict, authentic pre-kickoff capture remains the gating requirement for any future promotion proposal.
3. **R3/R4 sequencing:** R2 completed with all gates passed, so the between-season prior stage is settled in the research lane (`continuity_ridge_alpha_0_1`). R3 (within-season updates) is next in the research sequence, still isolated in Preview.
4. **Follow-ups recorded:** (a) the R2 run emitted non-fatal NumPy warnings (divide-by-zero/overflow/invalid in the head's matmul) — investigate the state rows that produce non-finite features before R3; (b) Game 4 spread shows no context lift — do not carry context into that route without new evidence; (c) the ~13–14% of completed games unmatched to FBS-vs-FBS states (FCS-involved) are excluded from head evaluation by design.

## Reproduction

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/build_r2_prior_tournament.py \
  --environment preview \
  --r1-foundation-manifest-uri artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/foundation/manifest.json \
  --certify-report-uri artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/coverage.json \
  --context-admission-report-uri artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/admission-report.json \
  --context-ref-uri artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/context-ref.json \
  --allow-reconstructed-context \
  --output-prefix artifacts/research/rating-successor-v2/r2-prior-20260904-4c6e610 \
  --as-of 2026-09-04T16:09:46Z \
  --expected-code-sha 4c6e61030a301d67f24037f238c6c2d20faeed96
```

Two lineage repairs were required and committed before this run: `278120a` (doubled `foundation/` path in outcome-ref loading) and `4c6e610` (game-label join and `game_id` normalization for the evaluation head). Both are schema-contract alignments between the R1 artifact layout and the head; neither touches shared library behavior.
