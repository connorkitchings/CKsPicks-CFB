# Session: Model Accuracy Panel (Backtest Context for Picks)

## TL;DR

- **Worked On:** Built the backtest-accuracy context panel that ships with the
  predictions reveal: extractor script distilling the frozen V4 tournament
  reports into a checked-in web JSON, plus a `ModelAccuracyPanel` component
  gated to predictions mode.
- **Outcome:** All quality gates green (361 passed / 2 skipped, ruff, contracts,
  web lint/typecheck/publication tests/build). Local smoke test verified the
  panel renders correct numbers in predictions mode and renders nothing in
  market mode. Invisible in production until the Aug 28 flip.
- **Plan Contract:** N/A (fast path; scoped feature with established patterns,
  user-approved approach in-session)
- **Approval / Status:** User approved: accuracy = points off final result
  (MAE), 1 decimal; no win% (no historical lines exist); panel only; no rush.
- **Blockers:** None.
- **Next:** Merge rides along with the next main push; panel goes live at the
  Aug 28 predictions flip.

## Context and Decisions

- Accuracy definition (user decision): **MAE vs final result** — spreads =
  points off final margin, totals = points off final total. No win% or ROI:
  historical betting lines are quarantined and cannot grade predictions
  (`legacy_market_references` contract).
- Authoritative source: the deployed bundle manifest embeds the immutable
  routing report (`artifacts/preview/refs/v4/locked-report-strict-20260818.json`)
  containing official champion routing + pooled/seasonal OOF metrics and locked
  2025 reports. The extractor distills that report — champion decisions are
  read from `routing`, never hardcoded.
- Baseline-champion routes (e.g. total/game_1 — the Week 0 totals route) have
  no locked-2025 report block; their locked MAE is computed from the frozen
  locked-candidates CSV (`baseline_prediction` vs `actual`, deduped per game,
  consistency-checked).
- Display: 2025 leads (`15.2 pts off final margin (2025, n=83)`), pooled
  2022–24 second (`16.0 pts avg 2022–24 (n=243)`), methodology footnote
  states out-of-sample evaluation pre-refit, not betting results. "Held-out"
  wording dropped per user feedback.
- **Legacy label discovery:** production prediction rows store `preseason`
  (legacy label), not `game_1` — first smoke test caught it. The panel maps
  legacy → canonical exactly like `canonical_prediction_regime` in the
  pipeline (`preseason→game_1`, `one_game→game_2`, `two_games→game_3`,
  `three_games→game_4`).
- Established route: intentionally omitted from the JSON (V2-lineage model,
  separate story) until those routes activate.

## Work Completed

1. `scripts/pipeline/extract_model_accuracy.py` — distills manifest + routing
   report (+ locked CSV for baseline champions) into
   `web/src/data/model-accuracy.json` with full provenance (bundle id, manifest
   SHA, report URI, selection design SHA).
2. `tests/test_extract_model_accuracy.py` — 6 tests (champion metrics for
   candidate/baseline champions, locked report vs CSV paths, dedup +
   inconsistency rejection, distill shape/JSON-serializability).
3. `web/src/data/model-accuracy.json` — generated (game_1: spread 15.98 OOF /
   15.16 locked; total 15.16 OOF / 15.73 locked; game_2–4 included).
4. `web/src/components/ModelAccuracyPanel.tsx` — per-route spread/total MAE
   stats, legacy-label normalization, methodology footnote.
5. `web/src/app/page.tsx` — panel mounted between WeekNav and GamesList, gated
   `publicationScope.mode === "predictions"`.
6. `web/README.md` — component + regeneration instructions.

## Files Modified

- `scripts/pipeline/extract_model_accuracy.py` (new)
- `tests/test_extract_model_accuracy.py` (new)
- `web/src/data/model-accuracy.json` (new, generated)
- `web/src/components/ModelAccuracyPanel.tsx` (new)
- `web/src/app/page.tsx`
- `web/README.md`

## Validation

- [x] `uv run ruff format --check .` + `ruff check .` (repo-wide, clean)
- [x] `uv run python contracts/validation.py`
- [x] Full suite: 361 passed, 2 skipped
- [x] Web: lint, typecheck, `test:publication` (3/3), production build
- [x] Local smoke (`next start` + production DB, read-only): predictions mode
      renders "Model accuracy — first game of the season" with 15.2/15.7 (2025,
      n=83) + 16.0/15.2 (2022–24, n=243); market mode renders zero accuracy
      content (fail-closed boundary holds)

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** commit + push to main (invisible until flip). Aug 28: after
  the predictions flip + redeploy, verify the panel appears under WeekNav.
- **Watch out for:** regenerate the JSON only via the extractor when a new
  bundle/tournament exists; never hand-edit. Established-route numbers join
  when those routes activate (Week 1+).

**tags:** ["web", "accuracy", "backtest", "v4", "predictions-mode"]
