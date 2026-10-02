# Manual V5 Weekly Operator

> **Status (2026-09-30):** The [exact repaired-V5 release packet](../plans/2026-09-29/v5-intended-update-production-release-packet.md)
> selected `2026w{0..4}-v5repair-20260929-p1` as retrospective scored replays
> and `2026w5-v5repair-20260929-p2` as the ungraded live slate. The old
> `2026w{0..4}-v5replay-bestquote-20260926-r3` runs and
> `2026w5-5d436e58c072` remain the exact six-week rollback set. The p2 Week 5
> quotes were captured at 2026-09-29 20:28:55Z; a later check found six moved
> quote values across five games. The final pre-kickoff freeze was completed
> 2026-09-30T12:34:06Z (see [Current Status](../status.md)). Do not grade Week 5
> until certified finals.

For the selected successor, continue from its independently verified rating
manifest and refitted bundle. Keep the original V5 projector and original
model-pair authorizations as rollback paths; a new prospective successor run
requires its own exact source, bundle, quote, and release authorization. The
full checklist below still governs market coverage, publication, and freeze.

## One cycle, reviewed stages

### Weekly close, open, and freeze checklist

Use this entire sequence when an operator asks to close a week, open the next,
publish, or freeze. Record each stage and its evidence in the session log; do
not treat a successful forecast or first publication as the end of the cycle.

1. **Close the prior slate:** Reconcile the selected frozen run, complete FBS
   schedule, certified finals, grading, and `close` receipt. Calculate the
   required final-stabilization interval from the latest certified final.
2. **Open the next slate:** Refresh and independently verify repair,
   measurements, ratings, and forecast. Match the forecast's paired spread and
   total predictions to every eligible scheduled FBS game; check the rating
   projection and readiness receipts before preparing a serving candidate.
3. **Reconcile market capture:** Capture the target week's CFBD lines and the
   optional second provider if enabled. Record each provider's status and
   capture time. Compare source game IDs, Silver quotes/snapshots, and candidate
   predictions against the same complete schedule, separately for spread and
   total. Record every missing game ID and classify it as source absent,
   processing loss, or unresolved. A null published line alone is not evidence
   that the provider has no line.
4. **Refresh before release:** Recheck current source availability before the
   Preview and production publication decisions. If additional lines are now
   available, take a new immutable capture and prepare a new candidate; never
   reuse an older artifact or describe it as current. A new production run
   requires its own exact packet, authorization, publication, selection, and
   health/page verification. Record remaining gaps and the next refresh time.
   Matchup stats (optional while matchup pages are closed): after the
   post-week Silver refresh, publish `team_season_stats` for the new week
   (Preview, then production after promoting Silver); see
   [Team stats](weekly_pipeline.md#team-stats-matchup-pages).
5. **Freeze before kickoff:** Make a final capture and reconcile both line
   types against every eligible game. Freeze only the selected reviewed run
   within the existing lead-time gate. Use a game-specific waiver only for a
   genuine provider exception after a fresh source check; an available line or
   an uninvestigated processing gap is not a waiver. Record the frozen run ID,
   quote lineage, coverage, and timestamp. Close and score only after finals
   stabilize.

The first publication may intentionally be partial while books open markets.
Its coverage is a dated observation, not a promise that lines remain absent.
The next market refresh and final freeze remain explicit tasks even if the
initial production release succeeded.

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
week, environment, decision reference, and exact same-week rollback run. For an
initial V5 cutover, record the reviewed V4 run where one exists. For a V5 line
refresh, the prior selected V5 run can serve as immediate rollback; explicitly
record the absence of a same-week V4 run. Validate the
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
freeze records no prospective timestamp. Keep the reviewed same-week rollback
run selectable. Reselect it with `select_public_run.py` and its exact run ID;
include `--allow-v4-fallback` when the rollback run is V4. Follow with
selected-week health and page checks. Never alter immutable artifacts to roll
back.
