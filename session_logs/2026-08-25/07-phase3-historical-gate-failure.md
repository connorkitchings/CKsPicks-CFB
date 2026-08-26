# Session: Phase 3 Historical Gate Failure

## TL;DR

- **Worked On:** Committed the completed-outcome regression fix and ran the
  authorized Preview Phase 3 materialization from its exact code identity.
- **Outcome:** The immutable historical evaluation has complete paired V4
  coverage but fails frozen uncertainty calibration (margin) and bias /
  standardized-mean (total) gates. No model, prediction, or candidate-manifest
  artifact was published.
- **Plan Contract:** [Phase 3 structured margin and total baseline](../../docs/plans/2026-08-25/phase3-structured-margin-total-baseline.md)
- **Approval / Status:** User explicitly authorized the commit and completion
  attempt on 2026-08-25; the contract remains `In Progress`.
- **Blockers:** The pre-registered historical gates failed. Phase 4 is blocked
  by contract; no retrospective tuning is authorized.
- **Next:** Create a fresh Sol contract for a new candidate identity if the
  user wants to pursue a recalibrated or otherwise revised structured baseline.

## Context and Decisions

- Commit `533507b99e5796e3cab2b557a2a4e101ce851028` filters only historical
  rows without both authoritative outcomes from expanding evaluation. It does
  not alter model equations, thresholds, inputs, or 2026 behavior.
- The fixed historical comparison set contains 2,997 completed games and
  5,994 target rows, all paired with the certified V4 ref.
- The candidate did not freeze: the outcome-only evaluation is immutable
  diagnostic evidence, not authorization to tune this baseline.

## Work Completed

- Committed the narrow outcome-completeness regression fix and its test.
- Ran Preview materialization from the committed code/configuration with the
  certified Phase 1, Phase 2, foundation, and V4 parents.
- Recorded the failed report at
  `artifacts/research/rating-successor/predictions/a505253d3e1d466fb70eeac4a1470c0ec9b3b58eb9916718194e19899f207119/runs/2026-08-26T0122Z-phase3-freeze/evaluation.json`
  (SHA-256 `0c9029f5701572b73d669499855e441ce9874fe343a5f171107ef1acb503ba60`).
- Confirmed no successful Phase 3 model, prediction, or candidate-manifest
  artifact exists under that run prefix.
- Updated the Phase 3 contract and roadmap to reflect the actual state.

## Validation

- [x] `uv run pytest tests/ratings -q` — 86 passed.
- [x] `uv run pytest -q` — 500 passed, 2 skipped.
- [x] Scoped Ruff format/check, contracts validation/sync, strict MkDocs, and
  `git diff --check` before the committed materialization attempt.
- [x] Preview evaluation has 5,994 / 5,994 candidate-to-V4 paired rows.
- [x] Preview artifact isolation: diagnostic evaluation only.

## Amendments and Blockers

- **Amendment:** Exclude the two unscorable historical rows; this restores the
  certified V4 comparison population without changing the baseline.
- **Blocker:** Margin uncertainty and total calibration gates fail. Do not
  weaken gates or revise this candidate after reading the report.

## Handoff Notes

- **Resume at:** A new Phase 3 planning contract for a separately identified
  challenger, if authorized.
- **Watch out for:** V4 remains production champion; Phase 4, markets, Neon,
  publication, and 2026 protected evidence remain out of scope.

**tags:** ["ratings", "phase3", "evaluation", "gate-failure", "preview"]
