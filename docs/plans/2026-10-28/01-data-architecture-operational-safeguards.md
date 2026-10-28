# Data architecture Stage 1: operational safeguards and baseline

- **Status:** Draft
- **Created:** 2026-10-28
- **Planner:** Sol
- **Approval source:** Owner approved the revised migration roadmap and requested its persistence in chat on 2026-10-28. This detailed Stage 1 contract adds execution interfaces; implementation requires its own approval or authorization of this exact path.
- **Implementation log:** `session_logs/YYYY-MM-DD/NN-data-architecture-operational-safeguards.md` (create in the implementation session)
- **Commit policy:** Separate plan commit; owner controls staging, commits, pushes and releases.

## Goal and acceptance

Complete the operational foundation of the [approved blueprint](../../planning/data_architecture_blueprint.md) without changing measurement semantics, the model, serving schemas, the scheduler's activation policy, or historical data. New football revisions retain independently reproducible score exceptions. Normal rollover fetches only authorized new observations; historical repair requires a reviewed request plan and hard request budget; retained-candidate preparation and promotion never call providers.

Implementation is complete only when:

1. New exception documents are revision-specific, their earlier entries come from the previous manifest's hash-verified reference, no existing differing bytes can be overwritten, and identical-byte resume succeeds.
2. Sunday automation stages/commits the exact new exception document; Monday market refresh inherits the same pinned reference without creating another file.
3. Recording fakes prove rollover scope and interruption/resume through actual request execution, not just step-list inspection.
4. Repair plans enumerate exact endpoints/parameters before fetching; apply requires a pinned plan, reason, budget and approval reference. Unlisted requests and exhausted budgets stop before an outbound attempt.
5. Preparation/release/rollback entry points complete under fakes with provider credentials absent and provider calls disabled.
6. Configured baseline and final required checks pass, with failures investigated rather than grandfathered by count. No real provider call, cloud mutation, repair or release is needed for this contract's acceptance.

## Baseline and constraints

Baseline is `dev` / `origin/dev` at `4b93ee56` after an authorized fast-forward from `356b24da`; planning branch is `codex/data-architecture-roadmap`. Read [current status](../../status.md), the [runbook](../../ops/weekly_runbook.md), and the [automation contract](../2026-10-26/01-weekly-update-automation.md) before implementation. Do not duplicate live release IDs here.

- The [incremental narrow amendment](../2026-10-25/01-incremental-close-week-rollover.md) is implemented. `advance-week` carries certified captures, fetches schedule/completed-week observations and gates earlier schedule/finals. The [October 20 draft](../2026-10-20/02-incremental-weekly-ingestion.md) retains deferred repair/promotion/request-execution requirements.
- `build_season_revision.py` has incremental and directly callable full-history modes; Make gates the latter only with `FULL_HISTORY=1`.
- `refresh_score_exceptions.py` reads/overwrites one exception path and re-pins a candidate manifest. `weekly_automation.py` hardcodes that path. `build_market_revision.py` already asserts exception-reference equality.
- `season/manifest.py` validates relative exception refs; `season/inputs.py` checks their exact bytes. Preserve the `season_revision_v1` reference shape and legacy relative-path compatibility.
- The October 27 rebrand log reports 2,339 Python tests passed / 12 skipped with `CFBD_API_KEY=ci-placeholder`; the earlier 16 failures came from constructor configuration. This is evidence, not a fresh baseline.

**Included:** revision/market builders, exception refresher, automation controller, manifest/input validation, ops step construction/resume, source request execution/inventory, scoped tests, Make targets and operational docs. Inspect `.github/workflows/weekly-season-update.yml`; change wiring only if new arguments require it, never its schedule/activation policy.

**Excluded:** measurements, profiles, migrations, projection-set/workflow changes, V5 formulas, market/grade selection, publication, repairs of old manifest references, schedule/final-score history repair, and actual repair execution. Add no dependencies or database migration.

Use matching runtime/environment wrappers. Tests use recording fakes, temporary storage and disposable PostgreSQL only. Never supply serving URLs as `TEST_DATABASE_URL` or expose secrets in receipts. Known historical checksum failures stay documented, not silently fixed.

## Ordered changes

### 1. Reproduce the baseline

Run `CFBD_API_KEY=ci-placeholder make test` in the isolated implementation worktree. Record commit, command and pass/skip/fail categories in the implementation log. Reproduce unexpected failures with focused tests. Do not modify the model to hide unrelated failures; a material unrelated blocker needs an amendment. Preserve unrelated changes.

### 2. Centralize exception references and immutable output

Introduce a small shared helper under `season/` for reference reading/path derivation and reuse it from the CLIs and `season/inputs.py`.

- Derive `conf/season/2026/score_reconciliation_exceptions_w<N>_v<K>.json` from each new football manifest `revision_manifest_w<N>_v<K>.json`. Require that naming convention on new writers; legacy readers retain existing valid paths.
- Resolve within the repository; reject absolute paths, traversal and symlink escape. Preserve existing entry semantics, duplicate/nonempty-reason validation, and shared canonical team mapping.
- Read baseline entries from the candidate's inherited, hash-verified exception reference. Missing reference means no declarations; missing or mismatched referenced bytes fail, never become an empty baseline.
- Separate baseline from destination in the refresher API. Keep `--exceptions` as an optional explicit destination only when it matches the derived path. Normal automation omits it. `--dry-run` writes no exception or manifest bytes.
- Preserve quarter-line-score proof, earlier-week mismatch and unused-exception gates. Validate the complete result before writing. Create the document exclusively; identical existing bytes succeed, differing bytes fail without changing either file.
- Atomically replace the candidate manifest only after the immutable file exists. Check its on-disk bytes still match the initially read candidate before replacement. Refuse to re-pin tracked manifests: changed committed revisions require a new version.
- Crash after document creation but before manifest finalization is resumable with identical bytes; do not promise a cross-file transaction. New uncommitted manifests may inherit the previous exception ref until this finalization step. Never prepare or commit them before finalization.

### 3. Wire rollover, refresh and automation together

- The season builder carries a verified previous ref; manual rollover finalizes exceptions before commit/prepare.
- Remove the shared `EXCEPTIONS_FILE` choice from `weekly_automation.py`. After refreshing, reread the finalized manifest, validate the ref, resolve the path, and commit exactly `[manifest, exception_path]` through the existing operation. Preserve clean-tree/commit pins, credential roles, Preview proof and weekly activation gates.
- `build_market_revision.py` preserves the source exception ref exactly and verifies bytes before new dataset registration. It creates no exception document, even when its manifest version changes. Preserve absent refs instead of raising `KeyError` or inventing one.
- Extend controller tests with recording dependencies and temporary repositories: Sunday finalization/commit, Monday inheritance, conflicting destinations and crash recovery. Keep workflow argument wiring consistent.

### 4. Complete rollover and promotion execution tests

Exercise `advance-week` and the ingestion request boundary with fake CFBD clients and a seeded local catalog for upcoming weeks 2, 8 and 12. Permitted requests are the season schedule and pinned-inventory plays/game-stat requests for completed week N-1. Canonical and provider weeks can differ: assert exact endpoint/parameter identity against pinned policy, not only numeric week equality. Market capture remains separately explicit; controller tests verify its declared current/next market weeks too.

Record carried earlier capture IDs/hashes and compare completed-week outputs with existing parity utilities and documented provenance exclusions. Do not broaden stability exclusions or accept changed grades.

Interrupt after a completed plays step; resume without repeating its requests. Interrupt inside ingestion; reuse verified registered requests and retry unfinished requests only. Reject changed inventory, carried captures or step definitions under the same run. Corrupt/missing evidence must not be accepted solely because a success marker exists.

Exercise retained-candidate `prepare`, `release` and owner-authorized `rollback` with fake storage/database, absent provider keys, and raising provider methods. Assert zero executed provider requests/fetch steps; do not require an import-free transitive module graph. No actual preparation/release against cloud state is authorized here.

### 5. Add budgeted observation-repair planning and apply

Add `scripts/pipeline/repair_season_observations.py` with plan/apply modes. Its bounded outcome is named weeks' replacement plays/game-stat captures and an auditable receipt. Rebuilding/publishing corrected season inputs remains a separate authorized data operation. This preserves the roadmap's distinct ingestion, retained-input rebuild and promotion boundaries.

**Planning interface:** `--season 2026 --environment preview --previous-manifest <path> --weeks <comma-separated canonical weeks> --reason <text> --max-requests <positive integer> --pipeline-run-id <fresh ID> --output <plan.json>`. All are required. Require unique integer weeks in the manifest's completed history, normalize their ordering, and read only pinned schedule/policy/parent evidence. No schedule refresh, market capture or provider inventory call.

Recover the complete retained provider schedule from the certified schedule dataset's source-capture lineage, including FBS/FCS games that a narrower Silver view may omit; pin its exact immutable bytes in the request plan. Missing parent evidence is a stop, never permission to use the current raw schedule. Use the independent inventory machinery in `quality/request_inventory.py` and `scripts/data/build_expected_request_inventory.py`, extended to take retained schedule evidence instead of mutable latest pointers. Enumerate actual CFBD endpoints/parameters. A provider-week query may overlap canonical weeks: declare true coverage and reject requests extending beyond the approved set. Require a revised owner-approved set instead of silently broadening it.

Canonical `season_observation_repair_plan_v1` JSON contains season, environment, source-manifest SHA-256, policy/input hashes, sorted weeks, reason, run ID, maximum outbound attempts and ordered requests. Each request records provider/entity/endpoint/parameters, covered canonical weeks and deterministic request hash. Exclude secrets and wall-clock request timestamps from request identity. Print the inventory and plan SHA-256. Permit identical-byte local resume, refuse conflicting plan files. If unique requests exceed the cap, write a local rejected report and stop before fetching or cloud writes.

**Apply interface:** `--apply --request-plan <plan.json> --request-plan-sha256 <sha> --approval-ref <owner decision reference>`. Apply settings come from the plan; reject incompatible overrides. Validate plan/input hashes and the exact whitelist before source writes. A nonempty reference records the decision, not proof of operator authorization. Weekly automation never invokes apply.

Use existing ingesters/capture registration with an optional execution guard immediately before **every outbound SDK attempt**, including retries/page calls. Unguarded ordinary callers retain existing behavior. Disable hidden SDK retries for guarded requests. Unexpected endpoints/parameters fail before sending.

Keep a locked, durable local per-run attempt journal beside the plan, shared across subprocesses. Reserve/fsync a unit before each outbound attempt. Failed requests, retries and page calls count. Reserve-before-send crashes conservatively consume budget; restart cannot reset usage or raise the cap. Reuse completed registered captures only with verified evidence. An uncertain in-flight attempt may retry only within remaining budget. Changed plan/budget requires a new run/decision. Budget exhaustion is not a transient retry condition.

Write `season_observation_repair_receipt_v1`: plan hash, approval ref, reserved-attempt count, completed capture IDs/hashes, incomplete request hashes and outcome. Actual apply may register immutable captures in Preview but must not overwrite old captures, revise manifests, build serving projections, activate releases or alter forecasts/grades.

Replace the executable `make season-revision` full-history path with refusal and guidance to plan/apply; `FULL_HISTORY=1` alone no longer permits fetching. Direct non-incremental `build_season_revision.py` must also refuse before requests. Explicitly enumerating all completed weeks through the budgeted repair interface supports full-history acquisition. Certified retained-input rebuilds remain provider-free; normal `season-close-week` stays available.

### 6. Reconcile documentation and close

Update Make help, runbook, quickstart and the older ingestion draft's amendment record to link this successor. Explain immutable filenames, inherited versus finalized refs, Monday reuse, budgets and repair captures versus corrected publication. Record actual implementation evidence in the blueprint/index; change status only for factual implemented limitations or live state. Never claim the tooling repaired history or released data.

## Validation

Extend exception-refresher, incremental-close-week, weekly-automation, market-revision, ops-state-machine, request-inventory/ingestion and season runner/release suites; add repair-plan/apply tests. Use existing disposable PostgreSQL fixtures for catalog/cross-process evidence.

Required cases:

- Legacy relative refs load; missing/hash-mismatched refs, traversal, symlink escape and duplicate entries fail.
- Successive football revisions preserve earlier bytes; market refresh shares the source ref unchanged.
- Validation failures write neither manifest nor exceptions; conflicting content fails; identical resume/document-first crash recovery succeeds; tracked manifest changes fail.
- Sunday commits the derived path, Monday never refreshes exceptions; schedule/cutoff gates remain intact.
- Recording clients prove rollover scope, provider-week mapping and partial-step resume; changed definitions refuse resume.
- Repair planning has no provider/cloud writes. Apply rejects missing approval, changed hashes, unlisted requests and exhausted budgets. Retries/pages/crashes/subprocess restarts cannot reset or exceed the cap.
- Make and direct full-history bypasses refuse to fetch; incremental rollover remains available.
- Fake preparation/promotion/rollback complete without provider keys and record zero provider requests.

Final commands: `CFBD_API_KEY=ci-placeholder make test`, `make contracts-check`, `make quality-check`, scoped `uv run ruff format --check` and `uv run ruff check` over changed Python files, `uv run mkdocs build --strict`, and `git diff --check`. Run `CFBD_API_KEY=ci-placeholder make check` for the integrated gate with web dependencies installed. No web change is planned; web scope expansion requires an amendment and `make web-e2e`.

## Handoff/amendments

**Next:** approve this contract or authorize its exact path in a fresh Terra task using `implement-plan`. Mark Approved only on that authorization, then In Progress when work starts. Roadmap approval alone does not authorize the new CLI details.

**Stop gates:** inaccurate baseline, broken certified exception ref, unresolved request coverage, inability to account for all outbound attempts, required schema/model/publication changes, or unexpected source history differences. State expected/actual and propose the smallest amendment. Do not weaken budgets, parity, score proof or provenance.

**Operation boundary:** implementation and fake testing are separate from invoking apply, rolling over real data, changing cloud state or promotion. No real provider calls, migration, repair, rehearsal or activation is authorized by this contract alone. Use the runbook and obtain concrete operation authorization when needed.

Mechanical amendments may proceed only with unchanged architecture, interfaces, scope and acceptance. Material deviations return to Sol; append reason, previous/revised approach and impact. Propose separate plan and implementation commits; never commit automatically.
