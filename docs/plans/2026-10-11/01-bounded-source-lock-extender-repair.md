# Bounded source-lock extender repair

- **Status:** In Progress
- **Created:** 2026-10-11
- **Planner:** Sol
- **Approval source:** User explicitly approved the proposed bounded repair and requested same-chat persistence and implementation on this exact path on 2026-10-11.
- **Planning log:** `session_logs/2026-10-11/03-bounded-extender-planning.md`
- **Implementation log:** `session_logs/2026-10-11/04-bounded-extender-implementation.md`
- **Commit policy:** Separate plan commit preferred; user controls Git operations. Same-chat implementation is explicitly authorized.

## Goal and acceptance

Enable an explicit append mode to add the next completed week's full schedule to an already-extended lock. Demonstrate 271 + 58 = 329 games using retained test fixtures only. Preserve existing historical rows, cutoffs and provenance exactly; retain legacy non-append behavior. Refuse historical drift, incomplete/duplicate identities, incomplete finals, count mismatch, skipped weeks, premature cutoffs and existing output paths in append mode.

## Baseline and constraints

The [closeout preflight](week7-transition-review.md) reproduced the current helper's rejection of the already-extended Week 5 lock; it also established that the lock lists no Week 6 identities. Current `dev` is `d22efb1a` with pre-existing dirty documentation and investigation work, all preserved. Scope is the pure extender, its existing CLI, focused tests and relevant contract/docs/log updates. No schema/model change, historical rewrite, EPA repair, downstream CLI redesign, database/R2 write, operational Week 6 lock, Week 7 opening or Production activation.

Retained source observations are fixtures, not certified outcomes. The [parent closeout](01-week6-closeout-and-transition-review.md) retains the empirical 24-hour stability gate (current baseline recheck Monday October 12 after 10:08 AM New York), clean committed apply-code requirement and exact user-run applies. Passing repair tests does not satisfy those operational gates.

## Ordered changes

1. Add optional `append_week` and `expected_games` helper arguments and `--append-week`/`--expected-games` CLI flags. Append mode requires both, pinned schedule/outcomes refs and the immediately following week. Keep legacy behavior when append mode is absent.
2. In append mode verify contiguous historical cutoffs, unique historical/source identities, complete historical rows and the prior extension row checksum when present. Compare historical week/team/kickoff/score identities with the supplied source; reject drift and historical kickoff waivers. Preserve existing rows/order and old cutoff values exactly.
3. Select the full next-week schedule, require exactly the requested positive game count and complete valid finals, preserve availability checks, and append rows deterministically. Add only the next cutoff and updated completed count. Preserve prior metadata under `extends.previous_extension`; bind base raw checksum, input refs and resulting row checksum.
4. Refuse an existing output file before append-mode cloud reads, and use exclusive output creation. Keep legacy output behavior intact.
5. Test retained 271-game base plus 58 observed games entirely in memory, legacy behavior, chained append/provenance, source ordering independence, rejection boundaries and downstream successor/comparison compatibility. Update parent blocker disposition to tooling repaired, with operational certification still pending.

## Validation

Run `uv run pytest tests/test_lock_extension.py`, then focused successor-lock and published-comparison compatibility tests. Test missing/duplicate games, incomplete/conflicting/nonfinite scores, historical drift, skipped weeks, count mismatches, cutoff boundaries, input immutability and output overwrite refusal. Run scoped Ruff lint/format checks, documentation-authority tests, `uv run mkdocs build --quiet` and `git diff --check`. Do not generate any operational lock or use network/database writes.

## Handoff/amendments

User explicitly authorizes implementation in this chat after persistence. Mark In Progress before code edits and Implemented only after repair acceptance passes; parent closeout remains In Progress. Mechanical adjustments preserving scope/acceptance may proceed with a recorded explanation; material downstream or operating changes return for a new decision.
