# Session: Operational V5 historical scoring

## TL;DR

- **Worked On:** The owner-approved first scoring of the serving recipe on its own input lineage, with an earlier-only bridge.
- **Outcome:** Operational V5 on 2022 to 2025: margin MAE 13.7424, total MAE 13.4383 (3,659 games per target). Flat totals and early-season margin bias are confirmed for the serving recipe.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved on 2026-11-14 ("Yes, score it"). Contract stays `Draft`.
- **Blockers:** None.
- **Next:** Owner decides whether to measure bridge contribution spread and extend the temporal check upstream.

**tags:** ["model-research", "baseline-audit", "scoring", "ratings-lab"]

## Context and Decisions

- Used the existing evaluation code unchanged; only the inputs differ (serving states, rebuild feature frame and offsets). The serving bundle's through-2025 coefficients were not used, to avoid leakage.
- Read-only retrieval of two rebuild forecast files, both matching the root manifest.
- Paired intervals come from the current `paired_comparison` (90%, season/week blocks), labelled as such; the protocol amendment is still only proposed.

## Work Completed

- Compared the September and rebuild feature frames: identical except offsets.
- Harness check: experiment states plus the September frame reproduce the rerun's predictions exactly.
- Fitted the bridge chronologically on the serving states and scored 2022 to 2025 and the early group (2018, 2019, 2021); wrote predictions and a scorecard to the local lab output.

- Next approved step ("Yes, run slices"): ran the existing slice functions on both models for 2021 to 2025. The historical column reproduces the published report cell for cell. For Operational V5: neutral-site margin bias -4.32 (unchanged), non-conference margin MAE unchanged at 15.37, all of the repair's gain in conference and later-season games, early weeks equal or worse (week 2 MAE 16.58, bias +5.85), total bias about one point smaller but still -2.6 in the lowest third of predicted totals.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — scoring section, capability table, next scope
- `docs/plans/index.md` — state line
- `docs/planning/direction-2026-11-14.md` — which diagnostics findings are now confirmed for the serving recipe
- Outside the repository: `~/cfb_ratings_lab_v6/output/operational-v5-historical-2026-11-14/`

## Validation

- [x] Harness check: largest prediction difference 0 against the rerun
- [x] Population check inside `common_bridge_predictions` passed (keys and outcomes equal the frozen V5 predictions)
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** remaining step 2 items in the contract's next executable scope.
- **Watch out for:** 2022 to 2025 are previously examined seasons; these numbers are a baseline, not independent evidence. The venue and conference rows used for slicing come from an unpinned cache.
