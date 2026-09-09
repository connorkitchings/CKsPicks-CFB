# Session: Simplify retrospective context metrics

## TL;DR

- **Worked On:** Removed redundant comparison-count text from the four
  retrospective-context metric boxes.
- **Outcome:** Each box now presents only the hit rate and W-L-P record.
- **Plan Contract:** N/A (approved, localized presentation change).
- **Approval / Status:** User explicitly requested the change on 2026-09-08.
- **Blockers:** None.
- **Next:** Commit and deploy through the normal web workflow.

## Work Completed

- Removed the unused comparison-count parameter from the historical context
  metric renderer.
- Preserved full-season, matching-week, Week 0 unavailable, and reconstructed
  historical-reference disclosure behavior.

## Files Modified

- `web/src/components/HistoricalModelContext.tsx` - Remove “x compared” from
  the four metric boxes.

## Validation

- [x] `npx nx run web:lint`
- [x] `npx nx run web:typecheck`
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** No active implementation work.
- **Watch out for:** Retain the explicit diagnostic/reconstructed-lines
  disclosure; only redundant metric copy was removed.

**tags:** ["web", "historical-context", "ui"]
