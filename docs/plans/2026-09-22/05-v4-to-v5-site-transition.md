# V4 to V5 Site Transition

- **Status:** Draft
- **Created:** 2026-09-22
- **Planner:** Codex (plan-session)
- **Approval source:** Pending user review; this planning request does not authorize implementation or activation.
- **Implementation log:** `session_logs/2026-09-22/NN-v4-to-v5-site-transition-implementation.md`
- **Commit policy:** Separate plan commit recommended because this spans a database migration, site behavior, and production release. User controls Git operations unless explicitly delegated.

## Goal

Replace V4 with the accepted V5 model on the public site for the first eligible future slate while preserving earlier V4 weeks, a pre-kickoff V4 fallback for the cutover slate, truthful model-specific records, and an auditable rollback. The replacement is complete when a current V5 forecast has been independently verified, the exact serving path and rollback have passed on Preview, the user has approved the specific production release, and the production site shows the selected V5 run with correct coverage, model label, lines, and health. Six prospective slates are ongoing monitoring, not a launch gate.

## Current State and Readiness Inventory

| Area | What exists | What remains |
| --- | --- | --- |
| Model | V5 historical development and through-2025 final fit are accepted; no 2026 outcome refit is allowed. | No claim of V5 superiority over V4; preserve that limitation in release notes. |
| Live data | Contract 07 measurements and Contract 08 rating replay are verified through Week 3. | Stabilized Week 4 finals, new immutable 07/08 manifests, and independent verifier receipts. If the Week 5 window is missed, target the next eligible slate. |
| Forecast | Contract 09 outcome-free live runner, independent verifier, and idempotent repeat are code ready. | Exact current forecast manifest and `ready` Contract 05 assessment for the chosen slate. |
| Serving | `v5_weekly_serving_v1` converts a pinned verified forecast to the existing prediction-run format; V4 config remains available. Synthetic tests passed. | Real Preview Neon publication, site inspection, dual-model freeze/score and rollback rehearsal. Preview config intentionally has null forecast refs and production authorization false. |
| Site | Header derives its name from the selected run; run-aware prediction rows already exist. | Historical weeks currently pick the newest frozen/scored run; close-week picks the newest frozen run; the season record picks the newest scored run per week. Those implicit choices can diverge after a dual-model cutover or rollback. The 2025 context panel is hard-coded to V4. |
| Production | V4 is active. Publication is gated by `CFB_PUBLICATION_MODE`, and run activation is transactional. | No V5 release decision or production rehearsal evidence. The V5 generation gate is not sufficient by itself: `publish_to_db.py` can publish an artifact directly, so the final activation boundary must verify authorization and lineage too. |

This inventory is based on repository code and the 2026-09-22 implementation logs. This documentation-only session did not query R2, Neon, Vercel, current game finals, or production configuration; those facts must be checked at execution time.

## Proposed Approach

### Release meaning

Use one explicitly selected public run for each 2026 week. V4 stays selected for weeks before the cutover; V5 starts with the chosen future week. The active-week pointer and each historical-week selection must agree. A rollback selects a previously validated V4 run for that same week without changing immutable predictions. Keep the research forecast manifest's `production_activation_authorized: false`; a separate, reviewed **serving release record** authorizes only a named forecast SHA, prediction-run SHA, season/week, and environment. No forecast fitting or selection changes occur at release.

### Public record policy (proposed; user preference pending)

Show a V5-only season record beginning with its first selected and scored week. Earlier V4 results remain accessible under their original V4 weeks and may be shown in a separately labeled V4 summary. Never call a blended V4/V5 total a V5 record. Show the existing V4-only 2025 retrospective context only on V4 pages; on V5 pages hide it until an honestly labeled V5 historical context is designed. Show the selected model name on each week, including archived weeks. Market-only mode remains unchanged.

### Selection design

Add an append-only migration for a small public `site_week_selections` table keyed by `(season, week)` with a `prediction_runs` foreign key, selection time, and reason; keep an append-only selection history for audit. Publication or rollback changes that row and `current_week.active_run_id` in one Neon transaction when it targets the current week. For older weeks, change only that week's selection. Require exact season/week match and a fully validated run; never infer a rollback target from creation order. Populate existing 2026 V4 week selections from reviewed run IDs before enabling the new site query. Until every public 2026 week is mapped, keep the current V4 site path; after enabling, missing or ambiguous selections fail closed to market-only display for that week. Keep 2025 legacy behavior unless separately migrated.

## Scope

### Included

- Release authorization at the final production publication boundary; exact manifest/config/run identity checks and fail-closed direct-artifact behavior.
- Explicit per-week public selection, safe reselection command, close-week and aggregate alignment, and V4 fallback.
- Site model labeling, model-specific record, V4 retrospective-context behavior, health visibility, and ISR verification.
- Preview migration, publication, freeze/score, site, and rollback rehearsal; then a separate, explicit production release decision and controlled cutover checklist.
- Runbook and status updates that distinguish development completion, current forecast certification, site release, and ongoing Contract 06 monitoring.

### Excluded

- Any 2026-based V5 refit or re-selection; a claim that V5 beats V4; betting or staking policy changes.
- Retrospective V5 forecasts for already played slates, fabricated prospective evidence, or six-slate collection as a prerequisite.
- Production publication, Vercel promotion, database mutation, or public activation during this planning session. Future production activation requires a decision tied to exact release artifacts.

## Affected Components and Contracts

- Research gates: Contracts [07](../2026-09-18/07-v5-2026-repair-and-measurement-extension.md), [08](../2026-09-18/08-v5-2026-rating-state-replay.md), [09](../2026-09-18/09-v5-2026-forecast-and-readiness.md), [05 archive](../../archive/v5-contracts/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md), and [06](../2026-09-13/06-v5-prospective-evidence-and-recommendation.md).
- Existing cutover tracker: [plan 04](04-v5-authority-simplification-and-site-cutover.md); this plan specifies its remaining site, selection, release, and rollback work. Do not mark plan 04 Implemented until its real Preview rehearsal and activation decision are recorded.
- Pipeline: `scripts/pipeline/generate_v5_weekly_bets.py`, `scripts/pipeline/preflight.py`, `scripts/pipeline/publish_to_db.py`, `scripts/pipeline/freeze_week.py`, `scripts/pipeline/score_to_db.py`, `src/cks_picks_cfb/ops/__main__.py`, `conf/weekly_bets/v5_preview_2026.yaml`, and the V4 config.
- DB contracts: append-only `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`, and a new canonical `contracts/migrations/0013_*.sql` revision (0012 is the current latest migration). Keep any documented web migration mirror in sync if the repository validator requires it.
- Site: `web/src/lib/queries.ts`, `web/src/app/page.tsx`, `web/src/app/api/health/route.ts`, `web/src/components/RecordBanner.tsx`, `web/src/components/HistoricalModelContext.tsx`, and focused tests/fixtures.
- Operating docs: `docs/ops/production_runbook.md`, `docs/ops/weekly_pipeline.md`, `docs/ops/v5_shadow_runbook.md`, `docs/modeling/v5_status.md`, and `docs/plans/index.md`. Remove the stale six-slate prelaunch instruction near the end of the shadow runbook.

## Implementation Tasks

### Task 1 — Make the public run choice durable

**Changes:** Add the selected-run table, audit trail, canonical migration, and read-only web-role grant. Implement reviewed backfill for already public 2026 V4 weeks, a transactional publish selection, and a `select-week-run` rollback operation with exact run ID, season/week, reason, and environment. Validate the candidate run's state, coverage, artifact SHA, and model identity before selection. Reject preview/partial runs in production. Log the previous and new run IDs. Preserve the existing V4 path until the backfill and site query are ready.

**Acceptance:** One selected run per 2026 week; current and historical views agree; rollback does not alter prediction rows or R2 artifacts; a missing selected run cannot silently fall through to a different model. Both V4 and V5 runs may coexist for a week without an implicit newest-run winner.

**Validation:** Migration and contract sync; Preview transactional publish/reselect tests; negative tests for wrong week, wrong environment, missing artifact, stale/partial run, and duplicate selection; `make contracts-check`.

### Task 2 — Close the production authorization bypass

**Changes:** Keep the forecast research manifest immutable and authorization false. Split production V5 artifact preparation from Neon activation so an exact immutable candidate artifact can be built and reviewed without a database write. Introduce a separately reviewed serving release record binding the verified Contract 09 manifest URI/SHA, 05 `ready` receipt, season/week, prepared V5 prediction artifact SHA, serving config SHA, and target environment. The production `publish_to_db.py` path must check that record and independently revalidate source and output identity before a DB write or active-pointer change, including direct `--from-artifact` calls; prohibit V5 CSV/local/legacy artifact bypasses. Preview may use a rehearsal release record that has no production authority. Ensure the selected run's `system_name`/`model_id` come from the verified manifest and match the config, not an unbound CLI label. V4 publication remains unchanged.

**Acceptance:** Without a matching explicit release record, every V5 production activation path fails before any Neon write. A modified config, forecast, prediction CSV, schedule, cutoff, or model label also fails. The release record names one slate and cannot authorize later weeks. The existing `CFB_PUBLICATION_MODE` remains a site visibility gate, not an authorization substitute.

**Validation:** Focused generation, preflight, publisher, and ops tests including direct-artifact bypass attempts; immutable digest tampering and environment tests.

### Task 3 — Align display, scoring, and records

**Changes:** Make `getRunForWeek` and week navigation use the reviewed selection for 2026; use its model ID for the page label. Change close-week's frozen-run resolver to the selected run, with a state check. Recompute any `system_stats` aggregate from selected scored runs, not newest scored runs. Compute the displayed V5 record only from selected V5 runs; preserve a distinctly labeled V4 record if shown. Suppress the V4-only 2025 context on V5 weeks. Expose selected run ID/model ID and selection consistency in `/api/health` without publishing research-only metadata. Preserve market-only mode and older V4 pages.

**Acceptance:** A Preview week with both frozen models shows and scores the selected one; a rollback switches the visible week and subsequent score/record source to V4. Corrected outcomes can update grades without changing the selected run. Earlier V4 weeks keep V4 labels and records; no mixed result is presented as V5.

**Validation:** Site query/component tests for V4 week, V5 week, rollback, missing selection, corrected score, and market-only mode; close-week/`system_stats` regressions; web lint/typecheck/build and contract sync.

### Task 4 — Certify the first real slate on Preview

**Entry gate:** Week 4 finals have stabilized. Refresh and independently verify 07 measurements and 08 rating replay under new immutable IDs, then run 09 preflight/apply/independent verify/idempotent repeat. Re-verify Contract 05 `ready` for the exact slate. If any dependency is blocked, record the missing parent and move the cutover target to the next eligible slate; do not backdate.

**Changes:** Pin the exact V5 forecast URI/SHA in a reviewed Preview config. Run standard Preview preflight and publication against Preview R2/Neon and a Preview Vercel deployment. Before the first kickoff, prepare and freeze a valid V4 run for the same slate as the rollback and grading fallback; publish and freeze V5 before kickoff as well. Inspect full FBS-vs-FBS coverage, two home-margin and market-sign examples, source cutoffs, model labels, health, record/context rendering, market-only behavior, and signed ISR. Re-select V4 via the new operation, verify site/health/score target, then re-select V5 if the rehearsal passes. Record run IDs, SHA-256 digests, timestamps, screenshots or request outputs, and measured rollback time.

**Acceptance:** Real Preview publication and rollback work using exact refreshed parents; no production or public mutation. Both fallback and V5 were frozen before kickoff. The site shows only the selected model for the slate. A blocked or late slate is a valid stop, not a waiver of the gate.

**Validation:** Contract 07/08/09 and 05 verifier receipts, idempotent 09 repeat, Preview DB queries, `/api/health`, browser inspection, freeze/score rehearsal as timing permits, and signed revalidation.

### Task 5 — Record a release decision and perform the cutover separately

**Changes:** Deploy the site/schema changes first with V4 still selected and verify its health. Prepare the immutable V5 production candidate artifact without Neon activation. Assemble a release packet with exact 07/08/09/05 and serving artifact refs/SHAs, Preview results, site screenshots, V4 fallback run, rollback command, health thresholds, model-specific record treatment, and a short statement of historical metric limits. Obtain explicit user approval of that exact packet before creating the production serving release record and activating the prepared V5 artifact. Verify the selected run, coverage, label, score source, ISR, and rendered page, then freeze before kickoff. Keep V4 fallback selectable. If a check fails, reselect V4 and verify health and rendering; preserve failed V5 runs for audit.

**Acceptance:** The activation decision names the exact release identity and slate; a production V5 run becomes public only after it. Rollback works without a code deploy or mutable artifact edit. The public page and health agree on run/model identity. Past V4 weeks remain intact.

**Validation:** Production checklist with recorded queries and URLs, operator review, and a post-activation audit. No automated activation based solely on a passing test or six-slate count.

### Task 6 — Establish the V5 weekly cadence

**Changes:** Document how each following week refreshes certified 07/08 state after stabilized prior-week outcomes, generates/verifies a new frozen-parameter 09 forecast, checks readiness, publishes progressively, freezes before kickoff, closes the selected run, and records Contract 06 attempts and separate quote diagnostics. Preserve V4 as a configurable emergency fallback. A future week cannot reuse a stale forecast or the one-slate release record.

**Acceptance:** Runbooks give one unambiguous operator path; monitoring reports never refit V5 or retroactively qualify a slate. Contract 06's six-slate review can be performed later without blocking V5 site operation.

**Validation:** Runbook walkthrough, strict documentation build, and focused tests for stale-forecast and release-record rejection.

## Testing Strategy

Use synthetic refs for negative lineage and timing cases, then one real Preview rehearsal with exact independently verified parents. Run focused Python and web regressions, Ruff, `make contracts-check`, migration checks, web lint/typecheck/build, strict MkDocs, and `git diff --check`. Confirm no tests or migrations write production. Do not treat fixture tests as proof of live forecast certification or Preview rollback.

## Risks and Edge Cases

- A published V5 artifact can currently reach `publish_to_db.py` directly; final-boundary authorization must precede production use.
- Two model runs for one week make creation-time run selection, close-week, and season aggregates ambiguous. Use the selected run everywhere.
- If V4 fallback is not frozen before kickoff, it cannot become an honest pregame grading fallback after kickoff. Move the cutover or use only the already valid frozen run.
- The existing 2025 context is V4-specific and the current 2026 record is model-agnostic. Label or suppress them as specified above.
- Schedule changes, incomplete paired targets, stale lines, late cutoff, missing quotes, corrected outcomes, partial applies, ISR delay, and Preview/production credential confusion need explicit negative checks. Missing market lines may show no lean under existing policy; they cannot hide a missing forecast game.
- Historical 2025 V4 backtest and V5 historical scorecard are not like-for-like; launch materials must not imply they are.

## Definition of Done

- [ ] User approves this exact plan and resolves the public record policy.
- [ ] Selection, release authorization, site, scoring, and rollback changes pass focused tests and quality gates.
- [ ] All already-public 2026 V4 week selections are reviewed and populated before the new site query is enabled.
- [ ] Refreshed live 07/08, certified 09, and verified `ready` 05 refs exist for the cutover slate.
- [ ] Real Preview publication and V4 rollback evidence pass, with both candidates frozen before kickoff when used as grading fallbacks.
- [ ] A separate user decision approves the exact production release packet; production activation and post-release checks are recorded in a later implementation/operations session.
- [ ] Runbooks, V5 status, plan 04 status, and session log reflect actual behavior; Contract 06 remains monitoring.

## Amendments

Record any change to release authority, per-week selection, score ownership, public record meaning, rollback, or pre-kickoff gates here before implementation. Do not silently weaken the current 07/08/09/05 certification path.
