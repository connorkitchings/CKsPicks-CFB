# Chart purpose, organization, and weekly data — Revision 5

- **Status:** Implemented — initial UI/report delivery. Owner selected both yardage metrics; the serving/publication follow-through is governed by the [October 18 expansion contract](../2026-10-18/01-charts-review-and-expansion.md).
- **Created:** 2026-10-16
- **Planner:** Sol
- **Approval source:** Owner's explicit “PLEASE IMPLEMENT THIS PLAN” request reproducing Revision 5 in the planning chat on 2026-10-16.
- **Implementation log:** `session_logs/2026-10-16/08-chart-purpose-implementation.md`
- **Commit policy:** Recommend separate plan commit; all staging, commits, integration and pushes remain owner-controlled. Implementation may begin on the approved uncommitted plan.

## Goal and acceptance

Deliver immediate chart UI improvements using existing release data and an offline comparison of explosiveness measures. Initial delivery is complete only when the independent UI changes pass validation and the real-data comparison report is ready for owner selection. Public explosiveness publication is a subsequent gated phase. Neither candidate's stability is established in advance.

Use PPA/play consistently in chart-facing titles, axes, tables, tooltips, exports, and methodology. Preserve internal `epa_*` identifiers and numerical calculations. CFBD calls its measure Predicted Points Added (https://collegefootballdata.com/exporter). Yards per successful play is not IsoPPP: IsoPPP measures points per successful play (https://www.footballstudyhall.com/2014/3/31/5563418/college-football-five-factors-statistics).

## Baseline and constraints

- Inspected clean `dev` and existing isolated chart worktree, both at `dddcf21e`. Reuse `.claude/worktrees/connorkitchings-charts-module` on `connorkitchings/charts-module`; preserve its ignored rehearsal artifacts. Primary checkout remains untouched.
- Current authority: `docs/status.md`, `docs/ops/weekly_runbook.md`, and the existing `01-charts-module.md` contract. Never copy live release IDs here. Preview has chart data; Production promotion is separate.
- Relevant components: `web/src/app/charts/page.tsx`, `web/src/components/charts/`, pure chart transforms/queries/tests, chart methodology, and new isolated research code/report. No serving/model/schema changes in initial delivery.
- Verify intended Preview R2 configuration before data reads without exposing secrets. Use the revision's immutable hash-pinned inputs, never repository-local `data/` or fresh unpinned ingestion.
- Existing scatterplots use dimmed outside-group points and transient search emphasis. Initial work replaces these behaviors without modifying forecast, rating, adjustment, grading, or release calculations.

## Ordered changes

### 1. Independent chart UI

| Chart | Purpose | Window | Controls |
| --- | --- | --- | --- |
| Did We Really Get Beat That Bad? | Compare winners' and losers' down-to-down success across games | Single week | Conference/group |
| Efficiency and PPA/play, pending selection | Compare team profiles across the national field | Season through week | Offense/defense, conference/group, one-team highlight |
| Opponent-adjusted PPA/play | Compare opponent- and venue-adjusted offense and defense | Season through week | Conference/group, one-team highlight |

- Retain existing chart URLs. Order controls as chart selection, week navigation, then chart-specific controls above the figure. Use Week N versus Through Week N accurately.
- Default to All FBS; retain published conferences and Power Four + Notre Dame.
- Remove excluded points/bars from SVGs, keyboard navigation, tables, and exports. A game qualifies when either team belongs to the selected group.
- Calculate scatter domains and play-weighted averages from the full eligible FBS population before filtering. Filtering/highlighting never changes them; week/side/metric changes do.
- Show national ranks for each plotted metric in scatter tables, computed before conference filtering. Competition ranks for ties; higher is better on offense, lower allowed is better on defense. No combined scatter rank.
- One persistent highlighted team, selected via searchable dropdown or logo click/tap; Enter/Space offers equivalent selection. Selecting the same team again or None clears it. Hover/focus tooltips do not change persistent highlight.
- Enlarge and label that marker; retain other qualifying teams. Clear selection when excluded by conference filter. Preserve selection across week changes; report unavailable observations if no point exists in the new window.
- Net success has no team finder or individual-game navigation. Preserve sorted bars, accepted logo spacing and contextual tooltips. Explain the winner's success-rate advantage/disadvantage in percentage points.
- Share scatter typography, grid, marker treatment, annotations and export composition. Subdued quadrant descriptions relative to FBS averages; adjusted PPA uses Better offense / Better defense and counterparts. Equal-net lines remain subdued with clearly labeled meaning. Annotations render behind markers.
- Export the filtered view with window, group, metric and highlighted team. Maintain mobile controls, keyboard/touch tooltips and accessible tables.
- Define PPA as CFBD Predicted Points Added averaged over eligible plays with valid PPA; document regulation, garbage-time and special-teams exclusions.

### 2. Offline explosiveness comparison

This task is independent of task 1. Use the Week 7 revision's exact hash-pinned Silver inputs and existing chart eligibility rules. Include completed eligible games before its active week, not Week 7 outcomes merely because this is the Week 7 revision.

- 20+ yard play rate = eligible plays gaining at least 20 yards / eligible plays with valid yardage.
- Yards per successful play = sum of yardage on eligible successful plays with valid yardage / count of those same plays. Never total offensive yardage divided by successes.
- Compute offense and defense-allowed versions for each available cumulative window from Through Week 2 onward. Retain independent denominators, finite observations, and nulls for zero exposure.
- Deliver paired plots, aggregate tables, source hashes, and a report in `docs/research/`. Generated datasets/images belong in ignored artifact storage outside repository-local `data/`.
- Evaluate coverage, distributions, rank movement, relationships with success rate/PPA, and sensitivity to removing each team-window's longest gain. Explain representative disagreements using counts and game context. These are descriptive comparisons, not evidence of predictive superiority.
- Owner records the selected metric/definition after reviewing evidence. Until then retain Efficiency and PPA/play publicly; no explosiveness label or toggle.

### 3. Weekly semantics and documentation

Team profiles pool numerators/denominators through the selected week; adjusted PPA reads the matching stored window. Keep Through Week 2 as the starting point. Explain historical windows as reconstructions from the active release, potentially reflecting later source corrections. Update chart methodology and the plan index as appropriate; live release/week state is unchanged by initial work.

### 4. Deferred serving/publication phase — do not execute before owner selection

Record selection and amend this contract before serving changes. Use an append-only migration and distinct `charts_v2` table set with an additive companion projection for the selected metric's per-team-game counts/sums. Keep existing `charts_v1` columns unchanged. Extend capability detection, queries, staging, verification/readback. Preserve retained `core_v1`/`charts_v1` checksums; nullable-column additions alone are insufficient because current readback hashes all payload columns.

Rehearse new serving data separately in Preview under the weekly runbook. Production migration/deployment/activation remains a separate owner decision. This future phase does not block completion of initial delivery.

## Validation

- Direct pinned-play formula checks: missing yardage/PPA, zero successes, zero explosive plays, unequal exposures, mirrored offense/defense observations. Earlier windows exclude later games.
- Unit/browser tests: actual filtering, either-team inclusion, fixed domains/averages, national competition ranks, dropdown/marker/keyboard highlight paths, transient tooltips, exclusion clearing and week-window unavailability.
- Table/export parity; visual inspection of dense national and small-group charts, desktop/mobile labels, keyboard/touch and PNG readability.
- Scoped chart unit/browser tests, web lint/typecheck/build, documentation checks and `git diff --check`. Use project tooling; no broad formatting.
- Later serving phase only: retained checksum/readback compatibility, new-metric reconciliation, unchanged forecasts/grades, Preview readback.

## Handoff/amendments

Approved for initial delivery by the owner's explicit implementation request. Fresh implementation chat uses repository-local implement-plan skill and this exact path. Mark In Progress and maintain the implementation log above. Delegate implementation per applicable `~/AGENTS.md`; preserve all unrelated work.

Material architecture/interface/scope/acceptance conflicts return for review. Mechanical amendments may proceed when those remain unchanged; record reason, previous/revised approach, and impact. Report initial delivery as Implemented only when its checks and real-data report pass; record the pending metric-selection gate explicitly. Owner controls all git publication.

### Implementation amendment — week navigation

The shared `WeekNav` arrow anchors caused full page navigation, clearing the required persistent team highlight. The arrows now use Next.js `Link` with disabled-link accessibility semantics; the existing dropdown already uses client navigation. This mechanical change preserves URLs, data windows, architecture and scope. Browser regression coverage verifies persistence through both arrow directions.

### Initial-delivery completion — 2026-10-16

Chart controls, actual group filtering, stable national reference values and per-axis ranks, persistent accessible highlighting, PPA terminology, filtered exports and responsive/keyboard/touch behavior are implemented. The [real pinned-data report](../../research/chart-explosiveness-comparison-2026-10-16.md) covers 329 eligible games, 40,461 eligible plays and 1,380 cumulative team-side-windows; four source hashes, 9,660 independent formula values and 658 offense/defense mirrors were verified. Generated plots/datasets remain in ignored artifact storage; prior rehearsal evidence is preserved.

Validation passed: 50 scoped Python tests; 186 web publication tests with one existing skip; 75 browser tests (24 focused chart/navigation); scoped Ruff; web lint (one preexisting warning), typecheck, fixture-mode production build; strict documentation build; visual inspection of national/small-group desktop/mobile charts and PNGs; `git diff --check`. Five focused review lenses found no blocking issue; one report range-rounding error was corrected against the generated CSV. Full evidence and the exact user-controlled commit allowlist are in the implementation log.

The public chart remains Efficiency and PPA/play. Owner selection and an amended contract are required before any `charts_v2` schema/serving work; Preview rehearsal and Production promotion retain their separate gates. No git staging, commits, integration, release activation or Production access occurred in this implementation.


### Owner selection and serving handoff — 2026-10-18

The owner selected **20+ yard rate** and **yards per successful play**, with a toggle, as recorded in `session_logs/2026-10-16/11-explosiveness-switcher.md`. The [expansion contract](../2026-10-18/01-charts-review-and-expansion.md) now authorizes the deferred companion `charts_v2` serving implementation and removes the intervening static research export. Its recovery completion plan was explicitly authorized by the owner on October 18. Initial-delivery history above remains unchanged. Local implementation does not complete the required Preview rehearsal, and neither contract authorizes Production promotion implicitly.
