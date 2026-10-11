# Implementation Contracts

`docs/plans/` holds task-level Sol-to-Terra contracts; `docs/planning/` holds strategic roadmaps. Start with [Current Status](../status.md) for selected runs, week state and the scoreboard, or the [V5 status guide](../modeling/v5_status.md) for the accepted model and V4 rollback boundaries.

## Current Execution

| Contract | Role | State / next gate |
| --- | --- | --- |
| [Week 6 closeout and transition review](2026-10-11/01-week6-closeout-and-transition-review.md) | Grade the served Week 6 run and certify its complete corrected replay; Week 7 held | In Progress; retained preflight and bounded extender tooling delivered. The 24-hour stability gate is removed ([contract 02](2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md)); clean apply code and operational replay certification remain required. [Transition review](2026-10-11/week7-transition-review.md). |
| [Week 7 cutover gate waiver and readiness](2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md) | Waives the Sunday checkpoint and integrity-first rule for the Week 7 cutover; removes the 24-hour finals rule | Approved; code delivered locally. Data steps, release and Production remain separate user decisions. |
| [Repair-track certification and closure](2026-10-08/02-repair-track-certification-and-closure.md) | Authoritative completion matrix for the October 4 repair objective | In Progress; integrity closure waived for the Week 7 cutover only (Amendment 14). Stage 1 closure does not close this track. |
| [Week 7 cutover run sheet](2026-10-10/01-week7-cutover-run-sheet.md) | Ordered execution, pivot gate and fallback under the repair contract | Draft; adds no release authority. Stable finals, certification and Preview rehearsal remain required. |

## Supporting / In-Progress

Supporting contracts retain their own approval and acceptance criteria. The repair matrix maps their unfinished repair/release obligations; independent work keeps its original owner.

| Contract | Role / remaining obligation |
| --- | --- |
| [Bounded source-lock extender repair](2026-10-11/01-bounded-source-lock-extender-repair.md) | Implemented; fixture-only append and successor compatibility verified. Operational lock generation remains stability-gated. |
| [Week 6 display-only Production release](2026-10-09/02-week6-display-production-release.md) | In Progress; Tasks 6–7 verification, configuration follow-through and post-finals grades-only backfill. No freeze or close. |
| [Stage 7B exact release and cutover](2026-10-06/02-stage7b-exact-release-and-cutover.md) | In Progress; foundations delivered, exact packet execution, freeze, repin, readback and rollback still gated. |
| [V5 Product Transformation](2026-09-23/01-v5-product-transformation.md) | In Progress; retains product/workflow acceptance and dependency-checked retirement obligations. Current record presentation follows the unified [record methodology](../modeling/record_methodology.md). |
| [06: prospective monitoring](2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | Ongoing immutable attempt/freeze records, outcome reports and quote diagnostics. Six slates are not a launch prerequisite; the count is a monitoring window. |
| [Matchup data layer v2](2026-10-02/01-matchup-data-layer-v2.md) | Approved supporting contract; corrected repinning and 2025 historical backfill remain mapped to repair closure. Delivered phases do not close the backfill. |
| [Team stats as the source of basic stats](2026-10-02/03-team-stats-feeds-ratings.md) | Draft with Phase 1 implemented; Phase 2 repair scope belongs to D4 of the two-window contract, not a separate rebuild. |
| [Week 5 data-issue investigation](2026-10-03/02-week5-data-issue-investigation.md) | Approved read-only evidence scope; Amendment 3 records delivered findings. Repair writes are governed by the successor contract. |
| [Data integrity repair in two windows](2026-10-03/04-data-integrity-two-window-implementation.md) | In Progress historical parent; [data specification](2026-10-03/window2/data-contracts-and-certification.md) and [release/schema/web specification](2026-10-03/window2/release-schema-and-web.md) retain normative gates, as amended. Remaining execution is tracked in the repair matrix. |

## Deferred Backlog

| Contract / effort | Owner and resume gate |
| --- | --- |
| [Archive unique local artifacts](2026-09-27/03-archive-unique-local-artifacts.md) | In Progress; 11 backups byte-verified, lifecycle proof and approved prune remain open. No artifact deletion is authorized by documentation housekeeping. |
| [Production boundary refactor](2026-10-01/04-production-boundary-refactor.md) | Draft; separate architecture acceptance and approval, outside repair execution. |
| Physical historical-plan archival; weekly-runbook consolidation | Deferred to Week 8 steady-state after repair/cutover closure; needs a separate reviewed scope. All plan and pinned-input paths stay unchanged now. |

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

The [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md) retains research context. The [V5 weekly operator](../ops/v5_weekly_operator.md) governs recurring stages and exact gates; the [production runbook](../ops/production_runbook.md) retains V4 rollback procedures. These runbooks remain separate through cutover.

**Numbering notes:** `2026-10-01/` has no `09` (the former `02` matchup-stats draft became `10`) and `2026-09-30/` has no `04`; numbering stays stable. The October 1 close-out of twenty older contracts is recorded in their status lines.

## Contract Workflow

Store contracts at `docs/plans/YYYY-MM-DD/<descriptive-slug>.md`; use numeric prefixes only when same-day ordering matters. The template at `.agent/skills/plan-session/assets/implementation-contract-template.md` retains lifecycle metadata and five sections: Goal and acceptance; Baseline and constraints; Ordered changes; Validation; Handoff/amendments.

| Status | Meaning |
| --- | --- |
| `Draft` | Investigation or approval pending. |
| `Approved` | Ready for Terra under recorded approval or an explicit handoff naming the exact path. |
| `In Progress` | Implementation underway. |
| `Implemented` | All acceptance criteria and required validation passed. |
| `Superseded` | A later contract replaces this scope. |

Use Sol planning → approval → persisted contract → fresh Terra implementation for architecture, data/model lineage, schemas/migrations, production/deployment, security-sensitive or multi-subsystem work. A Draft requires explicit authorization naming its exact path before implementation; record approval first. Use the established fast path for localized changes.

Mechanical amendments may proceed only if architecture, interfaces, scope and acceptance remain intact; material conflicts return to Sol. Record commit policy; separate plan commits remain recommended for multi-session, asynchronous, migration, production or difficult-to-reverse work. Git operations remain user-controlled.
