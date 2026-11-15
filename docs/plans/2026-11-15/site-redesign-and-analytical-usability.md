# Stratum CFB: site redesign and analytical usability

- **Status:** In Progress
- **Created:** 2026-11-15
- **Planner:** Sol
- **Approval source:** Owner approved the complete conversational plan and explicitly instructed “Please implement the plan.” on 2026-11-15.
- **Implementation log:** `session_logs/2026-11-15/02-site-redesign.md`
- **Commit policy:** Separate planning commit, then bounded implementation commits; merge into local dev after validation. No push or deployment authorization.
- **Baseline:** local dev `5dec23f9`; isolated worktree `codex/site-redesign`.

## Goal and acceptance

Redesign the site around balanced football analysis: understand games, assess teams, explore statistics, and evaluate the model. The approved direction is editorial analytics and primary navigation Games / Teams / Graphs / Model. Preserve Stratum branding, team identities, light/dark themes, and existing model/publication safeguards.

Stage 1 implements every work package below using existing certified serving data. Completion requires every acceptance item, focused tests, `make check`, `make web-e2e`, `git diff --check`, representative browser inspection, and real Preview verification of changed optional-table reads. Stage 2 is a separate future contract, not implementation scope.

## Baseline and constraints

- Read queries and presentation models may change; forecasts, grading, ingestion, database schemas and release projections do not.
- Keep all new reads scoped to the resolved release and exact relevant period. Never fill absent active-release data from unrelated legacy generations.
- Preserve publication mode, matchup availability, historical lineage and export gates, including all summaries and new charts.
- Do not add public forecast ranges, confidence scores, model changes, new data coverage, custom gesture inspectors, accounts or favorites.
- Owner selected an unscheduled explicit start instead of the previous summer-only window, and has now authorized this implementation. Deployment and data operations remain separate.
- Live release IDs and week state remain exclusively in `docs/status.md`. Do not alter other sessions' model research.

## Ordered changes

### 1. Shared design and navigation

- Use an editorial hierarchy: page title/purpose, compact data context, primary analysis, supporting detail. Preserve semantic colors/fonts; increase section whitespace, reduce nested cards, use restrained borders and stronger typography.
- Standardize primary width at 1,200px; explanatory prose about 760px; phone gutters 16px and desktop 24px.
- Retain four-item phone bottom navigation. Desktop uses unified brand/navigation header with team search, season selection and theme control.
- Create `/teams` index. Permanently redirect `/ratings` preserving query parameters. Keep team-profile, matchup, graph and model URLs.
- Add accessible global canonical-team search opening profiles, without external search services.
- Standardize section headers, metric descriptions, data-context rows, empty states and chart detail panels.
- Reserve win/loss colors for outcomes. Neutral styling for schedule difficulty and model-market differences, without green confidence-like edge tiers.
- Acceptance: consistent navigation, spacing, terminology and themes; old deep links resolve.

### 2. Availability, freshness and interpretation

- Default Graphs to Efficiency vs explosiveness. Explicit unavailable-chart links stay on that chart, with explanation and available alternatives.
- Replace raw-ID exclusions with coverage counts and expandable human reasons. Never silently substitute periods, populations or formulas.
- Distinguish data release activated, forecast updated, line captured and statistics through, using only authoritative source timestamps.
- Expose capture times for exact selected spread/total quotes; unknown remains unknown, never replaced by forecast time.
- Explain publication cadence without claiming a live feed or exact schedule freshness.
- Post-week labels are Through Week N, with Preseason or cutoff-date fallback when appropriate.
- Put units, adjustment status, population and proper denominators close to analysis; full definitions expandable.
- Replace finishing-drives touchdown/field-goal claims with descriptions of actual axes.
- Correct methodology that conflates historical study with operational verification; do not publish the separate session's evolving research.

### 3. Games and matchup

Games:

- Today / Upcoming / Results / All. Default Today if selected week contains today's ET games; otherwise Upcoming if any; otherwise Results if all final; otherwise All. Explicit URL selection overrides. Historical-week navigation opens All; Today is relative ET date.
- Preserve current upcoming/final/awaiting semantics. Awaiting published results count links to affected games; never label them live.
- Retain card/list presentations with clear teams, schedule/status, forecast, selected quote, explicitly labeled difference in points.
- Replace Model Bet with Model lean and unexplained differences/confidence-toned edge tiers with neutral explicit point differences.
- Add Model vs market view from market-board foundation, separate spread/total controls, internally normalize spread to home margin, explicitly label teams.
- Persist week, search, conference, sort, presentation and status in URL.

Matchups:

- Order: teams/kickoff or final/forecast/market; up to three What stands out facts; offense-versus-defense; compact rating evidence; expandable full stats/breakdown; Share matchup.
- Facts are deterministic templates from forecast-line difference, unit ranks and verified raw-to-adjusted evidence. No generated narrative or suggestion that context metrics are model inputs.
- One away-offense/home-offense selector controls comparisons, supporting factors and exports. Remove aggregate Key Factors winner verdict; retain individual values/ranks.
- Raw-to-adjusted PPP visual uses validated rating components, exposure and prior contribution. Preserve unavailable/lineage-updating states.
- Completed matchups retain frozen pregame evidence and show forecast versus final outcome; actual-game statistical breakdown is Stage 2.

### 4. Teams hub and profiles

- `/teams` has Rankings / Trends / Strength vs résumé / Compare, all with one exact certified period.
- Rankings has Strength (overall/offense/defense/weekly rating change/rank movement) and Résumé & schedule (FBS record/SOR/WAA/SOS) groups.
- National competition ranks computed before filters/sorting. Ties share ranks; sort never changes rank; nulls last.
- Weekly movement requires immediately preceding certified post-week, otherwise unavailable.
- Trends: Overall / Offense / Defense and Rating / Rank; max two teams; missing periods break lines; rating scale explained.
- Strength vs résumé: overall rating x, SOR rank y strongest at top; eligible coverage, no synthetic missing SOR.
- Compare: two replaceable/clearable team slots, shared period, strength/résumé/schedule and chosen component trajectory; no composite winner.
- National ranks and references independent of conference/search.
- Profiles: section navigation, component trends, linked opponents, Compare action, validated raw-adjusted explanation for displayed snapshot.

### 5. Graph exploration

- Football measurements in Graphs; trajectories/résumé in Teams; market board in Games.
- Scatter selection opens persistent values/units/national ranks/exposure panel with profile, next-matchup when available and Compare links.
- One selected plus optional second comparison team, same conventions throughout.
- Sortable table uses same filtered population/values as chart.
- Retain filtered-out selection in controls with explicit notice.
- URL restores chart/week/period/side/metric/conference/team selections on reload/back/forward.
- Exports include period, filters, population, units and legend. No custom zoom/gesture inspector.

### 6. Model assessment

- Order: separate target records; paired model-market accuracy; trends/error exploration; recent weekly results/archive; methodology/limits.
- Remove pooled normal-luck wording. Separate sample sizes and labeled 52.4% reference, no new significance claims.
- Target-selectable error scatter: market absolute error x, model absolute error y, equal-error diagonal; below model closer, above market closer.
- Reuse existing paired eligibility exactly; selected game shows forecast/retained line/actual/errors/matchup link; sortable table equivalent.
- Latest four weekly summaries initially; full archive expandable.

### Interfaces and safeguards

- Rating history preserves snapshot/source/cutoff/certified post-week. Never join generations solely on week or include future periods.
- Carry selected target quote capture timestamps through existing selection joins and page types.
- Chart metadata explicitly defines units/direction/population/denominators, separately per axis if necessary.
- Expose existing eligible paired errors as minimal client model.
- Preserve query parameter meanings, add view/compare/status where needed; normalize invalid values safely without expanding publication access.

## Validation

- Unit tests: ranks/ties/reversed sorting/filters; missing previous/intermediate weeks; same-week source generations; ET midnight/DST/TBD; partial finals/awaiting-only/historical/empty results; quote identity/timestamp nullability; paired eligibility, pushes, missing targets, sign conventions and retrospective exclusions.
- Integration/browser: shared matchup side across panels/resizing/exports; all publication/lineage gates; chart/table values/denominators; missing optional projections/null SOR/evidence; URL reload/back/forward and redirects.
- Accessibility/visual: keyboard/focus, chart tables, reduced motion, both themes, widths 320/390/tablet/desktop; populated, empty, unavailable and historical pages.
- Real Preview read checks for changed optional-table queries; fixtures cannot substitute for this gate.
- Final: `make check`, `make web-e2e`, `git diff --check`; docs/session log and explicit evidence. No deployment in this scope.

## Handoff and amendments

Stage 2 separately covers turnovers, pace, scoring composition, actual postgame breakdowns, authoritative schedule freshness and new projections/backfill. Predictive ranges wait for the model audit. Do not imply these capabilities exist.

Implementation now authorized by owner's explicit instruction. Commit bounded completed work locally, preserve unrelated work, merge into local dev after verification, never push without the separate owner instruction. Mechanical amendments may proceed only without changing architecture/interfaces/scope/acceptance; material conflicts return for review.

### Execution checklist

Continuation approval: the owner explicitly approved the seven-step “Continue the Stratum site redesign” execution plan and instructed implementation. Resume in the existing worktree, finishing shared design, Games/matchups, Teams/profiles, Graphs, then Model sequentially. Each bounded slice needs focused verification before its local commit; final review and all original acceptance gates precede integration into local dev. Preserve concurrent model research. The product scope above remains authoritative.

- [x] Shared design/navigation
- [x] Availability/freshness/interpretation
- [x] Games/matchups
- [x] Teams hub/profiles
- [x] Graph exploration
- [x] Model assessment
- [x] Final gates (`make check`, `make web-e2e` 436 passed / 10 skipped, `git diff --check`), browser inspection at 320/390/820/1280 in both themes (no overflow, no console errors), documentation, local integration
- [ ] Open before marking Implemented: Preview verification of the application code paths (only equivalent read-only SQL was run), and the selected-quote capture time on Model rows (`MarketGame` has no such field)
