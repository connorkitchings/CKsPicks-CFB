# Session: Plan the 2026 V5 intended-update production repair

## TL;DR
- **Worked On:** Converted the reviewed V5 rating repair into a production implementation contract.
- **Outcome:** Draft plan for new 2026 ratings, replacement Weeks 0–4 predictions and scores, and a prospective next-slate forecast, with atomic selection and old-lineage rollback.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md`
- **Approval / Status:** User requested a plan and clarified that ratings, predictions, and scores all change; contract remains Draft pending approval of the exact plan. Production activation requires a later exact release decision on completed packets.
- **Blockers:** None for planning.
- **Next:** Review and approve the exact contract; implement in a fresh Terra task.

## Context and Decisions
- Use the full historical repair and refitted through-2025 bridge as a versioned V5 successor. Preserve 2025 terminal measurement-derived 2026 priors and accepted V5 rollback.
- Replace completed Weeks 0–4 public selections with labeled retrospective repaired runs and new run-specific scores. The original frozen runs and grades remain immutable audit records.
- The current singleton release policy, globally scoped rating periods, and one-week selection interface require coordinated changes before release.
- Build and rehearse the complete release in Preview, then seek an exact production decision on hashes and run IDs. No production data was changed in this session.

## Work Completed
- Read the repository protocol, plan-session skill, contract template, plan index, recent research and session context, and affected source interfaces.
- Wrote the Draft implementation contract linked above.

## Files Modified
- `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — execution contract.
- `session_logs/2026-09-29/01-v5-intended-update-production-plan.md` — planning log.

## Validation
- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`

## Amendments and Blockers
- None. The worktree already contains uncommitted 2026 research changes from the previous session; preserve them during implementation.

## Handoff Notes
- **Resume at:** Have the user approve the exact Draft contract, then open a fresh task with `.agent/skills/implement-plan/` and the contract path.
- **Watch out for:** First kickoff and production selection may have moved since the 2026-09-27 snapshot. Refresh these read-only facts before choosing a live slate.

**tags:** ["ratings", "v5", "production", "planning"]
