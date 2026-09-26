# Implementation Contracts

`docs/plans/` holds task-level implementation contracts prepared by Sol and executed by a fresh Terra task. It is distinct from `docs/planning/`, which holds strategic roadmaps and long-lived initiatives.

## Location and naming

Store each contract at:

```text
docs/plans/YYYY-MM-DD/<descriptive-slug>.md
```

The date folder is the chronological ordering. Prefix a same-day filename with `01-`, `02-`, and so on only when implementation order matters.

Copy the template from `.agent/skills/plan-session/assets/implementation-contract-template.md`. A contract records status, approval source, implementation log, and commit policy as well as the goal, current state, tasks, validation, risks, definition of done, and amendments.

## Lifecycle

| Status | Meaning |
| --- | --- |
| `Draft` | Sol is investigating or the user has not approved the contract. |
| `Approved` | The contract is ready for Terra, either by recorded approval or an explicit user handoff for the exact path. |
| `In Progress` | Terra is implementing the contract. |
| `Implemented` | All definition-of-done items and required validation have passed. |
| `Superseded` | A later contract replaces this one. |

Terra must not execute a Draft contract without an explicit user instruction naming that exact path. In that case, Terra records the instruction as the approval source and changes the status to `Approved` before code changes.

## Current active contracts

The [V5 Product Transformation](2026-09-23/01-v5-product-transformation.md) is the approved implementation contract for the V5-only site and operating path. It supersedes the narrower [V4-to-V5 site transition draft](2026-09-22/05-v4-to-v5-site-transition.md) where their release or public-history policies differ. The older contract remains as an audit record.

The [V5 replay and Preview rehearsal](2026-09-24/01-v5-replay-preview-rehearsal.md) is Implemented under the product transformation. It covered clean-code replay publication, Preview scoring and serving, and same-week V4 rollback with V5 restoration. It does not authorize the current-slate or production cutover.

The [V5 weekly operator and exact release gates](2026-09-24/02-v5-weekly-operator-and-release-gates.md) contract is Implemented (2026-09-25) under its approved production-role amendment: the exact dual-identity guard, Keychain production wrapper, restricted `cks_prod_pipeline` role, and production migration 0014 are verified, and a fixture-class Preview operator rehearsal exercised the full controller. No production V5 authorization or activation is approved, and the stabilized Week 4 finals gate remains.

The [Week 4 finals to live Preview evidence](2026-09-25/01-v5-week4-finals-to-live-preview.md) plan is Approved (user handoff, 2026-09-25). It sequences the existing 07→08→09→05 authority, Preview serving and rollback proof, and exact packet review after the finals gate. Execution awaits complete certified Week 4 finals plus the 24-hour stabilization interval; it authorizes no production V5 activation.

The [complete Week 4 replay site cutover](2026-09-25/02-v5-week4-replay-site-cutover.md) is Approved (2026-09-25) to show V5 for all 2026 Weeks 0–4, including scored retrospective Weeks 1–3 and a complete, truthfully labeled Week 4 replay. Its material release-policy amendment was approved with three decisions: V5-labeled history as the default view, parallel execution with the live plan (whose finals gates take precedence), and Week 4 replay grades against the frozen V4 pre-kickoff quotes (Amendment 1). It uses a separate exact production replay authorization path; each production release still requires its separate packet decision. It does not create a prospective V5 Week 4 run or supersede the approved live-forecast plan.

The [V5 current status guide](../modeling/v5_status.md) is the entry point for the accepted model, exact lineage, historical results, and remaining operational work. V5 model development is complete. V4 still serves the public site.

| Current contract | Purpose | State |
| --- | --- | --- |
| [V5 ratings publication and navigation](2026-09-26/03-v5-ratings-publication-and-navigation.md) | Publish verified ratings to production Neon, enable /ratings nav, link game cards, and document weekly cadence | Implemented |
| [V5 authority and cutover](2026-09-22/04-v5-authority-simplification-and-site-cutover.md) | Simplify authority and prepare a verified Preview serving rehearsal and rollback | In Progress; no production activation |
| [07: 2026 measurements](2026-09-18/07-v5-2026-repair-and-measurement-extension.md) | Repair and certify current 2026 football data | Verified through Week 3; Week 4 refresh awaits stabilized finals |
| [08: 2026 ratings](2026-09-18/08-v5-2026-rating-state-replay.md) | Replay the fixed V5 rating design on 2026 games | Verified through Week 3; Week 4 refresh awaits 07 |
| [09: live forecast](2026-09-18/09-v5-2026-forecast-and-readiness.md) | Apply and independently verify the fixed forecast to the next slate | Code ready; live apply awaits fresh 07/08 parents |
| [06: prospective monitoring](2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | Preserve pre-kickoff attempts, outcome reports, and quote diagnostics | Code ready; no eligible V5 slate yet; six slates are not a launch prerequisite |

The [V5 contract archive](../archive/v5-contracts/index.md) preserves completed and superseded methodology, audit, diagnostic, and code-readiness records. Historical contract statuses describe what happened at the time; the current guide and cutover contract govern what happens next. The unrelated V4 feature schema v5 diagnostic is archived with those records and is not the V5 ratings successor.

### Other active work

The [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md) retains the broader research context. The [production runbook](../ops/production_runbook.md) governs the currently active V4 weekly operation until an explicit V5 activation decision.

## When to use a contract

Use the Sol-to-Terra workflow for architecture, data/model lineage, schemas or migrations, production/deployment behavior, security-sensitive work, or changes that span multiple subsystems. Use the normal fast path for a small, localized change that follows an established pattern.

## Amendments and commits

Terra may append a minor amendment and continue only when it preserves architecture, public interfaces, scope, and acceptance criteria. A material conflict requires stopping and returning to Sol for a revised contract.

Record whether the plan should receive a separate commit. A separate plan commit is recommended for multi-session work, asynchronous review, migrations, production changes, or difficult-to-reverse decisions. Git operations remain user-controlled.
