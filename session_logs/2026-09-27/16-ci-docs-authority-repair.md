# Session: CI docs-authority repair after Week 5 line refresh

## TL;DR
- **Worked On:** CI failure on commit `25bb477` (Python tests job): one failure in `test_data_first_documentation_authority.py::test_current_guide_records_model_completion_and_live_release`.
- **Outcome:** Root cause was three stale pinned assertions, not a docs regression — the Week 5 complete-line refresh rewrote `docs/modeling/v5_status.md` (new live run `2026w5-5d436e58c072` "selected in production", "same-week rollback" chain, "separately authorized exact packet" release) while the test still pinned the prior release wording. Updated the three assertions to the live wording; focused file passes 17/17 locally.
- **Plan Contract:** N/A (fast path: localized test alignment with the already-authorized release record in `session_logs/2026-09-27/14-week5-line-refresh-candidate.md`).
- **Approval / Status:** No production writes; test-only change. Needs user commit + CI confirmation.
- **Blockers:** None.
- **Next:** Commit test + this log, watch CI, then proceed with the ratings-history replay contract (Draft, awaiting approval) and the Week 5 freeze gate.

## Context and Decisions
- Run `36355404207`: 1477 passed, 1 failed — only the docs-authority test. Lint/contracts and Web jobs succeeded.
- Same failure class as the 2026-09-27 session-log-12 repair (assertion tied to superseded release wording). Followed that precedent: align the test to the live release rather than editing docs to satisfy the test.
- Kept the guardrail's intent intact: the test still requires the guide to record model completion, the live Week 5 run selection, the exact-packet authorization, and the rollback chain — just against current wording.

## Work Completed
- `tests/test_data_first_documentation_authority.py` — replaced `"tested rollback"` with `"same-week rollback"`, the `d6366e59fd43` "published in production" pin with `` `2026w5-5d436e58c072` is selected in production ``, and `"week 5 production release packet was validated and authorized"` with `"separately authorized exact packet then published and selected"`. Updated the inline comment.

## Files Modified
- `tests/test_data_first_documentation_authority.py` — stale release-wording assertions aligned to the live refresh
- `session_logs/2026-09-27/16-ci-docs-authority-repair.md` — this record

## Validation
- [x] `uv run pytest tests/test_data_first_documentation_authority.py -q`: 17 passed
- [x] `git diff --check` clean
- [ ] Full CI on push (the ~7 min pytest job is the one to watch)

## Amendments and Blockers
None. Note for the future: this assertion pins the exact live run ID, so every same-week line refresh will trip it again the same way. Left as-is deliberately (exact-ID pin forces human review of the release wording); a robust-prefix relaxation would be a separate test-semantics decision.

## Handoff Notes
- **Resume at:** Commit the two files, confirm CI green (especially the Python tests job), then continue freeze/replay work.
- **Watch out for:** The queued CI run `36356871210` on `f98fb1d` will also fail on this test — the fix commit supersedes it.

**tags:** ["ci", "tests", "docs-authority", "v5", "week5"]
