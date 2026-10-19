# Weekly close/open and promotion process review

- **Status:** Review requested by owner on 2026-10-19; investigation and implementation deferred at owner-requested session close.
- **Incident:** [Production session log](../../session_logs/2026-10-19/01-production-release-preflight.md).
- **Operational authority:** [Weekly runbook](../ops/weekly_runbook.md).

## Required boundaries

Preview-to-Production promotion must make zero CFBD or other provider requests. Reuse the accepted candidate and its immutable parents; a necessary schema/code rebuild must use retained certified inputs. Do not refresh lines just because a release is being promoted.

Normal week close/open must not re-query every historical week. Reuse certified history, scope football ingestion to the newly completed week and market ingestion to the authorized closing/upcoming scope. Historical refetches require an explicit repair/missing-input reason, exact affected games/weeks and an approved request budget. Do not silently alter historical forecasts, grades or lineage.

## Next-session investigation

Use plan-session to inspect `scripts/pipeline/build_season_revision.py`, `refresh_controller_silver`, the prepare-week step definitions, source-request inventories, resume/cache semantics, Silver parent composition and the season runner. Investigate from source, retained receipts and fixtures; do not make exploratory provider requests.

Explain exactly which CFBD requests the current weekly builder makes and why existing captures are not reused. Separate three operations: promote retained candidate; close/open a normal week incrementally; repair specifically identified history. Determine the smallest implementation preserving immutable checksums, exact reconciliation, point-in-time cutoffs, catalog registration and release verification. Reconcile Make targets and runbook so an operator cannot accidentally invoke full-history re-ingestion for a promotion or normal rollover.

Propose a decision-complete contract before code changes. Validation should prove zero provider calls for promotion, only expected new-week requests for rollover, explicit scope for repairs, reuse of certified historical hashes, stable completed-week numerical outputs, and correct restart behavior after interrupted work. Do not claim an incremental workflow exists until it is implemented and verified.

## October 19 facts

The unnecessary controller fetched schedule/plays/game statistics through part of Week 3 before cancellation; it did not complete all Weeks 0–7. Both the builder and child were stopped, and its expired operations receipt was closed as failed/cancelled through the state-store API. No partial-refetch football parent was activated. The final promotion preserves every certified nonmarket input reference and historical cutoff. The actual request/credit total was not audited and must not be guessed.
