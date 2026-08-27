# Session: Phase 5 Protected Prospective Evidence Planning

## TL;DR

- **Worked On:** Designed the Phase 5 protected prospective evidence contract.
- **Outcome:** Saved a decision-complete Draft plan. No implementation, data
  operation, R2/Neon access, or live 2026 freeze occurred.
- **Plan Contract:**
  `docs/plans/2026-08-26/phase5-protected-prospective-evidence.md`
- **Approval / Status:** User authorized planning/documentation only on
  2026-08-26; contract remains `Draft` pending implementation approval.
- **Blockers:** None for plan review. Live implementation must close the
  run-local drives-ref and authentic-clock gaps before Week 1 can count.
- **Next:** Review and separately commit the Draft plan; after approval, open a
  fresh Terra task using the repository-local `implement-plan` skill.

## Context and Decisions

- Phase 5 is an operations/evidence phase, not a model-development phase.
  Candidate v1 and `shadow_operations_v1` remain byte-for-byte frozen.
- A separate prospective policy hash carries the one-hour hard lead gate,
  normal-coverage threshold, and six-slate count without changing the shadow
  design ID.
- Production V4 publish/freeze remains outside Phase 5 authority. Phase 5 reads
  only an explicit already-frozen V4 run and writes only Preview research
  artifacts.
- Canonical eligibility uses actual freeze completion time, not only a
  caller-supplied data cutoff. Target execution is T-2 hours; hard evidence
  eligibility is T-1 hour.
- Evidence accumulation continues unchanged for six eligible slates and emits
  descriptive metrics only. It cannot tune, promote, or stop candidate v1.

## Investigation Findings

- `prepare-week` invokes `build_team_game_dataset.py`, which materializes
  byplay, drives, reconciled team game, and source reconciliation, but only the
  team-game ref alias is exposed. Phase 5 requires one immutable run-local ref
  set for all four outputs.
- The Phase 4 freeze validates requested `as_of` but not actual completion time
  or parent `created_at`, so Phase 5 must prevent accidental backdating before
  protected writes begin.
- The current live slate is schedule-derived and does not prove exact equality
  to V4's frozen eligible-game keys.
- Pregame states are reconstructed but not persisted. Phase 5 needs component
  and team-state artifacts to support later stability/responsiveness review.
- Target-only current-season snapshot assembly is algebraically legitimate
  because Phase 2 combines a fixed offseason prior with cumulative measurement
  exposure rather than recursively carrying each within-season posterior; the
  implementation must prove equivalence in regression tests.
- Cancellation reasons are recorded, but current scoring must additionally
  validate the latest authoritative schedule status.

## Files Modified

- `docs/plans/2026-08-26/phase5-protected-prospective-evidence.md` — Draft
  implementation and six-slate operations contract.
- `session_logs/2026-08-26/06-phase5-protected-evidence-planning.md` — planning
  investigation and handoff.

## Validation

- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`
- [x] Worktree review confirms documentation-only changes.

## Amendments and Blockers

- None. The contract is intentionally Draft and does not authorize product
  code or prospective evidence operations.

## Handoff Notes

- **Resume at:** Review the Draft contract. If approved, persist the separate
  plan commit and start a fresh Terra implementation task.
- **Watch out for:** Do not run Week 1 preflight/freeze, modify the frozen
  shadow config, or access live R2/Neon as part of this planning session.

Copy-ready Terra handoff after approval:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-08-26/phase5-protected-prospective-evidence.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["ratings", "phase5", "prospective", "planning", "shadow"]
