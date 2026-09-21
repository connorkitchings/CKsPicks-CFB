# Session: V5-12A Conditional Historical Scorecard Implementation & Preflight

## TL;DR

- **Worked On:** Contract 12A conditional historical scorecard code, unit tests, and Preview R2 preflight execution.
- **Outcome:** Scorecard logic and CLI implemented and verified; 21 unit tests passed; preflight executed successfully against Preview R2 with full 7,318-row population; 2025 headline and pooled 2022-2025 metrics computed in 7.0s. Evidence written to `/tmp/scorecard_preflight.json`.
- **Plan Contract:** `docs/plans/2026-09-19/12a-v5-conditional-historical-scorecard.md` (Status: In Progress)
- **Approval / Status:** User authorized execution ("Let's do sessions A and B simultaneously").
- **Blockers:** None for preflight. Apply to Preview R2 requires a clean committed worktree per contract commit policy.
- **Next:** User executes git commit checkpoint; then run `apply` and `verify`.

## Context and Decisions

- Contract 12A requires:
  - Exact entry record: `conditional-v1-20260919-9265314-11a` verification manifest.
  - Fail-closed re-reading of raw SHA `5a7e7d48...`, canonical SHA `7ce47863...`, and record SHA `7ee050b4...`.
  - Headline 2025 (n=934 per target), context 2022-2024, pooled 2022-2025 (n=3659 per target), and slices for completed game stages 0, 1, 2, 3, 4+.
  - Recomputed Gaussian CRPS and central 50/80/95% intervals from final target-season calibration variance.
  - Zero V4 comparison, zero readiness recommendation, permitted use `conditional_historical_results_only`.
- Preflight run completed cleanly in 7.0s:
  - 2025 Headline:
    - Margin: MAE 14.38, RMSE 18.38, bias -0.84, CRPS 10.34, 50% cov 55.1%, 80% cov 79.9%, 95% cov 94.8% (n=934)
    - Total: MAE 13.20, RMSE 16.39, bias +2.10, CRPS 9.31, 50% cov 52.8%, 80% cov 82.1%, 95% cov 97.0% (n=934)
  - Pooled 2022-2025:
    - Margin: MAE 14.64, RMSE 18.50, bias -0.12, CRPS 10.43 (n=3659)
    - Total: MAE 13.54, RMSE 16.90, bias +1.46, CRPS 9.54 (n=3659)

## Work Completed

- Created `src/cks_picks_cfb/forecast/historical_scorecard.py` (entry gate validation, data loading, population validation, metric leaf calculation, report rendering).
- Created `src/cks_picks_cfb/forecast/scorecard_publication.py` (preflight, signed publication, verification).
- Created `scripts/research/run_v5_conditional_scorecard.py` (CLI with `preflight`, `apply`, and `verify`).
- Created `tests/test_historical_scorecard.py` (21 unit tests, all passing).
- Executed Preview R2 dry run / preflight; output saved to `/tmp/scorecard_preflight.json`.

## Files Modified

- `src/cks_picks_cfb/forecast/historical_scorecard.py` — new
- `src/cks_picks_cfb/forecast/scorecard_publication.py` — new
- `scripts/research/run_v5_conditional_scorecard.py` — new
- `tests/test_historical_scorecard.py` — new
- `session_logs/2026-09-21/01-v5-12a-conditional-historical-scorecard.md` — this log

## Validation

- [x] `uv run pytest tests/test_historical_scorecard.py` — 21 passed.
- [x] `uv run python scripts/research/run_v5_conditional_scorecard.py preflight --run-id conditional-v1-20260921-scorecard --out /tmp/scorecard_preflight.json` — passed.
- [x] Ruff check and format clean.
- [x] `git diff --check` clean.

## Handoff Notes

- **Resume at:** Commit codebase changes, then run `uv run python scripts/research/run_v5_conditional_scorecard.py apply --run-id conditional-v1-20260921-scorecard --preflight-evidence /tmp/scorecard_preflight.json`.

**tags:** ["v5", "contract-12a", "scorecard", "preflight"]
