# Session: Historical reproduction rerun of the V5 repair experiment

## TL;DR

- **Worked On:** The owner-approved local rerun of `scripts/research/v5_intended_update_review.py`, the first check of step 2 in the baseline audit contract.
- **Outcome:** The retained 2026-09-28 results are reproduced: 2,543 numeric values agree to 2.8e-14 with identical structure. The 12 output files have equal row counts but different hashes, so row-level identity with the originals is not proven.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved the rerun on 2026-11-14 ("Yes, rerun it"). Contract stays `Draft`.
- **Blockers:** None.
- **Next:** Owner decides whether to approve an earlier-only bridge fit on the serving states, the first new scoring in this work.

**tags:** ["model-research", "baseline-audit", "reproduction", "ratings-lab"]

## Context and Decisions

- Ran offline through the script's `--verified-cache` option. The cache was built from the hash-verified local corpus stage and the control-input mirror; no network source was used.
- This reproduces the historical experiment on the 2026-09-21 inputs. It is not a check of the serving model; that is the separate operational-equivalence step.

## Work Completed

- Built `~/cfb_ratings_lab_v6/cache-intended-update-2026-11-14/` (nine tables, hashes in `_index.json`).
- Reran the script (100 seconds): four arms replayed (35,740 states each), bridges refitted chronologically, both built-in gates passed.
- Compared the new report with the retained results JSON section by section and recorded the outcome in the contract.

- Third approved step ("Yes, compare"): compared the serving bridge run's historical states with the rerun's repaired arm, row by row. Same keys, weeks and cutoffs in all 35,740 rows; contributing game sets equal in 35,698. Values differ: rating mean median absolute difference 0.023 standardized units (99th percentile 0.287, largest 0.864, correlation 0.9965), about twice as large in 2022 to 2025 as earlier. Priors differ in 31,890 rows. Operational V5's historical accuracy is therefore still unmeasured.

- Fourth approved step ("Yes, trace it"): read the removed builder from git history and compared per-game contributions. The serving states were built by the same replay code on the corrected rebuild's nine historical frames. Both sets use fixed priors of their own lineage (an earlier inference that the serving run carried its own priors was wrong). Exposure is equal in all 170,337 shared contributions; game values differ, and the share differing by more than 0.25 rises from about 3% (2015 to 2019) to about 14% (2021 to 2025), following the rebuild's admitted scoring decisions by season.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — rerun section, capability table, next scope
- `docs/plans/index.md` — state line
- Outside the repository: the cache folder and `~/cfb_ratings_lab_v6/output/intended-update-rerun-2026-11-14/`

## Validation

- [x] Script gates: certified replica fidelity; refitted bridge against 7,318 frozen predictions within 1e-9
- [x] Numeric comparison with the retained results: largest absolute difference 2.8e-14 over 2,543 values
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** operational equivalence (step 2, second check).
- **Watch out for:** the rerun's output hashes differ from the retained ones; do not cite them as the original artifacts.
