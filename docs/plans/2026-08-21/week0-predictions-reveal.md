# Week 0 Predictions Reveal and Manual Snapshot Operations

- **Status:** Implemented
- **Created:** 2026-08-21
- **Planner:** Sol
- **Approval source:** User explicitly approved and requested implementation in
  the current task on 2026-08-21.
- **Implementation log:**
  `session_logs/2026-08-21/02-week0-predictions-reveal.md`
- **Commit policy:** Commit with implementation; git operations remain
  user-controlled.

## Goal

Expose reviewed Week 0 model predictions publicly while preserving every
manually captured model/market snapshot and retaining final-freeze authority
for scoring.

## Implementation

1. Validate active run `2026w0-55de0317120d`: exact eight-game slate, 8/8/8
   coverage, finite model/market/edge values and directional leans, and zero
   high-confidence rows. Record its immutable artifact checksum, market
   capture, and cutoff as the initial public timing observation.
2. Set Vercel production `CFB_PUBLICATION_MODE=predictions`, retain the
   existing 2026/Week 0 publication scope, and redeploy the linked web app.
3. Smoke-test the production homepage and health endpoint. Require the active
   published run, predictions mode, leans with numeric edges, accuracy panel,
   display-only framing, and 8/8/8 health coverage.
4. Update the runbook and active launch contract: public view is
   latest-snapshot-only; manual publishes are immutable timing observations;
   final review/freeze remains mandatory and stops further publishing.

## Interfaces and Constraints

- Public environment: `CFB_PUBLICATION_MODE=predictions` is the only opt-in
  model-display value; all other values remain market-only.
- No database migration, capture scheduler, public history route, or timeline
  UI is in scope.
- Every manual publish uses explicit V4 configuration and an `AS_OF` roughly
  five minutes ahead. The newest run becomes public; earlier R2 artifacts are
  never overwritten.

## Validation

- [x] Active run review: published, 8/8/8, eight finite prediction rows,
  zero high-confidence rows, immutable checksum recorded.
- [x] Production deployment Ready and primary-domain alias applied.
- [x] `/api/health`: `mode=predictions`, active reviewed run, 8/8/8 coverage.
- [x] Homepage response contains prediction cards, numeric edges, accuracy
  panel, and display-only framing.
- [x] Existing publication-boundary test suite remains green from the current
  implementation session.

## Definition of Done

- [x] Reviewed Week 0 predictions are public.
- [x] First public timing snapshot is recorded.
- [x] Manual snapshot and final-freeze policy is documented.
- [x] Production health and rendered-response smoke tests pass.

## Amendments

None.
