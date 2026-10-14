# Task 4 Baseline Enforcement and Week 7 Display-Only Continuation

- **Status:** In Progress
- **Created:** 2026-10-13 (America/New_York)
- **Planner:** Sol
- **Approval source:** Owner's “Strongly Approve” response to the continuation plan in this chat, including the three operational guardrails; subsequent “proceed” authorizes persistence.
- **Planning log:** `session_logs/2026-10-13/04-task4-week7-continuation-planning.md`
- **Implementation log:** `session_logs/2026-10-13/05-task4-week7-continuation-implementation.md`
- **Commit policy:** Separate user-controlled plan commit; implementation and operational pin/lock commits remain user-controlled. Do not commit, merge, or push automatically.

## Goal and acceptance

Complete the missing Task 4 baseline derivation and enforcement, publish verified Task 4 r2 and five-stage 6B Week 6 frames in Preview, build Week 7 ratings corrected through Week 6, and prepare and rehearse the Week 7 display-only release. Production execution proceeds only after an exact owner P0 decision and user-run prerequisites.

Success requires a captured, hash-pinned baseline; exactly 276 declared new component IDs and 114 measurement game IDs; retained comparison of all 508 published Week 6 components; passing attribution, comparison and receipt stages; exactly 16 evidenced `cutoff_utc` cells across the four approved games; complete catalog readback; published hash readback and zero-write identical retry; 329-game 6B coverage including all 58 Week 6 games; verified post-Week-6 live rating provenance; and passing Preview release readback and owner-approved pointer rollback/reapply evidence. Do not mark this continuation Implemented while required release or rehearsal gates remain unmet.

## Baseline and constraints

- Inspected local `dev`: clean at `690f42ca`, 32 commits ahead of `origin/dev`. Phases 0–1 are complete. Worker worktrees `aa0b6eff0b3d126d5` and `addd03730b548ca0f` contain no delivered baseline-enforcement commits or uncommitted changes.
- Existing [Task 4 repair contract](02-task4-verification-and-catalog-repair.md) remains authoritative for its five repair steps; this continuation adds missing enforcement and execution ordering without relaxing acceptance. [Repair-track Amendment 16](../2026-10-08/02-repair-track-certification-and-closure.md#amendment-16--2026-10-13-week-7-ratings-decision-display-only-release-and-live-rating-provenance) governs corrected-through-Week-6 ratings and display-only posture.
- Owner reports catalog recovery registered 49/49 versions, identical retry wrote zero rows, and root bytes remained unchanged. Independently verify this report before deriving additions, capturing the baseline, or executing Task 4 r2.
- Preserve the published 11-stage 6A root (raw SHA-256 `9d218543eec7eda149bbb5ba446b5f73f33b8ae107d5a7da20bdbe00f8d007c3`), failed Task 4 r1, and invalid-lock archives. Do not rebuild or overwrite this evidence.
- Storage backend is R2; source and Preview credential variable presence was checked without printing secrets. Verify the actual task target before cloud I/O. Never create a repository-root data fallback.
- Baseline capture currently reads `DATABASE_URL`, but `with_preview_env.sh` supplies the migrator there and the pipeline role in `PREVIEW_DATABASE_URL`. Comparison already uses Preview runtime resolution and a read-only repeatable-read transaction. Correct the CLI rather than changing the wrapper's authorizer credentials.
- Live provenance separation already exists on `dev`. Include the forecast builder and serving verifier in the delegate's inspection/test scope; change them only to repair an evidenced remaining gap.
- Week 7 stays `display_only=true`, `published`/`pending`, never frozen. Historical Weeks 0–6 cutover, Advance-Mode producer integration, Week 8 predecessor policy and other original Phase 6 work are deferred.
- The pasted execution plan authorizes Preview Phases 2–5 automatically after successful checks. This specific owner instruction supersedes older wording requiring separate permission for each Preview write. Stop on any failed check, hash/count discrepancy, user-run Production step, exact P0 Production release decision, or rollback apply. No Production writes are authorized by this contract alone.
- Pointer-only rollback is the owner-selected scope: restore selections and `current_week` using the existing tool; retain stats and rating snapshots. Compare only restored scopes and explicitly account for retained data and expected audit-history effects. No release-receipt producer is required for this scope.

## Ordered changes

### 1. Missing worker implementation and quality gates

Delegate code work in an isolated worktree based on the reconciled `dev` HEAD. The worker implements directly without further delegation.

1. Add `--derive-component-additions --plan <yaml> --out <json>` to `capture_task4_w6_comparison_baseline.py`, mutually exclusive with existing capture/verify modes. Read published 6A artifacts through the same hash checks and reuse Task 4's component payload-building logic. Derivation must not require the unfinished baseline pin, bypass checks on other required inputs, write R2/catalog data, or create intermediate rebuild stage artifacts.
2. Against one verified pipeline-role read-only repeatable-read Preview snapshot, derive new component IDs from reconstructed versus published keys. Require exactly 276 unique IDs in the declared new as-of-week scope, reject missing published components and unexpected scope, and keep all 508 published Week 6 components under comparison. Use exclusive creation for the sorted JSON ID list at `conf/rebuild/task4_w6_component_additions_v1.json`; bind its bytes/hash as the baseline declaration source. A difference set alone is not permission to admit an unexpected key.
3. Share fingerprint/declaration logic between capture and comparison through importable rebuild code. Resolve capture through `PREVIEW_DATABASE_URL` and assert the pipeline identity; do not fall back to migrator credentials. Retain target assertions and read-only transactions.
4. In `published_comparison.build`, read and validate the pinned baseline, capture canonical table fingerprints and rating publication metadata in the same transaction as comparison rows, and reject drift. Call `check_additions` for the declared measurement and component populations. Preserve separately justified existing population rules for other tables; do not silently impose a new rule that suppresses or reclassifies previously documented differences.
5. Record baseline SHA, fingerprint/declaration check results and exact populations in the report. Verification must reject absent/failed enforcement evidence and independently recapture current Preview fingerprints before acceptance; capture timestamps themselves do not constitute content drift.
6. Inspect and verify forecast provenance: replay uses `replace_2026_ratings()` with `#pregame:<game_id>` references; live preserves `live_features` from `current_teams`, skips that replacement, and uses the existing full `rating:<rating_sha>#current:<current_teams_raw_sha256>/<team>` references. Require serving verification to recompute and check this binding. Do not duplicate the merged implementation or regress replay output.
7. Correct the fallback's authorizer instructions to supply both `--approval-decision-ref` and `--decision-ref`, with their distinct existing semantics. Correct stale rollback-tool availability/scope descriptions and obsolete freeze instructions in the active continuation steps.
8. Review implementation using the repository code-review workflow, run focused tests and full quality gates, then present the diff and proposed commit for the user-controlled merge/commit. Operational commands wait for a clean committed baseline.

### 2. Task 4 r2 in Preview

1. Execute a read-only catalog readback against Preview Neon and the retained published root. Require all 49 dataset versions and every expected catalog field to match, and independently hash the root bytes. Use the existing recovery dry-run path where suitable; do not repeat recovery writes solely to reconstruct evidence. For `recover_6a_catalog.py`, `--expected-code-sha` binds the root's recorded `code_sha` (`2147c5fb…`), while the recovery executable HEAD is recorded separately. This is the root's recorded code identity, not the different stage-build identity.
2. Only after this passes, derive the component IDs, capture `conf/rebuild/task4_w6_comparison_baseline_v1.json`, and replace the all-zero raw SHA pin in `conf/rebuild/6a_task4_w6_v2.yaml`. Commit declarations and pins through the user's git workflow.
3. From clean committed HEAD, run `rebuild_6a.py` preflight, build and verify for the r2 YAML with each command's documented HEAD-binding arguments. Require all three stages, both rating controls, exact additions and exactly 16 evidenced timestamp cells to pass. The approved games are `401862787`, `401862797`, `401856827`, `401856808`.
4. Dry-run `publish_6a.py`, apply, independently read back every published hash and prove identical retry writes zero rows. Record raw root/receipt hashes and embedded manifest checksums distinctly. Preserve r1 and the original 6A root.

### 3. Week 6 frames, locks and Week 7 live ratings

1. Create `conf/rebuild/6b_w6_v1.yaml` from the existing five-stage frames template, using an exclusive new run identity. Bind the unchanged 6A root, published Task 4 root and receipt, Week 6 source lock/parents, and served Weeks 0–5 refs by their correct raw/embedded hash semantics. Require week counts 8/43/49/57/58/56/58, totaling 329 games.
2. Set `cutoff_2026` equal to the Task 4 receipt cutoff. Separately set `unserved_week_as_of['6']` to the pinned post-Week-5 pregame cutoff, proving it is after Week 5's last kickoff and before Week 6's first kickoff. Do not use the post-Week-6 finals cutoff for that field.
3. Commit the configured plan, then run the five-stage 6B preflight/build/verify/publish and independent hash readback. Do not add the served-population-only market/finals/grading stages.
4. Generate successor and Week 7 live locks with explicit Week 6 flags, newly verified Task 4/6B roots and the matching parents. Preserve invalid archives; commit valid locks before dependent operations.
5. Build and verify the Week 7 live rating with existing preflight/apply evidence interfaces. Require post-Week-6 observations for all 58 Week 6 games and the unchanged sealed design. Verify every downstream parent hash.

### 4. Week 7 candidate and Preview rehearsal

1. Follow the full [weekly operator checklist](../../ops/v5_weekly_operator.md#weekly-close-open-and-freeze-checklist) as applicable to display-only publication. Reconcile the fresh complete FBS schedule and spread/total source coverage; retain capture time, missing IDs, next refresh and exact gates.
2. Choose timezone-aware `live_as_of` after capture. Calculate omitted IDs strictly from kickoff at or before that cutoff. The earlier handoff's two started games and 57 remaining games are historical context, not a fixed expected population; require equality to the fresh schedule-derived set.
3. Build forecasts, serving artifacts, verify and package using the corrected Week 7 rating and existing display-only interfaces. Require exact live `current_teams` hash bindings and replay provenance preservation.
4. Export Preview before-state; authorize with split decision flags; seed exactly the FBS slate; publish required missing venues, ratings and as-of-7 stats with readback. Require historical stats scopes unchanged; inspect and verify legitimate new as-of-7 rows rather than requiring a zero-difference result for a previously absent scope.
5. Publish and select the packaged run with existing freshness guards: candidate age strictly less than six hours, nonfuture cutoff, predicted set equal to schedule-after-cutoff, and every included kickoff later than database now. A stale candidate requires fresh capture and new candidate evidence; never waive the guard.
6. Publish/verify the matchup bridge and data with exact payload hashes. Read back Preview routes, current pointers, coverage, ratings and stats. Require Weeks 0–6 selections unchanged and a visible display-only posture.
7. Prepare and review the existing pointer-only rollback dry run under the owner/migrator role. Pause before rollback apply. After explicit owner approval, apply and verify restored pointers against the retained before-state, accounting for retained stats/snapshots and audit history. Reapply publication/selection/matchup steps only if all current freshness and readback gates still pass; otherwise stop with the stale-candidate evidence.

### 5. Production boundary and closeout

1. Present the exact Preview candidate/evidence for P0. Do not write Production before the owner approves that candidate.
2. Pause for user-run Production Silver catalog promotion, artifact staging and owner authorization SQL; independently verify their receipts and chain bindings before dependent operations. No SQL or staging operation is transferred to the agent by this plan.
3. After exact authorization, export Production before-state and execute the approved schedule/venues/ratings/stats, publish/select and matchup operations with freshness checks, expected Preview hashes, scoped readback and live route/display-only checks. Any Production rollback remains separately approved.
4. Update the original Task 4 contract and plans index only when its acceptance is met. Update `docs/status.md` only when serving state changes; record actual selected identity, omitted population and capture timestamp there without duplicating live run IDs in other status docs. Maintain the implementation log throughout. Leave Phase 6 deferred.

## Validation

- Focused tests: deterministic derivation without baseline/stage output; wrong count/scope; duplicates; missing published rows; published Week 6 rows incorrectly called additions; undeclared extras and unused declarations; baseline hash/schema rejection; table/publication drift at build and verify; refusal of missing enforcement report fields; verified pipeline-role use and wrong-role refusal; 114 measurement game IDs; the four-games/16-cells boundary; replay/live provenance and altered current-state hashes.
- Full code gates after worker integration: `make test`, `make lint`, `uv run ruff format --check .`, `git diff --check`. No broad rewriting formatter. The owner's previous 2,827 passed/30 skipped report is baseline context, not a substitute for new checks.
- Operational gates: 49 matching catalog versions and immutable root; exact addition populations; complete stage verification; published hash readback and zero-write retry; 329-game 6B coverage and distinct cutoff validation; 58-game Week 6 observation coverage; dynamic FBS forecast population and current freshness; Preview serving readback and owner-approved pointer rollback/reapply.
- Documentation persistence: `git diff --check` and `uv run mkdocs build --quiet`. Record any existing documentation warnings without treating unrelated warnings as new correctness evidence.

## Handoff/amendments

This planning session may save only this contract, planning log and contract-index entry. Implementation starts in a fresh Terra chat using the repository-local `implement-plan` skill with this exact path:

`docs/plans/2026-10-13/03-task4-baseline-and-week7-display-continuation.md`

The owner has approved the contract content and automatic Preview progression within the stated gates. Start by reconciling the clean committed `dev` baseline and delegating the missing worker implementation. Do not repeat completed Phases 0–1 or claim unverified cloud state.

Mechanical amendments may proceed only while architecture, interfaces, scope and acceptance remain intact. Record the reason, previous approach, revised approach and impact. Material conflicts return to Sol; any failed check or unexpected hash/count stops the dependent operation. P0, user-run Production prerequisites and rollback apply always remain explicit owner gates.

### Implementation reconciliation — 2026-10-13

The owner explicitly invoked `implement-plan` for this exact contract and authorized implementation in the existing chat. This later direction authorizes continuing here rather than requiring a fresh chat. The contract and planning files are present only as uncommitted changes in the attached managed worktree; root `dev` remains clean at `690f42ca`. Implementation reuses that isolated worktree, preserves the planning files, and still waits for user-controlled commit/integration before clean-HEAD operational commands. No commit policy or release gate changes.

### Section 1 execution checkpoint — 2026-10-13

Section 1 code/tests/documentation are delivered and reviewed in the isolated worktree. Focused validation: 113 passed; full project suite: 2,858 passed, 30 skipped. Independent pipeline-role catalog readback confirms 49 matching versions, 366 dependencies, 220 quality rows and unchanged root bytes. Changed-code lint/format, documentation build and diff checks pass. No derivation/capture, pin/lock changes or operational writes occurred.

The exact full-repository Ruff gates expose 33 pre-existing lint findings and 10 formatting failures in retained Week 6 capture-tools evidence, reproduced against original `dev`. The owner has been asked to approve an exclusion limited to `docs/plans/2026-10-11/week6-closeout-evidence/**/capture-tools/**` or retain the exact gate pending separate resolution; no answer is assumed. Diagnostic lint/format commands with that proposed exclusion pass, but validation requirements remain unchanged until a decision is recorded. User-controlled plan/code commit and integration remain a separate prerequisite for clean-HEAD operations. Contract stays In Progress.

### Approved amendment — retained Week 6 capture-tools exclusion

**Approval source:** Owner's explicit answer to the validation-scope question: “Approve an explicit exclusion for the retained Week 6 capture-tools evidence directory; lint and format-check everything else.”

**Reason and previous approach:** Exact repository-wide Ruff commands included unchanged historical capture-tools evidence, exposing 33 existing lint findings and 10 formatting failures. Broadly rewriting those retained scripts was outside this continuation.

**Revised approach:** Add only `docs/plans/2026-10-11/week6-closeout-evidence/**/capture-tools/**` to `[tool.ruff].extend-exclude` in `pyproject.toml`. Existing `force-exclude = true` applies the same narrowly approved exclusion to lint and format checks, including explicit-path invocations. Execute the original `make lint` and `uv run ruff format --check .` commands without ad hoc CLI exclusions; everything else remains checked.

**Impact:** Historical evidence bytes stay unchanged. This resolves the validation-scope conflict only; there is no forecasting, storage, database, publication, rollback or git-policy change. The prior pending Ruff decision is superseded by this recorded approval. Clean user-controlled plan/code commits remain required before operational execution. Contract stays In Progress until all operational acceptance is met.

### Local commit/integration authorization — 2026-10-13

After the reviewed diff, passing checks and manual commit/integration gate were presented, the owner replied “proceed” to the stated next steps. This authorizes the two reviewed local plan/implementation commits and fast-forward integration into `dev` for this handoff. No push, Production action or rollback apply is authorized. Operational baseline/pin changes will be presented after derivation/capture, with their next clean-HEAD gate preserved.
