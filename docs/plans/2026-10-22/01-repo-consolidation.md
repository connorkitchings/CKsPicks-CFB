# Repository consolidation, pruning and production hardening

- **Status:** Approved
- **Created:** 2026-10-22
- **Approval source:** Owner approved the plan in chat on 2026-10-22.
- **Implementation log:** session_logs/2026-10-22/02-repo-consolidation.md
- **Commit policy:** One commit per group on `connorkitchings/repo-consolidation`, based on `897fa55c`. Nothing goes to `main` or Production.

## Goal

V5 is the only operational model. Carry out the deferred "Phase 3" of `docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md` (deletion groups 3a–3e), consolidate agent guidance and docs, archive closed plans and logs inside the repo, and harden CI and environment-variable handling.

## Owner decisions (2026-10-22)

- Archive plans and logs inside the repo; do not delete them.
- Delete all V4 and legacy code, but keep the research code.
- Worktree off `dev`, one commit per group; nothing to `main` or Production.
- Include CI hardening and an environment/secret audit.
- Out of scope: restructuring the package, database schema or migration changes, Production writes, renaming the Sol/Terra workflow, moving evidence to R2.

## Boundary with the data architecture blueprint

`docs/planning/data_architecture_blueprint.md` §4 owns these paths; this cleanup leaves them alone:

- the prepare-week step list in `ops/__main__.py` (`build_steps`)
- `publish_team_stats`, `publish_matchup_data`, `promote_silver_versions`, `build_team_game_dataset`, `features/aggregations/`, `charts/`
- duplicate data paths (retired only under blueprint Contract 5)

## Deletion rule

Delete a module only when nothing in the live V5 graph, `scripts/research/`, `scripts/analysis/` or the research `src` packages imports it. Re-run the import graph after each group. Coverage must stay ≥ 60%. `rg` must find no references to deleted paths outside archived history.

## Keep

`ingest_season`/`ingest_week`, `preseason_features.py`, `features/situational`, `models/{late_quotes,market_grading,training_policy}`, `forecast/{live,offsets}`, the `data_first_phase*` data modules imported by `ratings/possession_*`, `omegaconf` (explicit dependency), the web schema's legacy tables and `/api/health`'s `predictionRuns` read, `contracts/`, `data-first-pregame-capture.yml`. Resolve the `data/schema_contracts.py` → `ratings/v4_benchmark` tie from the import graph. Uncertain items stay and are listed in the session log.

## Commit groups

1. `chore: fix ignore rules and remove stray tracked files`
2. `chore(ci): replace Nx with npm scripts and harden CI`
3. `refactor: remove 6A/6B rebuild and one-off cutover tooling`
4. `refactor: remove legacy V5 publication path`
5. `refactor: remove the V4 training and serving stack`
6. `docs: consolidate agent guidance and refresh stale docs`
7. `docs: archive closed plans and September session logs`
8. `chore: reconcile environment examples with code`
9. Close out: `docs/status.md` one-line note, session log, merge into `dev` after owner review.

## Gate (after every group)

```bash
uv run ruff format --check . && uv run ruff check .
uv run pytest tests -q -n 4            # plus Postgres suite on a disposable local cluster
uv run coverage report --fail-under=60
make contracts-check && make quality-check
uv run mkdocs build --strict
npm --prefix web run lint && npm --prefix web run typecheck && npm --prefix web run test:publication && npm --prefix web run build
rg -n '<each deleted path/module>' --glob '!docs/archive/**' --glob '!session_logs/**'   # zero hits
git diff --check
```

After groups 4 and 5, with owner go-ahead, run the serving-parity check from the 2026-10-15 plan (Preview R2 reads only). If credentials are unavailable, record it as not run.

## Definition of done

- Each group committed separately and passing the gate; CI passes on a PR into `dev`.
- No tracked V4/Hydra/MLflow/Nx code, configs or dependencies; `uv.lock` shrunk; `make help` lists only live targets.
- One authoritative copy of each piece of agent guidance; no current doc references old routes, V4 as operational, or deleted paths.
- `docs/plans/` and active `session_logs/` contain only October work and open contracts; the archive is indexed.
- `.env.example` covers every variable the code reads; no secrets or stray identifiers tracked.
