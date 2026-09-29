# Session: V5 intended-update repair experiment

## TL;DR

- **Worked On:** Implemented and ran the approved [three-way estimator review](../../docs/plans/2026-09-28/v5-estimator-three-way-review.md) with the user's cutoff-specific repair clarification and a first-boundary timing sensitivity.
- **Outcome:** Exact certified V5 historical replica; full 2015–2019 and 2021–2025 four-arm replay; 2022–2025 paired forecast evaluation; 2026 Week 4 Alabama/South Carolina diagnostic; [research report](../../docs/research/2026-09-28-v5-intended-update-repair-experiment.md).
- **Plan Contract:** `docs/plans/2026-09-28/v5-estimator-three-way-review.md` (Implemented, research only).
- **Approval / Status:** User explicitly requested implementation of the revised plan in this session. No promotion or production change authorized or made.
- **Blockers:** None for the research contract. Separate V6 R2 bucket is unprovisioned; outputs were local and summary JSON is versioned in `docs/research/`.
- **Next:** Review the historical-versus-live boundary discrepancy and early-stage tradeoff before commissioning any successor or promotion contract.

## Context and Decisions

- The repaired arm derives one game-specific four-pass adjusted value at **each** target cutoff, using earlier-week games available at kickoff+6h. The accepted historical control instead freezes a cumulative snapshot at first boundary. The first-boundary game-specific arm separates value-timing from the historical coverage issue.
- Direct read-only Preview R2 import checked the pinned parent SHA-256 values and certified states. The replica matched all 35,740 pregame states: max absolute mean `8.88e-16`, variance `2.22e-16`, exposure `0`. Its bridge matched the frozen 7,318 forecast rows to `2.84e-14`.
- The historical snapshot lookup yielded only 330 usable source-game-role observations. Current-season exposure appeared in 1,926/35,740 historical V5 states versus 29,376/35,740 repaired states. The live 2026 path is distinct and retains Alabama/South Carolina games. This limits promotion inference from historical MAE differences.
- Fixed PPP possessions, priors, 0.60 carryover, `k=8`, scales, population, offsets, and bridge protocol per user instruction. Original optional `k`/garbage-time variants were superseded by that fixed-input instruction; no input tuning or model selection occurred.

## Work Completed

- Added pinned snapshot/prior/state import, exact control stream, and FCS cohort fallback needed for historical parity.
- Added fixed-prior and cutoff-evidence extension to the research replay engine only, four-pass cutoff graph, game-specific and certified cumulative arms, shared exposure updater, and source-contribution explanations.
- Added synthetic weight, chronology, sparse-context, future-result, missing-measurement, and 2019→2021 gap checks. Existing ratings/storage/live regressions passed.
- Ran the common alpha-10 Ridge bridge separately for all four arms on identical keys; 2,000 season/week bootstrap replicates. Repaired headline margin MAE `13.744` versus control `14.320` (gain 90% interval `0.307`–`0.858`); total `13.507` versus `13.662` (`0.115`–`0.201`). Margin stages 0–3 worsened; 4+ improved. Single cumulative and dynamic game-specific states agreed to floating-point precision in the observed complete graphs.
- Reconstructed the read-only 2026 Week 4 live terminal graph. Same priors and exposures gave diagnostic Alabama overall `1.492`, South Carolina `0.880`, compared with accepted `1.433` and `1.439`. This ordering was never used as a selection criterion.
- Direct R2 run and a separate local-cache rerun produced identical report SHA-256 `b7b345b1982812b1879f294ea9eca222fdbb8d8f08f49ac96e788d3005cc625b`. The 2026 diagnostic JSON SHA-256 is `d02f80c8ab81dd0d378128184c3abeaeb5e9d0c7ddf55241712b6506982c625f`.

## Files Modified

- `docs/plans/2026-09-28/v5-estimator-three-way-review.md` — amendment, research completion, fixed-input scope.
- `src/cks_picks_cfb/ratings_lab/replay.py` — lab-only fixed priors and cutoff-evidence interface.
- `src/cks_picks_cfb/ratings_lab/v5_control.py` — pinned historical control and exact fidelity verification.
- `src/cks_picks_cfb/ratings_lab/adjusted_game.py` — four-pass game-specific and certified cumulative evidence.
- `src/cks_picks_cfb/ratings_lab/updaters.py` — shared V5 exposure math.
- `scripts/research/v5_intended_update_review.py` — read-only historical run and deterministic local report.
- `scripts/research/v5_intended_update_live_diagnostic.py` — pinned 2026 Week 4 diagnostic.
- `tests/ratings_lab/test_v5_intended_update.py` — focused proofs and boundary tests.
- `docs/research/2026-09-28-v5-intended-update-repair-experiment.md` and companion JSON files — findings and full machine-readable results.
- `docs/modeling/v5_status.md`, `docs/index.md` — research status links.
- `docs/research/ratings-lab-v1.md` — scope of the local-output experiment while the dedicated bucket is unavailable.

## Validation

- [x] Exact replica and frozen forecast parity gates.
- [x] 6 focused new tests passed.
- [x] 103 scoped ratings lab, V5 measurement/rating/live replay, verification, and storage tests passed before the final focused test additions.
- [x] Full `pytest -q`: 1,488 passed, 3 skipped (before the last bye fixture was added; all 6 focused tests reran successfully).
- [x] Ruff format check and lint on changed Python files.
- [x] `mkdocs build --clean` completed; existing cross-root link warnings remained.
- [x] `git diff --check`.
- [x] Two local historical runs produced an identical logical report hash.

## Amendments and Blockers

- The user-authorized dynamic-cutoff clarification and fixed-input sensitivity clarification are in the plan. The historical sparse-boundary behavior was a verified research finding, not a production change.
- External local data drive was not mounted, so full Parquet traces remain in `/private/tmp/cfb-v5-intended-update-final/`; the deterministic summary and live diagnostic JSON are in `docs/research/` and the scripts can reproduce them from pinned R2 parents. No repository `./data/` was created.

## Handoff Notes

- **Resume at:** Assess the historical/live evidence-semantic mismatch and stage 0–3 margin degradation in a new decision contract before any candidate promotion.
- **Watch out for:** Do not call the historical MAE gain an isolated live estimator fix; the historical control has a major coverage defect that the live path does not share. No git commit was made; proposed commit message: `research: compare V5 intended rating update with certified control`.

**tags:** ["ratings", "v5", "research", "replay", "forecast"]
