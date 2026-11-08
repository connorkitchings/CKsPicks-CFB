# Implementation Contracts

`docs/plans/` holds open execution contracts and the October 2026 contracts; `docs/planning/` holds strategic roadmaps. Start with [Current Status](../status.md) for live releases, week state and the scoreboard, the [V5 status guide](../modeling/v5_status.md) for model meaning, and the [weekly runbook](../ops/weekly_runbook.md) for recurring operations. Historical freeze/cutover contracts do not add gates to the installed atomic season workflow.

Closed contracts dated before 2026-10-01 (Implemented, Merged or Superseded) are archived under `docs/archive/plans/`; see the [archived contracts index](../archive/plans/index.md) and the [V5 contract archive](../archive/v5-contracts/index.md). Status is read from each file's own `Status` line.

## Current Execution

Contracts whose status is In Progress, Draft or Approved (newest first).

| Contract | Role | State / next gate |
| --- | --- | --- |
| [Web read performance](2026-10-29/01-web-read-performance.md) | Measure Vercel TTFB, release-cache the matchup loader, resolve ineffective ISR, cache key and `/model` entry size | Draft under the revised [roadmap](../planning/data_architecture_blueprint.md); runs in parallel with Stage 1a. Exact-path approval is the next gate. No deploy or data operations authorized. |
| [Data architecture Stage 1a: operational safeguards and baseline](2026-10-28/01-data-architecture-operational-safeguards.md) | Revision-specific immutable score exceptions, provider-free promotion and rollover request tests, full-history refusal and a `prepare` timing baseline; the budgeted repair CLI is deferred as Stage 1b | Draft, reduced to 1a on 2026-10-29 under the owner-approved [migration blueprint](../planning/data_architecture_blueprint.md); exact-path approval is the next gate. No data operations authorized. |
| [Stratum CFB rebrand](2026-10-27/stratum-cfb-rebrand.md) | Public identity, licensed wordmark, exports, metadata and current documentation; existing URL and data unchanged | Implemented 2026-10-27; published through PR #17 (`ab74daca`); full local gates and PR CI passed. |
| [Advanced visualization suite](2026-10-26/02-advanced-visualization-suite.md) | Five experimental visualizations: Standard vs Passing Downs, Finishing Drives, Resume vs Quality, Slate Market Board, and Matchup 5 Factors Tale of the Tape | Implemented October 26; verified with `make check`. Log: `session_logs/2026-10-26/03-advanced-visualization-suite-implementation.md`. |
| [Weekly update automation](2026-10-26/01-weekly-update-automation.md) | Unattended GitHub Actions close-week and market-refresh with automatic Production activation when every gate passes | Approved October 26; implemented on `connorkitchings/weekly-update-automation`. Owner gates: GitHub environment and secrets, `dev` to `main` release (merge commit), Preview rehearsal, then `CFB_WEEKLY_AUTOMATION_ENABLED=true`. Log: `session_logs/2026-10-26/01-weekly-update-automation.md`. |
| [Pre-merge fixes and Crest release completion](2026-10-25/01-pre-merge-fixes-and-crest-release.md) | Six review fixes plus the open-licence wordmark regeneration, then the `dev` to `main` publication | Implemented; deployed to Production 2026-10-25 in `86c16f66` |
| [Incremental close-week rollover and Week 8→9 advance](2026-10-25/01-incremental-close-week-rollover.md) | Narrow amendment of the incremental-ingestion draft: implement the normal close/open path (`advance-week`, carried captures, history stop gate, `season-close-week` target), then close Week 8 and open Week 9 on Preview | Approved October 25; implementation and Preview-only rollover in progress on `connorkitchings/incremental-close-week`. |
| [Repository consolidation, pruning and production hardening](2026-10-22/01-repo-consolidation.md) | Delete V4/legacy code, consolidate agent guidance and docs, archive closed plans and logs, harden CI and environment variables | Approved October 22; one commit per group on `connorkitchings/repo-consolidation`, merge into `dev` after owner review. Nothing goes to `main` or Production. Log: `session_logs/2026-10-22/02-repo-consolidation.md`. |
| [Serving-parity check and `rebuild/` retirement](2026-10-22/02-parity-and-rebuild-retirement.md) | Prove pruned `dev` reproduces the served projections; remove the 6A/6B rebuild package | Implemented October 22; log `session_logs/2026-10-22/03-parity-and-rebuild-retirement.md`. |
| [Mobile charts B: inspector](2026-10-21/04-mobile-charts-b-inspector.md) | Shared state, native-dialog SVG inspector, button zoom and native scrolling | Draft; blocked on A acceptance and separate owner authorization. |
| [Mobile charts A: page](2026-10-21/03-mobile-charts-a-page.md) | Independent mobile reflow, readable chart text, game-log rows, selection and settings | Implemented 2026-10-25; real-device acceptance waived by the owner. Log: `session_logs/2026-10-21/03-mobile-charts-a-implementation.md`. |
| [Site reorganization, design consistency and performance](2026-10-21/01-site-reorganization-and-performance.md) | Release-keyed data cache and query fixes (Phase 1), shared Card/Notice design system (2), four-tab navigation with merged Matchups and Model plus team links (3), Stats publication (4) | Implemented 2026-10-25; published to Production with the `dev` to `main` release. Review log: `session_logs/2026-10-25/01-final-site-review.md`. |
| [Charts pre-publication verification](2026-10-20/03-charts-pre-publication.md) | What had to be tested and decided before Charts was published | Superseded and Implemented 2026-10-25; Graphs published without a feature flag. Review log: `session_logs/2026-10-25/01-final-site-review.md`. |
| [Incremental weekly ingestion](2026-10-20/02-incremental-weekly-ingestion.md) | Separate promotion (no provider calls), normal week close/open (new-week requests only) and budgeted history repair | Draft; the normal close/open path is being implemented first under the owner-approved narrow amendment [2026-10-25/01](2026-10-25/01-incremental-close-week-rollover.md); repair mode and promotion harness remain deferred. No provider calls or code changes were made in this plan. |
| [SOS/SOR as a season-release projection](2026-10-19/02-sos-sor-release-projection.md) | Strength of schedule, strength of record and wins above average computed per release in Python and served from `season_release_team_resume` | Approved October 19; implemented locally on `connorkitchings/sos-sor-release-projection`, awaiting owner commit. Remaining owner gates: migration 0028 on Preview then Production, the Preview `to_regclass` check, prepare/Preview rehearsal, Production readback. Log: `session_logs/2026-10-19/03-sos-sor-release-projection.md`. |
| [Charts ratings and possession views](2026-10-18/03-charts-ratings-and-possession.md) | Rating-trajectory and possession views on a shared trajectory panel | Implemented; published as Graphs (`/stats`) on 2026-10-25 with no feature flag. Review: [2026-10-20/03](2026-10-20/03-charts-pre-publication.md). |
| [Charts review and expansion](2026-10-18/01-charts-review-and-expansion.md) | Release-backed explosiveness and six chart views | In Progress; code complete, migrations 0027/0028 applied and `charts_v2` serving. Pre-publication verification: [2026-10-20/03](2026-10-20/03-charts-pre-publication.md). |
| [Charts module: weekly team charts](2026-10-16/01-charts-module.md) | New Charts page (net-success bars, efficiency scatter, adjusted EPA/play) with atomic `charts_v1` release projections | Implemented; published as Graphs (`/stats`) on 2026-10-25 with no feature flag. Review: [2026-10-20/03](2026-10-20/03-charts-pre-publication.md). Future visual tuning and export performance are follow-ups. |
| [Season operations and Week 7 bridge](2026-10-14/01-season-operations-and-week7-bridge.md) | Governing atomic season workflow and first recurring update | In Progress; cutover complete; awaiting first controller weekly update. Section 4 documentation is delivered locally by Phase 2 of the review contract, awaiting its owner commit; local checks do not close the weekly-update acceptance gate. |
| [Stage 7B preflight hold](2026-10-06/stage7b-preflight-hold.md) | Historical hold record, preserved unchanged; execution authority is the superseded Stage 7B contract | In Progress (as recorded); evidence only, no execution authority. |
| [Stage 7B attestation implementation evidence](2026-10-06/stage7b-attestation-implementation-evidence.md) | Evidence packet for the superseded Stage 7B contract; execution authority is that contract | In Progress (as recorded); evidence only, no execution authority. |
| [Week 5 data-issue investigation](2026-10-03/02-week5-data-issue-investigation.md) | Retained read-only findings and supporting specifications; not a separate publication path | Approved (read-only); authorizes investigation only. Writes are governed by the superseded two-window contract. |
| [Team stats as the source of basic stats](2026-10-02/03-team-stats-feeds-ratings.md) | Phase 1 implemented; remaining numerical repair is backlog, not a weekly gate | Draft (Phase 1 implemented 2026-10-02; Phase 2 superseded as execution scope by the two-window data-integrity contract). |
| [Matchup data layer v2](2026-10-02/01-matchup-data-layer-v2.md) | Retained requirements for corrected repinning and 2025 backfill; unfinished work is in the [deferred backlog](../status.md#deferred-backlog) | Approved. |
| [Production boundary refactor](2026-10-01/04-production-boundary-refactor.md) | Separate architecture acceptance and approval | Draft. |
| [Archive unique local artifacts](2026-09-27/03-archive-unique-local-artifacts.md) | Retained lifecycle proof and approved prune remain open; no artifact deletion is authorized by documentation housekeeping | In Progress. |
| [V5 Product Transformation](2026-09-23/01-v5-product-transformation.md) | Retained product and dependency-checked retirement obligations; record presentation follows the unified [methodology](../modeling/record_methodology.md) | In Progress. |
| [06: prospective monitoring](2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | Continuing 2026 outcome monitoring and immutable provenance | In Progress; monitoring tooling ready, no qualifying live slate yet. Six slates are not a launch prerequisite. |

## Deferred

| Contract | Role | State / resume gate |
| --- | --- | --- |
| [Mobile charts C: evaluation](2026-10-21/05-mobile-charts-c-evaluation.md) | Evaluate custom gestures/history only after inspector device evidence | Deferred; no gesture/history code authorized. |
| [Data correctness backlog](../status.md#deferred-backlog) | EPA replacement, six quality follow-ups, scoring/descendant recertification, 2025 matchup backfill and non-monotonic scores | Separately scoped; not a weekly gate. |

## Closed Contracts Kept in Place

Every contract still under `docs/plans/` that is not listed above, one row per file, oldest first. All are dated October 2026; lifecycle metadata, amendments and evidence stay in each file. Supersession does not mean unfinished repairs were implemented: remaining data obligations are retained in the [deferred backlog](../status.md#deferred-backlog). This table is navigation, not execution authority.

| Date | Contract | Status |
| --- | --- | --- |
| 2026-10-01 | [Implementation Contract: Performance Dashboard Enhancements](2026-10-01/01-performance-dashboard-enhancements.md) | Implemented |
| 2026-10-01 | [Plan: Frontend Modularity, Shared Slate Architecture & Comparative Utility](2026-10-01/02-web-architecture-modularity-and-slate-enhancements.md) | Implemented |
| 2026-10-01 | [Plan: Advanced Stats Matchup Breakdown (Parker Fleming Style)](2026-10-01/03-advanced-stats-matchup-breakdown.md) | Implemented |
| 2026-10-01 | [Dead-Code Prune](2026-10-01/05-dead-code-prune.md) | Implemented |
| 2026-10-01 | [Documentation Cleanup, Contract Close-out and Archive/Delete](2026-10-01/06-docs-cleanup-and-archive.md) | Implemented |
| 2026-10-01 | [High-Quality Team Logos: Self-Hosted, ID-Keyed, Theme-Aware](2026-10-01/07-high-quality-team-logos.md) | Implemented |
| 2026-10-01 | [Game Venue Location (City, State) on Picks and Results](2026-10-01/08-game-venue-location.md) | Implemented |
| 2026-10-01 | [Authentic Team Stats: Play-by-Play Pipeline, Neon Table, Gated Matchup Read](2026-10-01/10-authentic-team-stats-pipeline.md) | Implemented |
| 2026-10-02 | [Port Picks/Results Prototypes to Production](2026-10-02/02-port-picks-results-prototypes.md) | Implemented |
| 2026-10-02 | [Remove Edge Constraints and Grade All Games](2026-10-02/04-remove-edge-constraints-grade-all-games.md) | Implemented |
| 2026-10-02 | [Data Issues: Review and Rerun Together](2026-10-02/05-data-issues-review-and-rerun.md) | Superseded |
| 2026-10-03 | [Unified Data Fix and Matchup Rollout (Historical Investigation Record)](2026-10-03/01-unified-data-fix-and-matchup-rollout.md) | Superseded |
| 2026-10-03 | [Data integrity review: decision packet (D1-D9)](2026-10-03/03-data-decision-packet.md) | Implemented |
| 2026-10-03 | [Data Integrity Repair in Two Windows](2026-10-03/04-data-integrity-two-window-implementation.md) | Superseded |
| 2026-10-04 | [Pipeline Data-Quality Gates](2026-10-04/01-pipeline-data-quality-gates.md) | Implemented |
| 2026-10-04 | [Pre-Stage-6 Integrity and Corrected-Lineage Rebuild](2026-10-04/02-pre-stage6-integrity-and-rebuild.md) | Implemented |
| 2026-10-05 | [Stage 6B: Completed-Week Reconstruction (2026 Weeks 0–5)](2026-10-05/01-stage6b-completed-week-reconstruction.md) | Implemented |
| 2026-10-05 | [Stage 6B Task 2 Quality Review and Repair](2026-10-05/02-stage6b-task2-quality-review.md) | Implemented |
| 2026-10-06 | [Stage 7A: Release Foundations](2026-10-06/01-stage7a-release-foundations.md) | Implemented |
| 2026-10-06 | [Stage 7B: Exact Release and Cutover](2026-10-06/02-stage7b-exact-release-and-cutover.md) | Superseded |
| 2026-10-07 | [Track 1: Production Venues and Full `dev` Promotion](2026-10-07/01-track1-production-promotion.md) | Implemented |
| 2026-10-07 | [Week 6 Display-Only Run on Served (Successor) Lineage](2026-10-07/03-week6-display-run.md) | Superseded |
| 2026-10-07 | [Stage 1: Week 5 corrected data finalization (Preview only)](2026-10-07/04-stage1-week5-corrected-data-finalization.md) | Implemented |
| 2026-10-07 | [Track 1 release preparation packet — PROMOTED 2026-10-07 (see the final section; earlier text below is the pre-promotion record)](2026-10-07/track1-release-packet.md) | Implemented |
| 2026-10-08 | [Stage 1 decision brief: what the corrected data work produced and how to release it](2026-10-08/01-stage1-decision-brief.md) | Implemented |
| 2026-10-08 | [Repair-track certification and closure](2026-10-08/02-repair-track-certification-and-closure.md) | Superseded |
| 2026-10-09 | [byplay_v2: provider-keyed play identity (impact-first)](2026-10-09/01-byplay-v2-play-identity.md) | Implemented |
| 2026-10-09 | [Week 6 Display-Only Run: Production Release](2026-10-09/02-week6-display-production-release.md) | Superseded |
| 2026-10-09 | [6A-Bridged Matchup Publication for the Corrected Lineage](2026-10-09/03-matchup-6a-bridge.md) | Implemented |
| 2026-10-10 | [Week 7 cutover run sheet (Weeks 0-6 corrected replays + pending Week 7)](2026-10-10/01-week7-cutover-run-sheet.md) | Superseded |
| 2026-10-10 | [Cutover-safe documentation consolidation](2026-10-10/02-cutover-safe-documentation-consolidation.md) | Implemented |
| 2026-10-10 | [Pre-finals integrity and cutover preparation](2026-10-10/03-pre-finals-integrity-and-cutover-preparation.md) | Implemented |
| 2026-10-10 | [Investigate the 95 database-only adjusted rows](2026-10-10/04-investigate-database-only-adjusted-rows.md) | Implemented |
| 2026-10-11 | [Bounded source-lock extender repair](2026-10-11/01-bounded-source-lock-extender-repair.md) | Implemented |
| 2026-10-11 | [Week 6 closeout and Week 7 transition review](2026-10-11/01-week6-closeout-and-transition-review.md) | Superseded |
| 2026-10-11 | [Week 7 cutover gate waiver and readiness](2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md) | Superseded |
| 2026-10-11 | [Week 7 standalone fallback (display-only on corrected ratings through Week 6)](2026-10-11/03-week7-standalone-fallback.md) | Superseded |
| 2026-10-11 | [Week 7 transition review — October 11 preflight](2026-10-11/week7-transition-review.md) | Evidence companion (no status line) |
| 2026-10-13 | [Task 4 Verification and Catalog Registration Repair (6a-task4-w6-r2)](2026-10-13/02-task4-verification-and-catalog-repair.md) | Superseded |
| 2026-10-13 | [Task 4 Baseline Enforcement and Week 7 Display-Only Continuation](2026-10-13/03-task4-baseline-and-week7-display-continuation.md) | Superseded |
| 2026-10-14 | [Permanent Venue-Catalog Fix: Ingest the Complete CFBD Catalog in Raw + Silver](2026-10-14/02-venues-complete-catalog-fix.md) | Implemented |
| 2026-10-14 | [Speed up CI while preserving regression coverage](2026-10-14/03-ci-speedup.md) | Merged |
| 2026-10-15 | [Weeks 6–7 review fixes and V5 streamline](2026-10-15/01-review-fixes-and-v5-streamline.md) | Implemented; Phase 3 is complete, executed by the [repository consolidation contract](2026-10-22/01-repo-consolidation.md) |
| 2026-10-15 | [Repair weekly ingestion and stage an honest Week 8 template](2026-10-15/02-weekly-ingestion-repair.md) | Superseded |
| 2026-10-15 | [Integrate weekly-ingestion-repair branch remnants](2026-10-15/03-weekly-ingestion-repair-integration.md) | Implemented locally |
| 2026-10-16 | [Chart purpose, organization, and weekly data — Revision 5](2026-10-16/02-chart-purpose-and-explosiveness.md) | Implemented |
| 2026-10-18 | [Parity gate evidence (Phase 1, section 1f)](2026-10-18/01a-parity-evidence.md) | Evidence companion (no status line) |
| 2026-10-18 | [Keep Charts unpublished behind an explicit flag](2026-10-18/02-charts-publication-gate.md) | Implemented |
| 2026-10-18 | [Mobile web experience](2026-10-18/04-mobile-web-experience.md) | Implemented |
| 2026-10-19 | [Mobile and Week 8 Production release](2026-10-19/01-mobile-week8-production-release.md) | Complete |
| 2026-10-20 | [Website UI/UX Foundations, Unified App Shell, Matchup Hero & Performance Benchmark](2026-10-20/01-website-ui-ux-improvements.md) | Implemented |
| 2026-10-20 | [Website UI/UX Phase 2: BetCell Hierarchy, Conference Filters, Ratings Rank Badges & Collapsible Matchup Sections](2026-10-20/02-website-ui-ux-phase2.md) | Implemented |

The [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md) retains independent research context. The [weekly runbook](../ops/weekly_runbook.md) is the sole recurring operational authority; old runbooks are archived. V4 is documented in the [retrospective](../modeling/v4_retrospective.md), not operated.

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
