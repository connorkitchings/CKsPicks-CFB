# Manual V5 Weekly Operator

> **Status:** Implemented and rehearsed on Preview; V4 remains public. The
> first live 07/08 refresh requires stabilized Week 4 finals. A production
> V5 publish requires a separately approved, exact one-slate release record.
> The fixture-class rehearsal (cycle `v5-rehearsal-2026w4`, repair component
> on stabilized Weeks 0–3 inputs) exercised every controller mechanic; it is
> not live evidence.

## One cycle, reviewed stages

The operator is `scripts/pipeline/run_v5_weekly_cycle.py`. It has no timer or
automatic trigger. Run it from a clean committed checkout with `PYTHONPATH=.:src`
and explicit `--season`, `--week`, `--environment`, `--cycle-id`, and
`--descriptor`. Use `zsh scripts/ops/with_preview_env.sh` for Preview database
operations and `zsh scripts/ops/with_production_pipeline_env.sh` for production
V5 database operations. The descriptor is a local JSON file with `schema_version`
equal to
`v5_weekly_cycle_v1`, those same four identity fields, the exact 40-character
committed `code_sha`, and a `components` object. Add a component only when its
immutable inputs are known; keep the cycle ID and all completed component
definitions unchanged. A changed code SHA or completed input needs a new cycle
ID and new immutable research run IDs.

## Database identity for V5 operations

Every production V5 publisher, selector, and operator command runs through
`zsh scripts/ops/with_production_pipeline_env.sh`. That wrapper reads only the
restricted `cks_prod_pipeline` branch URL from the local macOS Keychain service
`ckspicks-cfb/production/pipeline-url`, exports `DATABASE_URL` and
`CFB_ARTIFACT_ENV=production`, and fails when the item is absent. The owner
URL from `.env` is an admin and migration credential; it must never publish or
select a V5 run. Preview V5 commands use `zsh scripts/ops/with_preview_env.sh`
and the `cks_preview_pipeline` role.

Inside the publication and selection transactions, both `session_user` and
`current_user` must equal the exact restricted pipeline role
(`cks_prod_pipeline` in production, `cks_preview_pipeline` in Preview).
Owner, migrator, web, wrong-branch, and `SET ROLE` sessions are rejected
before any V5 prediction or selection write, including direct
`publish_to_db.py --from-artifact` and direct `select_public_run.py` calls.
V4 publication and same-week V4 fallback are unchanged. The pipeline role has
`SELECT`-only access to `v5_serving_authorizations`; only an administrator
creates the one-run release record in a separate, later decision.

The components run in this order: `repair`, `measurement`, `rating`, `forecast`,
`readiness`, `prepare`, `publish`, `freeze`, `close`. The first three refresh
Contracts 07/08; forecast/readiness apply Contracts 09/05; the remaining
components use the normal weekly serving and scoring path. Each research
component has `run_id`, UTC `as_of`, sealed `config`, its raw `config_sha256`,
`arguments` with the exact named input URI flags accepted by its existing
runner, and `parents` mapping every input URI to its raw SHA-256. `prepare`
also uses the serving config and a stable prediction run ID. `publish`,
`freeze`, and `close` specify that same run ID and UTC `as_of`; `publish`
also binds its serving config and SHA. `close` binds a certified Silver
`game_outcomes` ref URI and SHA, plus the reviewed last-final timestamp as
`finals_stabilized_at`. The controller verifies the ref covers all games in
the selected frozen run and waits 24 hours after that timestamp.

For each component, save a preflight outside the repository, review its
population, cutoff, parent URIs and checksums, then invoke `apply` with the
same descriptor and evidence path. Example:

```bash
SHA=$(git rev-parse HEAD)
PYTHONPATH=.:src .venv/bin/python scripts/pipeline/run_v5_weekly_cycle.py preflight \
  --descriptor /tmp/v5-2026w5-cycle.json --season 2026 --week 5 \
  --environment preview --cycle-id v5-2026w5-reviewed \
  --component forecast --evidence /tmp/v5-2026w5-forecast-preflight.json
# Review the JSON and exact inputs. Then, from the same clean committed SHA:
PYTHONPATH=.:src .venv/bin/python scripts/pipeline/run_v5_weekly_cycle.py apply \
  --descriptor /tmp/v5-2026w5-cycle.json --season 2026 --week 5 \
  --environment preview --cycle-id v5-2026w5-reviewed \
  --component forecast --evidence /tmp/v5-2026w5-forecast-preflight.json
PYTHONPATH=.:src .venv/bin/python scripts/pipeline/run_v5_weekly_cycle.py status \
  --descriptor /tmp/v5-2026w5-cycle.json --season 2026 --week 5 \
  --environment preview --cycle-id v5-2026w5-reviewed
```

Use new immutable run IDs for 07/08 and 09 after finals stabilize. Research
applies remain Preview-only, run their independent verifiers, and save a
versioned receipt in `ops.pipeline_runs`/`ops.pipeline_steps`. The next
component requires the preceding successful receipt. A retry uses the same
cycle/component identity and skips a verified completed step. A different
identity under the same ID fails. `prepare` writes an immutable candidate
without Neon publication. `publish` re-verifies the forecast source, complete
paired schedule, market lineage, and, in production, the exact authorization
before a write. `freeze` checks the selected run, full coverage, and the
one-hour pre-kickoff hard boundary again at apply. `close` scores the selected
frozen run against the bound outcomes ref and reuses the existing resumable
close operation. Do not treat replay, a fixture rehearsal, a candidate
artifact, or `pending` predictions as prospective evidence.

## Production release packet and rollback

After the live 07/08/09/05 receipts and populated Preview rehearsal pass,
prepare the exact production prediction artifact without Neon activation.
Record its run ID, artifact URI/SHA, config SHA, model ID, inference bundle SHA,
verified 09 forecast URI/SHA, verified `ready` 05 verifier URI/SHA, season,
week, environment, decision reference, and V4 fallback run. Validate the
packet read-only with `scripts/pipeline/validate_v5_release_packet.py` and
the exact serving config. A separate user decision on that packet precedes
an admin insert into `v5_serving_authorizations`. The pipeline role has
SELECT only; the web role has no table access. The broad `v5_release_policy`
still applies but cannot replace this one-run record. Direct artifact
publication and later V5 reselection enforce the same record. No production
authorization is created by this runbook or the operator.

If a stage fails, inspect `status` and its ops step receipt. Resume only with
the identical descriptor, preflight evidence, and run ID. An incomplete R2
prefix is ineligible; diagnose and use a new ID after a clean commit. A late
freeze records no prospective timestamp. For an approved cutover, keep the
reviewed same-week V4 run selectable; rollback is `select_public_run.py`
with its exact run ID and `--allow-v4-fallback`, followed by selected-week
health and page checks. Never alter immutable artifacts to roll back.
