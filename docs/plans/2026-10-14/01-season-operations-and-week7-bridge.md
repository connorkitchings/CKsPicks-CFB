# Simplify season operations without delaying the Week 7 bridge

- **Status:** In Progress
- **Created:** 2026-10-14 (America/New_York)
- **Planner:** Sol
- **Approval source:** Owner pasted the complete revised plan with “PLEASE IMPLEMENT THIS PLAN”, then directed “Let's document the full plan first and then get to work”. Implementation in this existing chat is explicitly authorized.
- **Planning log:** `session_logs/2026-10-14/01-season-operations-plan.md`
- **Implementation log:** `session_logs/2026-10-14/02-season-operations-implementation.md`
- **Commit policy:** Separate reviewed plan commit; operational pin/configuration and implementation commits remain user-controlled unless separately authorized. No automatic push, merge, or deployment authorization is inferred from this plan.

## Goal and acceptance

Deliver two phases: first show the already-graded Week 6 results and publish remaining-game Week 7 picks using ratings updated through complete Week 6 inputs; then install one chronological season workflow with atomic releases and automatic routine weekly operation.

The Week 7 bridge must not wait for the architecture replacement. Temporary Week 5 ratings are excluded. Target replacement readiness before Week 8, without turning architectural readiness into a reason to withhold otherwise valid picks.

Completion requires verified Production bridge serving, complete reconstructed historical results, accepted atomic-release cutover, and a subsequent weekly update through the same controller without repair contracts, component approvals, or freeze-history dependencies. Do not claim completion on code delivery alone.

## Baseline and constraints

- Primary checkout is clean `dev` at `c6ad76df8964d6e317d0de96f30da0a2363edc6c`, tracking `origin/dev`. The owner separately merged/pushed those contents to `main`, whose observed tip is `4a525f73`. Deployment identity and current serving state still require fresh verification.
- The prior worktree was removed. Use the new attached worktree `/Users/connorkitchings/.codex/worktrees/season-operations/ckspicks-cfb`, created from `dev`, for all edits. The user explicitly requested moving the primary checkout back to `dev`; that switch is complete.
- Task 4 r3 full verification passed at the committed baseline. Preview publication copied 39 objects plus root, and identical retry wrote zero objects. Its root embedded manifest checksum is `3aaecf61596ee6e31ef750579c657f7262cb617ef777ada75c3f92f125672e72`; raw root SHA-256 is `a85a210e9c88b3d22296bff0b37d74375f05a3eebb5dafda601ae26f2d201570`. Verify published bytes again before reuse. Old local staging disappeared with the removed worktree; recover immutable remote evidence rather than repeat experiments.
- Preserve the original 6A root, raw SHA-256 `9d218543eec7eda149bbb5ba446b5f73f33b8ae107d5a7da20bdbe00f8d007c3`. Its recorded build identity differs from later publisher/executable identity; never substitute one checksum or code identity for another.
- Recorded Production state has 58 Week 6 finals, 55 predicted games and 110 grades; spread 35-19-1, total 23-32-0. This is dated evidence, not a substitute for current readback. Full Weeks 0–6 scope currently expects 329 games, subject to refreshed canonical schedule reconciliation.
- R2 is the durable store. Check required credentials and explicit Preview/Production targets without exposing values. Never create a repository-root data fallback.
- Keep the accepted fixed model and numerical design. Earlier-week-only observations, observation availability, identity and score reconciliation, and complete required prior-week data remain mandatory.
- This contract replaces overlapping weekly/cutover requirements as the governing target. During Phase 1, existing numerical interfaces and exact Production/owner/rollback gates remain in effect; their unrelated repair obligations do not become bridge prerequisites.
- Phase 2 automatic Production operation starts only after separately approved initial migrations, grants, policy installation and cutover. The pipeline cannot enable or broaden its own policy. All rollback applies remain owner-authorized.
- Known structural risks: legacy stats/matchups are mutable and not release-qualified; stale cached evidence must not survive source changes; provider corrections can affect other teams' later opponent-adjusted states; physical document moves can invalidate retained pins.

## Ordered changes

### 1. Immediate bridge using existing infrastructure

1. Freshly verify Production selections, finals, grades, deployed revision and Preview repair outputs. Distinguish actual deployment from Git branch state.
2. Promote reviewed site changes that include the graded Week 6 display run in Results and Performance, under existing release authority. Verify deployed totals against database grades. Retain accurate 55-of-58 coverage; do not call this the full historical replacement. If already deployed and correct, record evidence and do not redeploy solely to repeat this step.
3. Reuse the published Task 4 r3 package. Do not repeat attribution, baseline capture, catalog recovery or historical model fitting.
4. Complete remaining Week 6 frames and corrected rating generation through all 58 games. Require complete finals and required plays/drives before Week 7 ratings. Reuse existing verified historical foundations and sealed model design.
5. Capture fresh lines, reconcile the current FBS schedule and forecast only still-unstarted games using post-Week-6 states. Recheck schedule eligibility immediately before activation.
6. Verify forecasts, serving data, ratings, stats and matchup bindings in Preview; present concrete Production evidence and execute the existing release pathway after exact approval and user-run prerequisites.
7. Update serving status only after verified publication. Historical replacement, unrelated backfills and new release-pointer tables are not required to close Phase 1.

### 2. One model and one chronological season workflow

Introduce `scripts/pipeline/run_season.py` with `prepare`, `status`, `release` and `rollback`. Preparation supports historical reconstruction through a completed week and ordinary refresh; durable checkpoints allow resume. Historical and recurring paths share computational stages.

- Seal accepted numerical design, parameters, priors, historical inputs and bridge in one model manifest. Import verified repaired inputs without repeating historical fitting or experiments.
- Create one immutable season-data revision containing schedule, finals, normalized plays/drives, football measurements, scoring events and market references.
- Replace repair-run-specific forecasting adapters with direct model/revision inputs. Reuse existing measurement, opponent-adjustment, rating, offset, prediction and scoring functions.
- At each week, predict from a pre-week cutoff using only available earlier-week observations; grade completed games, then compute post-week state for the next week. Current-season results never refit model parameters; markets never enter football features.
- Require every scheduled non-cancelled prior-week game to have final scores and required play/drive data. Validate identity, duplication, teams, stream completeness and score reconciliation. Missing required inputs block advancement. Accepted nullable metrics follow the fixed model's existing rules.
- Reconstruct full slates, including started games. Preserve actual capture times and identify reconstructed outputs without fabricating freeze receipts.
- Provider corrections create a new revision, a concise correction report and rebuilt affected history. Initially replay the full current season deterministically; cache unchanged normalization/measurement work rather than implement narrow team-only invalidation.
- Keep raw captures, canonical inputs and final outputs checksummed in R2. Intermediate aggregations are rebuildable caches. Catalog registration and reconciliation scans are optional indexing/maintenance rather than release prerequisites.
- Reuse durable state-machine infrastructure for resume, concurrency, progress and failure recording. Retire the separate component-by-component controller from recurring operation.
- Produce one verification report bound to model, code/configuration, source revision, outputs, scope and grading policy. Evidence is reusable only when all identities match. Verify checksums at actual read boundaries and retain lightweight transactional concurrency/before-state checks.

Historical market precedence is applied independently per game and target:
1. Use verified retained pre-kickoff captures when eligible captures exist.
2. Otherwise use CFBD historical lines as an explicitly retrospective benchmark.
3. Otherwise retain predictions/finals and leave that target ungraded.

Keep existing consensus-first model direction and best-quote selection within the chosen source set. Retain source, capture time and benchmark type; historical CFBD fields are not called verified closing lines.

### 3. Fixed-schema atomic releases

Define additive schema and grants in `contracts/schema.sql` and append-only migrations; synchronize canonical TypeScript/Python/web contracts. Use fixed table names and typed Drizzle queries, never dynamic per-release table names.

- Add `season_releases` with release identity, environment, season, model/source/run manifest hashes and references, verification reference, active week, creation time and status (`staged`, `active`, `superseded`, `rolled_back`).
- Enforce at most one active release per environment/season using a unique partial index. The active row is the pointer; do not maintain a second independent pointer.
- Add fixed release-scoped projections mirroring existing serving contracts for schedule, finals, grades, ratings, team stats, matchup measurements/components and week selections. Include `release_id` in keys; reuse immutable prediction runs when bytes match.
- Stage complete projections without changing the active site. Activation locks the season, checks expected prior release, policy, candidate verification and staged readback, atomically changes statuses and appends activation history.
- Preserve frontend response types and page structure. A shared request release context resolves once and filters every query consistently. Cache keys include release identity; invalidate affected pages after activation.
- Rollback reactivates retained prior projections across all views and deletes no rows/artifacts.
- Replace new per-layer authorizations with one owner-configured automatic-release policy bound to approved model, workflow version, environment and grading policy. Pipeline roles cannot enable or broaden it.
- Automatically prepare/rehearse Preview and activate the matching Production candidate only after checks. Initial migration, grants, policy installation and cutover remain owner-controlled.
- Preserve legacy schemas, authorization rows and genuine historical receipts through migration. Archive obsolete activation paths after accepted cutover and rollback rehearsal.

### 4. Documentation consolidation and rollout

Make `docs/ops/weekly_runbook.md` the sole recurring operational authority: refresh completed data → validate completeness → rebuild ratings/predictions/results → rehearse Preview → activate and verify.

- Supersede overlapping repair, fallback, cutover and freeze-dependent operating contracts. Move attribution experiments, legacy comparisons, catalog recovery and unrelated backfills to historical evidence or separate backlog, without falsely marking unfinished obligations implemented.
- Retain concise active model semantics, methodology, architecture, serving status and quality guidance; correct stale serving/stabilization claims.
- Archive completed/superseded operational documents after checking links, executable references and artifact pins. Preserve referenced bytes/paths where moving them would break retained evidence. Keep active independent research outside weekly authority.
- Update repository instructions, command help and navigation.
- Build the replacement alongside the bridge. Reconstruct complete Weeks 0–6 and Week 7 outputs; incorporate Week 7 finals/observations only when complete.
- Reconcile expected 329 historical games against fresh schedule; verify finals, predictions, available grades, ratings and matchup data before cutover.
- Target Week 8 readiness. If it slips, retain the validated existing publication pathway rather than block valid picks on architecture completion.

## Validation

- Bridge: complete Week 6 required inputs; future-game eligibility; live-state bindings; Preview readback; deployed Week 6 totals; Production Week 7 pages.
- Fixed-model numerical parity on identical measurements, offsets, ratings and forecast inputs. Explain grading differences attributable to the approved historical fallback.
- Completeness/leakage: missing plays/drives, cancellations, duplicates/conflicts, score reconciliation, nullable metrics, missing lines, earlier-week-only observations, availability cutoffs, no market features and full late-opened reconstruction.
- Revision/resume: deterministic unchanged inputs, historical correction propagation, checkpoint recovery and stale-report invalidation.
- Releases: invisible staging, concurrent activation refusal, wrong environment/model/policy, expected-prior mismatch, request-wide release consistency and all-view rollback parity.
- Measure cold reconstruction and warm preparation separately from provider capture. Target warm preparation within 15 minutes, profile/cache expensive work, and report actual performance without introducing an arbitrary time gate that withholds correct picks.
- Run affected tests, full Python checks, schema synchronization, web lint/typecheck/build, documentation checks and actual Preview browser/database verification. Preserve the already-approved Ruff exclusion for retained Week 6 capture evidence. Do not broad-format unrelated files.
- Run `git diff --check` and `uv run mkdocs build --quiet` for plan/log persistence.
- Acceptance requires verified Production cutover and a subsequent weekly update through the same controller. Neither planning approval nor passing local tests claims deployed success.

## Handoff/amendments

The owner explicitly authorizes implementation in this chat; no fresh-chat requirement is imposed. Persist and validate this complete plan first. Then mark In Progress, create the implementation log, delegate bounded code work per repository instructions, and begin fresh bridge readback.

Keep a TODO list in the implementation log: (1) plan persistence/validation; (2) bridge readback/deployment; (3) Week 6 frames/ratings; (4) Week 7 Preview and exact Production gate; (5) season runner; (6) atomic schema/readers/publisher; (7) documentation cleanup; (8) migration/cutover/next-week proof.

Present the concrete reviewed plan commit and operational configuration commits at their clean-code gates. A material conflict stops affected operations and returns for decision; continue independent authorized work where possible. Mechanical amendments require unchanged architecture, interfaces, scope and acceptance, recording reason, prior/revised approach and impact.

### Owner-authorized local commit and integration

After the reviewed plan/configuration, successful checks and clean-code prerequisite were presented, the owner replied “Authorized. Let’s proceed”. This authorizes two local commits (plan, then configuration/evidence) and fast-forward integration into dev. No push, deployment, Production write or rollback apply is authorized by this answer.
