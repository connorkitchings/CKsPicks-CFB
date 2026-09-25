# Session: V5 weekly operator planning

## TL;DR

- **Worked On:** Started the session workflow, reviewed V5 status and the completed replay/Preview rehearsal, and planned the next V5 product milestone.
- **Outcome:** Approved implementation contract at `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` for a manual resumable operator and exact production release safeguards.
- **Plan Contract:** `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` (Approved; implementation not started).
- **Approval / Status:** User chose workflow preparation and an operator CLI, then said “Proceed” after the proposed plan. Production activation remains a separate exact-artifact decision; Git operations remain user-controlled.
- **Blockers:** Week 4 finals have not stabilized. A new 07/08 refresh, 09 live forecast, and 05 `ready` verdict cannot be claimed yet.
- **Next:** Use a fresh Terra task with the exact approved contract path. Restore Vercel Deployment Protection from the prior Preview rehearsal. After stable Week 4 finals, certify new 07/08 parents and proceed to 09/05 for the next eligible slate.

## Context and Decisions

- V5 historical development is accepted; Weeks 0–3 replay `v5-replay-20260924-cb2252a` and Preview V4 rollback/V5 restoration are complete. V4 still serves production.
- The existing ops state machine has leases and resumable receipts, while 07/08/09/05 research commands already separate reviewed preflight from immutable apply and verification.
- The current `v5_release_policy` authorizes a model and earliest week but does not bind a specific forecast/readiness/prediction artifact. The next milestone prepares an exact one-slate authorization boundary without creating a production authorization.
- The user chose a manual CLI instead of a GitHub Actions or external scheduler. Automatic triggers are deferred.
- Storage configuration needed for investigation was present; no credentials were printed and no live data operation was performed.

## Work Completed

- Read the repository start-session and plan-session skills, current contracts, recent logs, V5 runbooks, ops/publisher code, migration 0013, and the existing scheduled capture workflow.
- Recorded the approved contract and linked it from the plans index. No implementation code or external state was changed.

## Files Modified

- `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` — approved execution contract.
- `docs/plans/index.md` — current contract link.
- `session_logs/2026-09-24/04-v5-weekly-operator-planning.md` — planning handoff.

## Validation

- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`

## Amendments and Blockers

None. Current live certification remains gated on stabilized Week 4 finals; this contract prepares the operator and release guard only.

## Handoff Notes

- **Resume at:** Implement the exact approved contract in a fresh Terra task.
- **Watch out for:** Do not treat retrospective replay or fixture checks as prospective evidence. Do not create a production release authorization or activate V5 under this contract.

**Suggested plan commit message:** `Document V5 weekly operator and exact release gates`

**Copy-ready implementation prompt:**

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["v5", "planning", "weekly-operations", "publication"]
