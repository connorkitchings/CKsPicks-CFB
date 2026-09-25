# Session: V5 live Preview execution planning

## TL;DR

- **Worked On:** Documented the next V5 operational sequence after the implemented weekly operator and release boundary.
- **Outcome:** Created a Draft plan for Week 4 finals/V4 close, refreshed 07/08 parents, Contract 09/05 live certification, Preview serving/rollback, and a reviewable exact packet. No execution occurred.
- **Plan Contract:** `docs/plans/2026-09-25/01-v5-week4-finals-to-live-preview.md` (Draft; execution approval pending).
- **Approval / Status:** User requested planning and documentation only. Production V5 activation and one-slate authorization remain separate decisions; Git operations remain user-controlled.
- **Blockers:** Week 4 finals and their 24-hour stabilization gate remain open. At the prior read-only check, no Week 4 finals were recorded.
- **Next:** Review and approve the draft; after finals stabilize, execute its gated steps in a separate implementation session.

## Context and Decisions

- Latest completed implementation is the manual V5 operator and exact production release boundary (`09c30cd`). V4 remains public; production 0014 has zero authorization rows.
- Existing 07/08/09 and site-cutover contracts already decide model lineage, timing, verifiers, and release policy. The new plan sequences their outstanding operations without changing them.
- Week 5 is the first intended live target if it retains valid pre-kickoff time. A missed timing gate must be recorded truthfully and moved to the next eligible slate under new identities.
- Readiness needs an exact same-week V4 comparison artifact, and rollback needs a same-week Preview V4 serving run. The plan prepares them through the existing V4 path if absent.
- The plan stops at a validated exact release packet and Preview evidence. It does not authorize an admin authorization insert or production V5 publication/selection.

## Work Completed

- Reviewed the current contracts, V5 weekly operator and shadow runbooks, product transformation status, and latest freeze/implementation/gate-check logs.
- Added the Draft execution plan and linked it from the implementation-contract index.
- Preserved the pre-existing untracked Week 4 gate-check session log and made no code, R2, Preview, or production changes.

## Files Modified

- `docs/plans/2026-09-25/01-v5-week4-finals-to-live-preview.md` — gated operational plan.
- `docs/plans/index.md` — Draft plan link and authority note.
- `session_logs/2026-09-25/05-v5-live-preview-execution-planning.md` — planning handoff.

## Validation

- [x] `.venv/bin/mkdocs build --strict --quiet` — passed.
- [x] `git diff --check` — passed.

## Amendments and Blockers

None. This plan adds an execution sequence and is Draft; it does not amend the accepted model or release contracts. The finals gate prevents current operational 07/08/09/05 apply.

## Handoff Notes

- **Resume at:** Review the Draft plan, then obtain execution authorization. Recheck final outcomes and timing before any operator preflight/apply.
- **Watch out for:** Use new immutable IDs and independently verified refreshed parents. Do not convert replay or fixture evidence into a live claim. Keep V4 public until a separate exact-packet activation decision.

**Suggested commit message:** `Plan V5 live Preview certification after Week 4 finals`

**tags:** ["v5", "planning", "forecast", "preview"]
