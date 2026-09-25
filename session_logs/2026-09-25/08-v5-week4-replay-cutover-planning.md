# Session: Plan complete V5 Week 4 replay site cutover

## TL;DR

- **Worked On:** Investigated the request for a V5-only site covering all of Week 4 and scored retrospective Weeks 1–3.
- **Outcome:** Documented a Draft, planning-only contract for complete Week 4 V5 replay coverage and a separate exact production replay release lane.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md`.
- **Approval / Status:** User requested planning and documentation; Draft awaits review of the material release-policy change. No implementation or production activation is authorized by this session.
- **Blockers:** First Week 4 kickoff has passed, so a full prospective Week 4 V5 run is impossible. Current production publisher and selector reject V5 replay. Week 4 scores await certified finals.
- **Next:** Review the Draft's retrospective Week 4 evidence label and separate replay authorization contract. If approved, use a fresh implementation task; present exact release packets for separate production decisions.

## Context and Decisions

- The user requires V5 Weeks 1–3 to be published and scored as retrospective site history before calling the 2026 site V5-only. The requested Week 4 view covers all 58 games, including the game whose kickoff preceded this planning session.
- Production's V4 Week 4 run `2026w4-da5d98761831` remains frozen with 58 predictions. The 2026-09-25 15:11 UTC read-only checkpoint recorded one kickoff and zero Week 4 finals. A pre-kickoff data cutoff can prevent outcome leakage but cannot establish a pre-kickoff forecast receipt after kickoff.
- The Draft selects a conservative full-slate `replay` classification with actual creation/publication timestamps. It proposes exact, separate replay authorization; it preserves the approved Week 5 live gate and V4 rollback.

## Work Completed

- Read the planning skill, relevant product/replay/live contracts, current publisher and selector guards, replay builder, and V5 performance query.
- Created the Draft contract and linked it in the plan index. No code, schema, data, deployment, or production state changed.
- Critiqued the proposed execution phases against the current replay adapter, scorer, release guard, selection path, and performance query. Tightened the Draft's open decisions, exact quote provenance and V5 lean recomputation, replay/live stats separation, clean-code and migration checkpoints, complete-finals scoring gate, and live-path priority. Kept the contract Draft; the proposed session text alone does not record approval of those decisions.

## Files Modified

- `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` — new Draft contract.
- `docs/plans/index.md` — Draft reference and relationship to the existing live plan.
- `session_logs/2026-09-25/08-v5-week4-replay-cutover-planning.md` — planning record.

## Validation

- [x] `.venv/bin/mkdocs build --strict --quiet` — passed.
- [x] `git diff --check` — passed.

## Amendments and Blockers

This Draft would change the production replay release policy. The first kickoff and current production guards are material conflicts with a prospective Week 4 cutover. The Draft resolves them only by proposing a separate retrospective release lane; implementation must wait for review.

## Handoff Notes

- **Resume at:** Review and approve or revise the Draft evidence classification and exact replay authorization. Preserve the previously approved post-Week-4 live plan.
- **Watch out for:** Do not label the Week 4 replay live, backdate the artifact, or treat missing game results as proof of a pre-kickoff forecast.

**Suggested commit message:** `Plan complete V5 Week 4 replay site cutover`

**tags:** ["v5", "planning", "week4", "replay", "site-cutover"]
