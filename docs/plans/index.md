# Implementation Contracts

`docs/plans/` holds execution contracts; `docs/planning/` holds strategic roadmaps. Start with [Current Status](../status.md) for live releases, week state and the scoreboard, the [V5 status guide](../modeling/v5_status.md) for model meaning, and the [weekly runbook](../ops/weekly_runbook.md) for recurring operations. Historical freeze/cutover contracts do not add gates to the installed atomic season workflow.

## Current Execution

| Contract | Role | State / next gate |
| --- | --- | --- |
| [Incremental weekly ingestion](2026-10-20/02-incremental-weekly-ingestion.md) | Separate promotion (no provider calls), normal week close/open (new-week requests only) and budgeted history repair | Draft; awaiting owner approval. No provider calls or code changes in the plan. |
| [Website UI/UX foundations, unified shell, matchup hero & performance benchmark](2026-10-20/01-website-ui-ux-improvements.md) | CSS tokens (`--surface-elevated`, `color-scheme`), unified masthead/theme toggle/footer across all 8 routes, matchup hero sources/edges/ranks + top mismatches, 52.4% break-even benchmark on `/performance`, and `TeamHighlightCombobox` hydration fix | Approved with changes October 20; ready for Terra implementation. Land web commits only after the Week 8 line refresh is released. Log: `session_logs/2026-10-20/01-website-ui-ux-review-plan.md`. |
| [Website UI/UX foundations, unified shell, matchup hero & performance benchmark](2026-10-20/01-website-ui-ux-improvements.md) | CSS tokens (`--surface-elevated`, `color-scheme`), unified masthead/theme toggle/footer across all 8 routes, matchup hero sportsbook sources, 52.4% break-even benchmark on `/performance`, and verified zero hydration warnings on `/charts` | Implemented locally October 20; all web lint, typecheck, unit, production build, and 104 E2E tests passed, awaiting owner commit. Logs: `session_logs/2026-10-20/01-website-ui-ux-review-plan.md`, `session_logs/2026-10-20/02-website-ui-ux-implementation.md`. |
| [Website UI/UX Phase 2: BetCell hierarchy, conference filters, ratings rank badges & collapsible matchup sections](2026-10-20/02-website-ui-ux-phase2.md) | `BetCell` 3-line hierarchy condensation on Picks cards, conference filter (`All FBS`, `Power Four + Notre Dame`, individual conferences) on `/ratings`, `/`, and `/results`, rank-tier badges on `/ratings`, and synchronized collapsible secondary sections in `UnitMatchupTable` | Draft October 20; awaiting owner approval or Terra execution authorization. Log: `session_logs/2026-10-20/03-website-ui-ux-phase2-plan.md`. |
| [Website UI/UX foundations, unified shell, matchup hero & performance benchmark](2026-10-20/01-website-ui-ux-improvements.md) | CSS tokens (`--surface-elevated`, `color-scheme`), unified masthead/theme toggle/footer across all 8 routes, matchup hero sportsbook sources, 52.4% break-even benchmark on `/performance`, and verified zero hydration warnings on `/charts` | Implemented and committed on `dev` at `ddb08414` October 20; all web lint, typecheck, unit, production build, and 104 E2E tests passed. Logs: `session_logs/2026-10-20/01-website-ui-ux-review-plan.md`, `session_logs/2026-10-20/02-website-ui-ux-implementation.md`. |
| [SOS/SOR as a season-release projection](2026-10-19/02-sos-sor-release-projection.md) | Strength of schedule, strength of record and wins above average computed per release in Python and served from `season_release_team_resume` | Approved October 19; implemented locally on `connorkitchings/sos-sor-release-projection`, awaiting owner commit. Remaining owner gates: migration 0028 on Preview then Production, the Preview `to_regclass` check, prepare/Preview rehearsal, Production readback. Log: `session_logs/2026-10-19/03-sos-sor-release-projection.md`. |
| [Mobile and Week 8 Production release](2026-10-19/01-mobile-week8-production-release.md) | Deploy mobile and advance Production serving | Complete; Production 0026/0027/0028 and Week 8 activation done, mobile deployed, CI green. Charts remains hidden. |
| [Mobile web experience](2026-10-18/04-mobile-web-experience.md) | Core mobile journeys, shared controls and responsive presentation | Implemented and deployed October 19; mobile journeys and validation complete. Charts and unlinked team-history redesign excluded. |
| [Weeks 6–7 review fixes and V5 streamline](2026-10-15/01-review-fixes-and-v5-streamline.md) | Week 8 safeguards, documentation truth and optional cleanup | In Progress; Phase 1 committed as `2807e087`; Phase 2 documentation validated, awaiting owner commit. Phase 3 is deferred. Week 8 Preview execution awaits Week 7 finals/controller inputs. |
| [Season operations and Week 7 bridge](2026-10-14/01-season-operations-and-week7-bridge.md) | Governing atomic season workflow and first recurring update | In Progress; cutover complete; awaiting first controller weekly update. Section 4 documentation is delivered locally by Phase 2 of the review contract, awaiting its owner commit; local checks do not close the weekly-update acceptance gate. |
| [Weekly-ingestion-repair integration](2026-10-15/03-weekly-ingestion-repair-integration.md) | Salvage the log-13 correction and fixture tests from `codex/weekly-ingestion-repair` (`bb2f1fe8`) | Implemented locally, awaiting owner commit; afterwards the two codex worktrees/branches are deleted. |
| [Charts module: weekly team charts](2026-10-16/01-charts-module.md) | New Charts page (net-success bars, efficiency scatter, adjusted EPA/play) with atomic `charts_v1` release projections | Complete as released, hidden behind `CFB_CHARTS_ENABLED`; deep visual verification deferred until Charts is slated to be un-hidden. Future visual tuning and export performance are follow-ups. |
| [Chart purpose and explosiveness comparison](2026-10-16/02-chart-purpose-and-explosiveness.md) | Chart controls, PPA labels and pinned Week 7 offline comparison | Initial delivery implemented; owner selected 20+ yard rate and yards/success. The serving phase follows the October 18 expansion contract. |
| [Charts review and expansion](2026-10-18/01-charts-review-and-expansion.md) | Release-backed explosiveness and six chart views | Complete as released, hidden behind `CFB_CHARTS_ENABLED`; migrations 0027/0028 applied and `charts_v2` serving. Visual verification deferred until un-hide. |

## Supporting / In-Progress

| Contract | Role / remaining obligation |
| --- | --- |
| [V5 Product Transformation](2026-09-23/01-v5-product-transformation.md) | Retained product and dependency-checked retirement obligations; record presentation follows the unified [methodology](../modeling/record_methodology.md). |
| [06: prospective monitoring](2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | Continuing 2026 outcome monitoring and immutable provenance. Six slates are not a launch prerequisite. |
| [Matchup data layer v2](2026-10-02/01-matchup-data-layer-v2.md) | Retained requirements for corrected repinning and 2025 backfill; unfinished work is in the [deferred backlog](../status.md#deferred-backlog). |
| [Team stats as the source of basic stats](2026-10-02/03-team-stats-feeds-ratings.md) | Draft with Phase 1 implementation; remaining numerical repair is backlog, not a weekly gate. |
| [Week 5 data-issue investigation](2026-10-03/02-week5-data-issue-investigation.md) | Retained read-only findings and supporting specifications; not a separate publication path. |

## Superseded Operating Contracts

The following contracts are Superseded by [season operations](2026-10-14/01-season-operations-and-week7-bridge.md) and the [review/documentation contract](2026-10-15/01-review-fixes-and-v5-streamline.md). Their files, amendments and evidence stay at their original paths. Supersession does not mean unfinished repairs were implemented: remaining data obligations are retained in the [deferred backlog](../status.md#deferred-backlog), with detailed historical evidence in the repair matrix.

| Contract | Historical role |
| --- | --- |
| [Stage 7B exact release and cutover](2026-10-06/02-stage7b-exact-release-and-cutover.md) | Component packet, freeze and repin cutover. |
| [Repair-track certification and closure](2026-10-08/02-repair-track-certification-and-closure.md) | Historical completion matrix; unfinished quality/numerical work survives in backlog. |
| [Week 6 display-only Production release](2026-10-09/02-week6-display-production-release.md) | Single-week display release and follow-through. |
| [Week 7 cutover run sheet](2026-10-10/01-week7-cutover-run-sheet.md) | Dated pivot, exact packet and fallback instructions. |
| [Week 6 closeout and transition review](2026-10-11/01-week6-closeout-and-transition-review.md) | Historical finals/grades/replay preflight. |
| [Week 7 cutover gate waiver and readiness](2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md) | Historical checkpoint/finals-stability waiver. |
| [Week 7 standalone fallback](2026-10-11/03-week7-standalone-fallback.md) | Unused standalone alternative. |
| [Task 4 verification and catalog repair](2026-10-13/02-task4-verification-and-catalog-repair.md) | Bounded predecessor repair and catalog recovery. |
| [Task 4 baseline and Week 7 display continuation](2026-10-13/03-task4-baseline-and-week7-display-continuation.md) | Baseline enforcement and display bridge. |
| [Data integrity repair in two windows](2026-10-03/04-data-integrity-two-window-implementation.md) | Historical parent specifications; unfinished numerical work remains backlog. |
| [Repair weekly ingestion and stage an honest Week 8 template](2026-10-15/02-weekly-ingestion-repair.md) | Manual-ingestion checklist and pending Week 8 template from `codex/weekly-ingestion-repair` (`bb2f1fe8`), never merged. The operational repair landed in Phase 1 of the review contract (`2807e087`) via the controller flow; the log-13 correction and fixture tests were integrated by [the integration contract](2026-10-15/03-weekly-ingestion-repair-integration.md), and the manual runbook section and template were rejected. |

## Completed and Supporting Evidence

| Contract | State / retained evidence |
| --- | --- |
| [CI speedup](2026-10-14/03-ci-speedup.md) | Merged, PR #7. Hosted PostgreSQL 16 checks passed; retained result is 69% coverage and 4m32s execution. No new hosted run is claimed here. |
| [Permanent venue-catalog fix](2026-10-14/02-venues-complete-catalog-fix.md) | Implemented; complete 11-season catalog and supplement-free Preview/Production readback recorded in the contract. |
| [Pre-finals integrity and cutover preparation](2026-10-10/03-pre-finals-integrity-and-cutover-preparation.md) | Implemented documentation preparation only; dated operating gates are historical under the superseded parent. |
| [95 database-only adjusted rows investigation](2026-10-10/04-investigate-database-only-adjusted-rows.md) | Implemented read-only investigation; replacement and cleanup remain deferred. |
| [Bounded source-lock extender repair](2026-10-11/01-bounded-source-lock-extender-repair.md) | Implemented bounded compatibility evidence; no recurring legacy controller requirement. |

## Deferred Backlog

| Contract / effort | Resume gate |
| --- | --- |
| [Data correctness backlog](../status.md#deferred-backlog) | Separately scope EPA replacement, six quality follow-ups, scoring/descendant recertification, 2025 matchup backfill and non-monotonic scores. |
| [Archive unique local artifacts](2026-09-27/03-archive-unique-local-artifacts.md) | Retained lifecycle proof and approved prune remain open; no artifact deletion is authorized by documentation housekeeping. |
| [Production boundary refactor](2026-10-01/04-production-boundary-refactor.md) | Draft; separate architecture acceptance and approval. |
| [V5 streamlining, Phase 3](2026-10-15/01-review-fixes-and-v5-streamline.md#phase-3--streamline-deferrable) | Deferred; check import reachability and record combined coverage before any deletion, stop below 60%. |
| Physical historical-plan archival | No plan/evidence paths move in this cleanup. |

## Historical Records

Lifecycle metadata remains in each original file. This table is navigation, not new execution authority. Historical plans have not moved. The former checkpoint “Week 4 refresh awaits stabilized finals” was satisfied on 2026-09-27.

| Collection | Contracts retained at their original paths |
| --- | --- |
| Ratings and live forecasting | [V5 ratings publication and navigation](2026-09-26/03-v5-ratings-publication-and-navigation.md); [Ratings lifecycle integration](2026-09-27/04-ratings-lifecycle-integration.md); [V5 authority and cutover](2026-09-22/04-v5-authority-simplification-and-site-cutover.md); [07: 2026 measurements](2026-09-18/07-v5-2026-repair-and-measurement-extension.md); [08: 2026 ratings](2026-09-18/08-v5-2026-rating-state-replay.md); [09: live forecast](2026-09-18/09-v5-2026-forecast-and-readiness.md); [Weekly ratings history replay](2026-09-27/05-weekly-ratings-history-replay.md); [2026 V5 intended-update production repair](2026-09-29/v5-intended-update-2026-production-repair.md); [Performance dashboard](2026-10-01/01-performance-dashboard-enhancements.md) |
| Product and repository delivery | [Authentic team stats pipeline](2026-10-01/10-authentic-team-stats-pipeline.md); [Dead-code prune](2026-10-01/05-dead-code-prune.md); [Docs cleanup and archive](2026-10-01/06-docs-cleanup-and-archive.md); [Game venue location](2026-10-01/08-game-venue-location.md); [High-quality team logos](2026-10-01/07-high-quality-team-logos.md); [Port picks/results prototypes to production](2026-10-02/02-port-picks-results-prototypes.md); [Remove edge constraints and grade all games](2026-10-02/04-remove-edge-constraints-grade-all-games.md) |
| Data decisions and rebuilds | [Data issues: review and rerun together](2026-10-02/05-data-issues-review-and-rerun.md); [Unified data fix and matchup rollout](2026-10-03/01-unified-data-fix-and-matchup-rollout.md); [Data integrity decision packet](2026-10-03/03-data-decision-packet.md); [Pre-Stage-6 integrity and rebuild](2026-10-04/02-pre-stage6-integrity-and-rebuild.md); [Stage 6B completed-week reconstruction](2026-10-05/01-stage6b-completed-week-reconstruction.md); [Stage 6B Task 2 quality review](2026-10-05/02-stage6b-task2-quality-review.md); [Pipeline data-quality gates](2026-10-04/01-pipeline-data-quality-gates.md) |
| Release and corrected-lineage delivery | [Stage 7A release foundations](2026-10-06/01-stage7a-release-foundations.md); [Track 1: Production venues and full `dev` promotion](2026-10-07/01-track1-production-promotion.md); [byplay_v2 play identity](2026-10-09/01-byplay-v2-play-identity.md); [6A-bridged matchup publication](2026-10-09/03-matchup-6a-bridge.md); [Stage 1: Week 5 corrected data finalization](2026-10-07/04-stage1-week5-corrected-data-finalization.md); [Stage 1 decision brief](2026-10-08/01-stage1-decision-brief.md); [Week 6 display-only run on the served lineage](2026-10-07/03-week6-display-run.md) |
| Earlier V5 delivery | [V4-to-V5 site transition draft](2026-09-22/05-v4-to-v5-site-transition.md); [replay and Preview rehearsal](2026-09-24/01-v5-replay-preview-rehearsal.md); [weekly operator and exact release gates](2026-09-24/02-v5-weekly-operator-and-release-gates.md); [Week 4 finals to live Preview evidence](2026-09-25/01-v5-week4-finals-to-live-preview.md); [Week 4 replay site cutover](2026-09-25/02-v5-week4-replay-site-cutover.md) |
| Research benchmark | [V6 ratings research platform](2026-09-28/v6-ratings-research-platform.md); [Phase 5](2026-09-30/07-v6-phase5-finishing-drives.md): retained as benchmark, no production effect |
| Earlier model/audit evidence | [V5 contract archive](../archive/v5-contracts/index.md): completed/superseded methodology, audits, diagnostics and code readiness, including the unrelated V4 feature-schema-v5 diagnostic |
| This documentation cleanup | [Cutover-safe documentation consolidation](2026-10-10/02-cutover-safe-documentation-consolidation.md): logical indexing and compact template only; no repair or release closure |

The [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md) retains independent research context. The [weekly runbook](../ops/weekly_runbook.md) is the sole recurring operational authority; old runbooks are archived with redirects. V4 is documented in the [retrospective](../modeling/v4_retrospective.md), not operated.

**Numbering notes:** `2026-10-01/` has no `09` (the former `02` matchup-stats draft became `10`) and `2026-09-30/` has no `04`; numbering stays stable. The October 1 close-out of twenty older contracts is recorded in their status lines.

## Contract Workflow

Store contracts at `docs/plans/YYYY-MM-DD/<descriptive-slug>.md`; use numeric prefixes only when same-day ordering matters. The template at `.agent/skills/plan-session/assets/implementation-contract-template.md` retains lifecycle metadata and five sections: Goal and acceptance; Baseline and constraints; Ordered changes; Validation; Handoff/amendments.

| Status | Meaning |
| --- | --- |
| `Draft` | Investigation or approval pending. |
| `Approved` | Ready for Terra under recorded approval or an explicit handoff naming the exact path. |
| `In Progress` | Implementation underway. |
| `Implemented` | All acceptance criteria and required validation passed. |
| `Merged` | Implemented and merged; integration evidence is recorded in the contract. |
| `Superseded` | A later contract replaces this scope. |

Use Sol planning → approval → persisted contract → fresh Terra implementation for architecture, data/model lineage, schemas/migrations, production/deployment, security-sensitive or multi-subsystem work. A Draft requires explicit authorization naming its exact path before implementation; record approval first. Use the established fast path for localized changes.

Mechanical amendments may proceed only if architecture, interfaces, scope and acceptance remain intact; material conflicts return to Sol. Record commit policy; separate plan commits remain recommended for multi-session, asynchronous, migration, production or difficult-to-reverse work. Git operations remain user-controlled.
