# V5-12A: Conditional Historical Scorecard

- **Status:** Implemented
- **Created:** 2026-09-19
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact Contract 12A plan with "PLEASE IMPLEMENT THIS PLAN" on 2026-09-19.
- **Planning log:** `session_logs/2026-09-19/03-v5-12a-conditional-historical-scorecard-planning.md`
- **Implementation log:** `session_logs/2026-09-21/01-v5-12a-conditional-historical-scorecard.md`
- **Commit policy:** Separate scorecard-code and Preview-evidence/report checkpoints; user controls Git operations.

## Goal and entry gate

Publish a transparent V5-only historical scorecard after a successful Contract
11A verification record proves the exact frozen forecast artifact can be
reconstructed. The entry record must carry exact Repair, measurement, rating,
and forecast parent/output hashes and `permitted_use:
conditional_historical_results_only`.

This contract has no entry if 11A records a mismatch, failed comparison, missing
evidence, or a different identity. In that case it publishes no scorecard values.
Development evidence remains 2015–2019 and 2021–2025; reject 2020 and 2026.

The required entry record is exactly
`artifacts/research/data-first-football-v1/forecast-verification/conditional-v1/runs/conditional-v1-20260919-9265314-11a/verification-manifest.json`,
with raw SHA-256
`5a7e7d4861e954feb570d52d0e45f9a50d88918fc91dd825dc0a9d1a9ba1326d`,
canonical SHA-256
`7ce47863e1e34874357f3f503ef1d8f1f232e48c9b199c5aff99dfb5606b93ad`,
and record raw SHA-256
`7ee050b45ea8df9e00f44bdde3159f4d6a2ffe16878a93835e69ad068302cda2`.

## Conditional-use boundary

Outputs are conditional historical development evidence with permitted use
exactly `conditional_historical_results_only`. This status never restores
forecast eligibility; it never authorizes a 2025 final fit, 2026 replay, live forecast,
production promotion, market comparison, or V4 change; create prospective
evidence; or satisfy the final-readiness or Contract 06–09 gates.

Every evidence output and readable report must name the frozen Repair
`repair-v2-20260909T1417Z`, measurement
`possession-v1-measurements-20260915-18fb0aa-r6`, rating
`possession-v1-ratings-20260917-d029526-cert`, and forecast
`forecast-v1-20260917-4600ddd-04b` identities, exact verified hashes, and all
unresolved foundation limitations.

## Scope, metrics, and allowed writes

Calculate V5-only results from the exact 11A-verified output population. Report
2025 as the headline, 2022–2024 as context, and pooled 2022–2025 results.
For margin and total separately, report MAE, RMSE, bias, Gaussian CRPS, central
50/80/95% interval coverage and width, sample counts, exclusions, calibration
fallback/residual counts, and completed-game-stage slices.

Use `prediction - actual` as signed error. Recompute CRPS and intervals from
the final target-season calibration variance; do not reuse the stored
head-selection CRPS. Use central Normal quantiles `0.6744897501960817`,
`1.2815515655446004`, and `1.959963984540054` for 50/80/95%; coverage includes
both endpoints and width is `upper - lower`. Each target's evidence block has
`headline_2025`, `context_by_season` for 2022–2024,
`pooled_2022_2025`, and pooled `by_completed_game_stage` values `0`, `1`, `2`,
`3`, and `4_plus`, each with the full metric leaf.

The verified population is exact and fail-closed: 7,318 target rows / 3,659
games; 896/910/919/934 rows per target in 2022/2023/2024/2025; and per-target
stage counts 573/301/244/253/2,288 for 0/1/2/3/4+. It must report source,
included, and excluded counts plus exclusion reasons; exclusions are zero.
Malformed, duplicate, non-finite, unexpected-season, incomplete-target, or
unmatched-calibration rows block publication rather than becoming exclusions.

Write a signed Preview scorecard and terminal manifest under:

```text
artifacts/research/data-first-football-v1/historical-scorecards/conditional-v1/runs/<run-id>/
```

Publish a readable report under `docs/research/`. Both outputs carry
`permitted_use: conditional_historical_results_only` and
`production_activation_authorized: false`. Do not compare V4, recommend
readiness, retune, refit, change artifacts/configuration, access markets, or
write to catalog, Neon, production, web, or V4.

The implementation exposes a research-only module and CLI with default
no-write preflight, evidence-bound `--apply` requiring a clean committed
worktree, `--verify-manifest-uri`, and report rendering only from a verified
terminal manifest. Use immutable signed `historical-scorecard.json` and
`scorecard-manifest.json` outputs. The independent verifier must revalidate
11A and source references, then recompute counts and metrics without trusting
stored derived values.

## Tasks and acceptance criteria

1. Add bounded scorecard, publication, verification, and report-rendering
   interfaces; prohibit imports of forecast producer modules.
2. Revalidate the successful 11A manifest, its signatures, exact hashes,
   population, output refs, and the four frozen parent identities before
   scoring.
3. Compute and test every declared metric, population/exclusion count,
   fallback count, residual count, and completed-game-stage slice under the
   frozen chronology.
4. Publish signed, Preview-only scorecard evidence and a readable V5-only
   report; independently re-read both, compare recomputed values, and require
   an idempotent repeat.
5. State that the results are conditional historical development evidence and
   list all unresolved limitations. The report makes no readiness recommendation.

The completed scorecard answers the 2025 historical question only. It cannot
clear any blocker or replace the full audit and final review.

## Definition of done and amendments

- [x] A successful, exact-hash Contract 11A record is independently re-read.
- [x] Required V5-only metrics are present for 2025, 2022–2024, and 2022–2025.
- [x] Signed Preview evidence and readable report name all frozen identities and
  limitations.
- [x] No V4 comparison, readiness recommendation, 2026 action, or scorecard is
  emitted after a failed 11A verification.
- [x] Focused tests, full warnings-as-errors suite, Ruff, strict MkDocs,
  contracts checks, and `git diff --check` pass.

Contract 12 remains the only historical-readiness review. Changes to metrics,
populations, conditional-use status, or downstream scope require an approved
amendment before execution.
