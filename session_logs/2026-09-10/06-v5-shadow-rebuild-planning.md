# Session: v5 Shadow Rebuild Planning (Sol)

## TL;DR
- **Worked On:** Planning pass for item 3 — the 2026 feature-mismatch rebuild.
- **Outcome:** New Draft contract `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Preview-only shadow diagnostic, Option A); 2026-09-09 Draft retained as root-cause record, superseded as executable plan. Awaiting user approval before any Terra implementation.
- **Plan Contract:** `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Draft)
- **Approval / Status:** Pending user review.
- **Blockers:** None for planning. Implementation blocked until approval.
- **Next:** User approves (or amends) the contract; then a fresh Terra task implements it.

## Context and Decisions
- Investigation verified the mismatch claim against prod `input_dataset_refs`: all 2026 runs bind v4 matchups (W0 `74ffdbbf`, W1 `30ac8b5d`, W2 `9b7bc478`), never v5.
- New findings that reshaped the plan: (1) W1/W2 core parents (`6d6f4da2`, `bda6032a`) are absent from R2 — exact v4 reproduction requires a builder rerun + parity gate, not direct ref reuse; (2) Week 2 is now frozen, so any rebuild is diagnostic-only until a separate production contract exists; (3) the 2026-09-09 Draft Step 5 is not executable (no `superseded` state; hand-edited run tables bypass ops).
- Selected Option A (Preview-only shadow, no serving writes) over production swap; Option B explicitly deferred to a future contract.
- Preserved `M docs/ops/production_runbook.md` and `?? .opencode/` untouched.

## Work Completed
- Readonly verification: prod runs/refs, R2 preseason `8c47f6d5` (strict, eligible, pre-kickoff as_of), v5 benchmark `fe55e758`, assembler + generator CLI flags, R2 core/baseline version census, manifest parent/as_of audit per week.
- Wrote the Draft contract with pinned cutoffs, tasks, gates, stop rules, kill criterion, and definition of done.
- Updated `docs/plans/index.md` (new row + supersession note on the old Draft).
- This planning log.

## Files Modified
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` - new Draft contract
- `docs/plans/index.md` - new entry + supersession note
- `session_logs/2026-09-10/06-v5-shadow-rebuild-planning.md` - this log

## Validation
- [x] `git diff --check` (clean)
- [x] `uv run mkdocs build --quiet` (passed)
- [ ] User approval of the contract (pending)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** User reviews the Draft contract; on approval, run the copy-ready Terra prompt below in a fresh task.
- **Watch out for:** Do not execute the contract in this session; Terra must stop per stop rules on any parity/cutoff failure.

Copy-ready Terra prompt:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["planning", "v5-shadow", "diagnostic", "2026-season", "sol"]
