# Session: V4 to V5 site transition planning

## TL;DR

- **Worked On:** Reviewed the V4 publishing/site path and V5 live adapter, then drafted a site transition contract.
- **Outcome:** A decision-ready plan covers exact live certification, production authorization, public week selection, model-specific records, Preview rehearsal, V4 rollback, and separate production approval. No implementation or operational apply occurred.
- **Plan Contract:** `docs/plans/2026-09-22/05-v4-to-v5-site-transition.md` — Draft.
- **Approval / Status:** Planning/documentation only as requested; implementation and production activation are not authorized by this session.
- **Commit policy:** Separate plan commit; the user explicitly requested the commit in this session. Include only this plan and planning log.
- **Blockers:** Stabilized Week 4 finals, refreshed verified 07/08, a certified 09 forecast, verified `ready` 05, and a real Preview rehearsal are still outstanding. Public record policy awaits the user's preference.
- **Next:** Review the draft and record-policy choice. After approval, implement the site safety and selection work; perform live certification and Preview rehearsal when the data gate passes.

## Context and Decisions

- V5 historical development is accepted, while V4 remains the public model. This review used repository code and recent logs; it did not query R2, Neon, Vercel, or live results. Documentation-only work did not require data storage credentials.
- The V5 adapter can produce ordinary immutable weekly runs, but the final `publish_to_db.py` activation boundary needs a separate release check because it can publish an artifact directly.
- Historical site pages select the newest frozen/scored run, close-week selects the newest frozen run, and season stats select the newest scored run per week. These implicit choices become unsafe when V4 and V5 coexist for a cutover week; the plan chooses an explicit per-week public selection.
- The site currently shows a model-agnostic 2026 record and hard-coded V4 2025 retrospective context. The draft proposes a V5-only record after cutover and separately labeled V4 history, pending user confirmation.
- A production candidate artifact should be prepared without Neon activation so the exact artifact SHA can be included in the release packet that the user reviews.
- The six-slate count remains prospective monitoring, not a site launch prerequisite. No 2026 outcome may refit this V5 identity.

## Work Completed

- Read the repository-local start-session and plan-session skills, quickstart/context, current V5 guide, contracts 06–09, prior cutover plan, operating runbooks, and recent session logs.
- Inspected the V5 serving adapter, production publisher, active/frozen run resolution, scorer aggregates, site queries, health route, and publication policy.
- Created the Draft implementation contract with scope, ordered tasks, acceptance criteria, validation, release gates, and rollback design.

## Files Modified

- `docs/plans/2026-09-22/05-v4-to-v5-site-transition.md` — draft contract.
- `session_logs/2026-09-22/13-v4-to-v5-site-transition-planning.md` — planning record.

## Validation

- [x] `git diff --check` — passed.
- [x] `.venv/bin/mkdocs build --strict --quiet` — passed.
- [x] `uv run mkdocs build --quiet` — passed during end-session.

## Amendments and Blockers

- The public V5 record treatment is proposed and remains open to the user's answer. No live source status was asserted from this documentation-only inspection.
- The existing V5 shadow runbook still contains a stale six-slate prelaunch sentence near its end; the plan includes correcting it during implementation.

## Handoff Notes

- **Resume at:** Resolve the record display policy, review/approve the draft, then implement the selection and release safety path before operational cutover.
- **Watch out for:** Do not use newest-run ordering to decide public display or scoring when both V4 and V5 exist. Do not mutate production in a planning session.
- **Proposed commit:** `docs(v5): plan V4 to V5 site transition`.

After the user approves this exact plan, the fresh implementation task can use:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-22/05-v4-to-v5-site-transition.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["v5", "v4", "site", "release", "planning"]
