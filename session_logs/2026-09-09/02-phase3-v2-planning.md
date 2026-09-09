# Session: Phase 3 v2 detailed execution contract

## TL;DR

- **Worked On:** Expanded the approved Phase 3 v2 plan into an execution-ready
  contract after Repair v2 Preview verification.
- **Outcome:** The contract now fixes complete-population behavior, output
  schemas, the frozen tournament, and the user-selected six-hour reconstructed
  historical availability buffer.
- **Plan Contract:** `docs/plans/2026-09-08/phase3-measurement-and-core-selection-v2.md`
- **Approval / Status:** Approved by user on 2026-09-09.
- **Blockers:** None for implementation planning. Preview execution requires a
  later user-created clean committed checkpoint.
- **Next:** Start a fresh implementation task using `implement-plan` and the
  approved contract.

## Context and Decisions

- Repair v2's verified Preview manifest is the sole modeling parent. Phase 3 v1
  is diagnostic-only and cannot contribute features, training, selection, or
  ratings.
- The repaired population is 8,936 scheduled / 8,935 eligible / 8,903 usable;
  all 32 completed games missing measurements remain in the forecast population.
- Historical source admission uses prior canonical week plus a six-hour buffer
  between source kickoff and the target week's earliest eligible kickoff. All
  such data is explicitly `historically_reconstructed`.
- Candidate registry, thresholds, adjustment iterations, and model scaffold are
  sealed; no result-driven expansion is authorized.
- Phase 3 v2 is Preview-only and hands off to a separate Phase 4A v2 task. It
  does not alter V4, production, Neon, web serving, or live predictions.

## Work Completed

- Replaced the terse Phase 3 v2 contract with a decision-complete implementation
  contract.
- Added the availability policy as Amendment 1 rather than silently changing the
  earlier approved plan.
- Defined expected fixture-scale interfaces and counts, including 6,318 eligible
  validation games and 202,176 prediction rows.

## Files Modified

- `docs/plans/2026-09-08/phase3-measurement-and-core-selection-v2.md` - Expanded
  approved Phase 3 v2 execution contract.
- `session_logs/2026-09-09/02-phase3-v2-planning.md` - This planning handoff.

## Validation

- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`

## Amendments and Blockers

- **Amendment:** Historical availability is now concretely defined as the
  six-hour reconstructed buffer selected by the user.
- **Blockers:** None for planning. Do not apply Preview artifacts until the
  implementation task meets its clean-checkpoint condition.

## Handoff Notes

- **Resume at:** Open a fresh implementation task with the copy-ready prompt
  below.
- **Watch out for:** Preserve user-owned `.opencode/`; never create `./data/`;
  2020 remains forbidden; do not modify Phase 3 v1 or production state.

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-08/phase3-measurement-and-core-selection-v2.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["planning", "data-first", "phase3", "research", "lineage"]
