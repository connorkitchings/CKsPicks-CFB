# Session: Plan the model performance dashboard and scatterplot repro

## TL;DR

- **Worked On:** Planning the `/model` market-comparison dashboard and a mobile scatterplot touch repro.
- **Outcome:** Contract written and approved; implementation delegated.
- **Plan Contract:** [`docs/plans/2026-11-08/model-performance-dashboard.md`](../../docs/plans/2026-11-08/model-performance-dashboard.md)
- **Approval / Status:** Owner approved the plan; contract Status `Approved`.
- **Blockers:** None. Open question: which chart showed the scatterplot failure.
- **Next:** Implement the contract, then validate.

**tags:** ["planning", "web", "model-page"]

## Context and Decisions

- Compare to the retained pre-kickoff line only; no closing-line comparison.
- Big-miss threshold 28 points; ties excluded from the "closer" denominator.

## Work Completed

- Created worktree off `origin/dev` and saved the contract.

## Files Modified

- `docs/plans/2026-11-08/model-performance-dashboard.md` — new contract
- `session_logs/2026-11-08/01-model-performance-dashboard-plan.md` — this log

## Validation

- [ ] `git diff --check`

## Amendments and Blockers

- None

## Handoff Notes

- **Resume at:** Contract implementation
- **Watch out for:** Spread sign (`-canonicalSpread`), banned words on `/model`, mobile KPI position.
