# Session: Stage 6B implementation

## TL;DR
- **Worked On:** Stage 6B execution contract (`docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md`), Task 0 (issue register) and Task 1 (harness generalization).
- **Outcome:** Contract and Amendment 1 (write boundary: Preview R2 `rebuild/6b/<run_id>/` plus `lake/gold/reconstruction_*` with catalog registration; no serving, selection, grade or production writes) approved by the user. Task 1 implemented; Tasks 2-5 open.
- **Next:** Task 2, the twelve 6B stages and `conf/rebuild/6b_v1.yaml`.

## Task 1 (harness generalization)
- `RebuildPlan.namespace` (`rebuild/6a/` default, `rebuild/6b/` allowed). It enters the signed plan and the root manifest only when it is not the default, so published 6A plans and roots keep their exact hashes (6A plan shas `fc263834...` and `dff398aa...` are pinned in a test).
- `GuardedStore(run_namespace=...)`; the orchestrator's root key, the parity receipt keys and `PublishedRun`'s prefix follow the plan or root. Preflight refuses a guard that lacks the plan's namespace. The existing 6A stage modules keep their fixed `rebuild/6a/` prefixes, so a 6B plan cannot run one: the guard rejects the write.
- Served-chain tokens (run and serving paths, rating `e80ae347...`, bundle `30c4f1eb...`) are in `LEGACY_PARENT_TOKENS`; only `legacy_allowed` stages may read them.
- `scripts/pipeline/rebuild_6a.py` and `publish_6a.py` pass the plan's namespace to the guard; they keep their names.

## Decisions
- Write boundary (Amendment 1): Preview R2 `rebuild/6b/<run_id>/` plus `lake/gold/reconstruction_*` with catalog registration; no serving, selection, grade, authorization or production writes (user choice).
- Replay Weeks 0-5; Week 5 uses the p2 run's original cutoff and quote set (user choice).
- 2026 offsets use 6A semantics (unresolved team-games unusable); the run stops if frozen-at-cutoff offsets differ from kickoff-order offsets (user-approved gate).
- The run stops, before predictions, if the 6A bundle needs an adapter (user-approved gate).
- Contract is a new execution contract; production claims about the Week 5 quote set are excluded.
- The 6A stage modules keep fixed `rebuild/6a/` prefixes rather than being rewritten; the guard rejects them under a 6B plan.

## Files changed
- Docs: `docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` (new; In Progress), `docs/plans/index.md`, `docs/data/known_issues.md` (6A updates to issues 2, 3, 7, 10, 13, 14; committed in `26edbd5`), `docs/status.md`, this log.
- Code: `src/cks_picks_cfb/rebuild/{plan,targets,orchestrator,parity,published,inputs}.py`, `scripts/pipeline/{rebuild_6a,publish_6a}.py`.
- Tests: `tests/test_rebuild_namespace.py` (new).

## Validation
- `tests/test_rebuild_namespace.py` (10 tests; 9 fail without the change). Full suite: 1,956 passed, 9 skipped. `ruff check .`, `make contracts-check`, `mkdocs build --quiet`, `git diff --check` clean.
- No R2 or database access in this task.

## Blockers
- None. Open risks recorded in the contract: 6A bundle compatibility with `apply_exported_bridge` (unverified), the offset-freeze gate, drift of the pinned replay thresholds file, and whether production's frozen Week 5 used the same quote set (no production claim is made).
- One live publish attempt in the earlier 6A Task 4 work was denied by the permission classifier; the user ran the identical command. No 6B publish is pending.

## Contract status
`docs/plans/2026-10-05/01-stage6b-completed-week-reconstruction.md` stays **In Progress**: Definition-of-done items 2-8 are open.

## Next
Task 2: write `conf/rebuild/6b_v1.yaml` (pins taken from hash-checked reads: 6A main and Task 4 roots, source lock, bets config, Week 5 market refs and outcomes ref, served manifests) and the twelve stages, starting with `foundation`, `scoring_events_2026`, `offsets_2026` and `states_at_cutoff`; check bundle compatibility before the `predictions` stage. All git operations and live publishes stay user-run.

**tags:** ["stage6b", "harness", "namespace", "contract"]
