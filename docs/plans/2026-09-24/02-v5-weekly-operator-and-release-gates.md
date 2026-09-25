# V5 Weekly Operator and Exact Release Gates

- **Status:** In Progress
- **Created:** 2026-09-24
- **Planner:** Sol (plan-session)
- **Approval source:** User selected workflow preparation and an operator CLI in the planning conversation, then said “Proceed” after reviewing the complete plan on 2026-09-24. On 2026-09-25 the user approved the production-role correction, chose to provision the role and apply migration 0014 now, then instructed Sol to document the amendment without implementing it. Neither approval authorizes production V5 activation.
- **Implementation log:** `session_logs/2026-09-25/01-v5-weekly-operator-and-release-gates.md`
- **Commit policy:** Separate plan commit recommended because the work spans an append-only migration and production publication policy. Git operations remain user-controlled.

## Goal and current state

Prepare one manual, resumable V5 weekly operating path and close the remaining exact-artifact authorization gap before a production cutover. Success means an operator can inspect and run each stage with reviewed inputs and stable identities, recover safely from a failed step, and prove that no V5 production artifact can reach Neon or public selection without a one-slate authorization bound to its exact bytes.

V5 historical development is accepted. The immutable Weeks 0–3 replay, Preview serving, and same-week V4 rollback rehearsal are complete. V4 still serves production. Week 4 is underway at planning time; its finals have not stabilized, so new Contract 07/08 parents, a Contract 09 live forecast, and Contract 05 `ready` evidence cannot yet be claimed. The existing ops state machine provides leases, resumable steps, and run receipts. The 07/08/09 and shadow CLIs provide evidence-bound preflight/apply and independent verification. `publish_to_db.py` already reconstructs the V5 source, but `v5_release_policy` authorizes a model and starting week rather than one forecast and one prediction artifact. The V5 config's boolean production flag is not an exact release decision.

## Approach and boundaries

Use a manual CLI, not a GitHub Actions or external scheduled trigger. Compose the established research and ops commands; do not reimplement possession measurements, ratings, forecast math, or market ingestion. Keep preflight and apply separate so an operator reviews exact parents, cutoff, population, and digests before an immutable write. Preserve the current clean committed-code gate, independent verifiers, Preview-only research applies, provider request limits, and retry identities.

Add an append-only, admin-written V5 serving authorization table in migration 0014. One row authorizes one environment, season/week, and prediction run. It binds the model and inference bundle SHA, verified 09 forecast URI/SHA, verified 05 readiness URI/SHA, serving config SHA, prediction artifact URI/SHA, decision reference, and approval timestamp. The pipeline role receives SELECT only; the web role receives no access. The old `v5_release_policy` remains an additional model/earliest-week check. Research manifests retain `production_activation_authorized: false`. No authorization row, production migration, production publication, public selection, or V4 retirement is part of this implementation milestone.

### Included

- Operator CLI and stage receipts/status for refreshed 07/08 parents, 09 forecast and 05 readiness, weekly serving preparation/publication, freeze, and close.
- Exact release authorization contract, production publisher/selection checks, migration and shared schema synchronization, focused tests, and operator documentation.
- Fixture and isolated Preview rehearsals that do not claim a certified live forecast.

### Excluded

- Automatic scheduling, provider captures beyond the existing commands, a live 07/08/09 apply before stabilized Week 4 finals, production activation, and V4 execution retirement.
- Any 2026 outcome fit or V5 reselection, retroactive prospective evidence, or changed betting policy.

## Implementation tasks

### 1. Build the manual stage controller

Add `scripts/pipeline/run_v5_weekly_cycle.py` with `preflight`, `apply`, and `status` actions and stages `refresh`, `forecast`, `publish`, `freeze`, and `close`. Require explicit `--season`, `--week`, `--environment`, `--as-of` where time applies, and a stable `--cycle-id`; require exact immutable parent refs and existing run IDs for the selected stage. Store a versioned cycle descriptor and per-stage receipt in the existing ops control plane, binding code SHA, config SHA, input refs/SHAs, cutoff, and output manifest/run IDs. A repeated identical apply returns the prior result; an identity change with the same cycle/stage ID fails. Use the existing lease for the season/week, and expose current state and the first blocking dependency through `status`.

The controller invokes existing 07/08/09/05 preflight, apply, independent verification, and repeat paths, and existing `publish-week`, `freeze-week`, and `close-week` operations. It never automatically promotes a successful preflight to apply. `refresh` requires stabilized completed-game sources and new immutable 07/08 run IDs; `forecast` requires their signed receipts and a future-slate schedule; `publish` requires a verified 09 forecast and 05 `ready` for the same slate. A blocked readiness report is retained as evidence but cannot advance publication. `freeze` enforces the existing first-kickoff lead and paired coverage; `close` waits for certified finals and scores the selected frozen run. Keep source request caps, soft-fail market behavior, and no-repeat paid requests from the existing ops steps.

**Acceptance:** An operator can resume a partial cycle with the same identity and see exact completed/blocked stages. Concurrent applies cannot run a stage twice. Missing, stale, altered, or wrong-slate parents fail before a write. Replay artifacts cannot be used as prospective parents.

### 2. Prepare an immutable production candidate without activation

Separate V5 candidate artifact preparation from Neon publication. Add an explicit prepare-only path that generates the normal prediction-run artifact from a pinned, independently verified 09 manifest and serving inputs, with a stable prediction run ID, without a Neon write or `current_week` change. This path may read the Preview research manifest from the shared immutable R2 bucket. It must not require setting the serving config's production-authorization boolean to true; that boolean cannot substitute for the release record. Preserve source reconstruction, complete margin/total pairs, schedule and cutoff checks, model identity, and raw artifact digests. The ordinary Preview rehearsal path stays usable.

**Acceptance:** The candidate is reviewable by exact URI/SHA before activation. A repeat with the same inputs is byte-identical; changed bytes at the same immutable URI fail. No candidate-preparation command selects a public run.

### 3. Enforce one-slate release authorization at the final boundary

Add `contracts/migrations/0014_v5_exact_release_authorization.sql` and synchronize `contracts/schema.sql`, `contracts/schema.ts`, and the web schema copy. The table is append-only for the pipeline role and has a unique authorization identity for an environment/season/week/prediction run; replacement requires a new reviewed record. Provide a read-only packet validator that compares the proposed record to the 09 and 05 verifier receipts, prepared artifact, config, and model identity. Creating the record remains an administrative action after the later exact-packet approval; this milestone creates none.

Before any production V5 insert, update, or selection, `publish_to_db.py` must find the matching authorization and revalidate all bound URIs and raw SHAs inside the transaction. This applies to `--from-artifact` and direct CLI calls as well as the operator path. `select_public_run.py` and the shared selection function must reject a production V5 run lacking the same authorization, including a previously published run. Preview replay selection retains its current rehearsal policy; V4 publication and rollback remain available. Do not trust an unbound CLI model label or config flag.

**Acceptance:** Missing or mismatched authorization causes zero production prediction/selection writes. A record cannot authorize another week, run, environment, forecast, readiness receipt, config, model, or altered artifact. The pipeline role cannot insert or change an authorization.

### 4. Document and verify the handoff

Update `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`, and `docs/modeling/v5_status.md` with the manual stage sequence, preflight-review/apply split, stable retry IDs, exact release packet fields, rollback, and the Week 4 finals gate. Keep the existing Product Transformation contract In Progress. Record any implementation amendment and the actual validation in the implementation session log.

**Acceptance:** The runbooks give one operator path, explain how to resume or stop after a failed stage, and never imply that fixture rehearsal, replay, or a prepared candidate is a live or activated forecast.

## Testing and acceptance

- Focused tests for stage ordering, repeat and concurrent apply, crash recovery, stable receipt identity, clean-code requirement, missing/stale parent, blocked readiness, replay rejection, late cutoff, incomplete pairs, and missed freeze.
- Publisher and selection tests for absent authorization and each altered field, including the direct `--from-artifact` bypass; verify no transaction writes on failure and V4 fallback still works.
- Apply migration 0014 to an isolated test/Preview database, verify role grants and schema sync, then run focused Python tests, Ruff, `make contracts-check`, strict MkDocs, and `git diff --check`.
- Use fixtures or isolated Preview to exercise the operator. Operational 07/08/09/05 certification waits for stabilized Week 4 finals and is recorded in a later execution session with new immutable identities.

## Risks and definition of done

The candidate-preparation split must preserve the existing final source reconstruction; a local CSV or caller-supplied label must not bypass it. A partial R2 prefix is ineligible and requires a new run ID after diagnosis. The operator must not conceal the approval step by chaining preflight into apply. The V5 release record is a serving authorization, not a change to the research manifest or a claim of model superiority over V4.

- [ ] Manual stage CLI, status, retries, and negative gates pass.
- [ ] Exact release schema and final publication/selection checks pass; no production authorization row or activation was created.
- [ ] Candidate preparation, Preview/fixture rehearsal, focused tests, contracts, lint, and docs checks pass.
- [ ] Runbooks and implementation session log record the actual result; plan status changes to `Implemented` only after all items pass.

## Amendments

Record any change to authorization identity, stage ordering, evidence classes, preflight/apply separation, or production boundary here before implementation. A material change requires renewed Sol review.

## Implementation blocker (2026-09-25)

Terra found that the configured production `DATABASE_URL` authenticates as
`neondb_owner`. The approved design assumes the production publisher runs as a
restricted pipeline role with SELECT-only access to
`v5_serving_authorizations`. An owner connection can create or alter the
authorization row, so the planned database permission boundary is not
established. Implementation stopped for renewed Sol review. The smallest
proposed change is to provision and use a dedicated production pipeline role
with the required serving grants and SELECT-only authorization access before
any production V5 path is enabled. No production migration, authorization,
publication, or selection was performed. Preview migration 0014 is applied;
its authorization table is empty and its Preview role grants were verified.

## Approved amendment — production pipeline identity (2026-09-25)

**Reason and authority:** Renewed Sol review resolved the material conflict above. Read-only production inspection found `neondb_owner` as the configured production `DATABASE_URL` login, `cks_pipeline` as an existing NOLOGIN group, no `cks_prod_pipeline` role, and migration 0012 as the latest applied version. Migration 0013 and then 0014 are pending. The user explicitly selected provisioning the restricted role and applying 0014 in production in this milestone, with no authorization row, V5 publication, selection, or activation. This section supersedes the earlier exclusions of production migration and role setup; all other one-slate release and weekly-operator decisions remain in force. The blocker remains above as the historical reason implementation paused; this amendment is the approved design, not evidence that it has been executed.

### Ordered implementation

1. Review the paused, uncommitted implementation against this amendment. Keep `0014_v5_exact_release_authorization.sql` byte-identical: it was applied on Preview and its checksum is immutable. If a schema correction is necessary, stop for review and use a later append-only migration. Retain the existing plan's stage order, evidence classes, preflight/apply split, and exact release fields.
2. Add `scripts/ops/with_production_pipeline_env.sh`, analogous to the Preview wrapper. It reads only the `cks_prod_pipeline` production URL from macOS Keychain service `ckspicks-cfb/production/pipeline-url`, sets `DATABASE_URL` and `CFB_ARTIFACT_ENV=production`, and fails if the credential is absent. The owner URL remains an admin/migration credential; do not write the new URL to the repository, Vercel, shell history, or logs. Document the wrapper as the production V5 operator, publisher, and selection entry point.
3. Tighten the V5 database guard so production V5 publication and selection require both `session_user` and `current_user` to equal `cks_prod_pipeline`, including direct `publish_to_db.py --from-artifact` and direct selection calls. Preview V5 uses `cks_preview_pipeline`. Reject owner, migrator, web, wrong-branch, and changed-role sessions before any V5 prediction or selection write. Preserve the V4 production path and same-week V4 fallback.
4. With an admin-only production connection, create `cks_prod_pipeline` as a LOGIN, INHERIT role with a securely generated password and `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`; grant it membership only in the existing `cks_pipeline` group. Do not give it ownership, direct migrator/web grants, or schema/database CREATE. Store its branch-scoped URL in the Keychain item above and verify a fresh connection authenticates as that exact role. Inspect effective membership and privileges; stop if it has an unexpected admin path. The new role receives the existing serving rights through `cks_pipeline`, whose authorization-table grant is SELECT only.
5. After the user commits the reviewed migration file, inspect production `schema_migrations` and the pending list again. Apply only the expected 0013→0014 chain with the admin connection; stop on drift or an unexpected migration. Confirm the V4 serving view and active run remain unchanged and `v5_serving_authorizations` has zero rows. Through a real `cks_prod_pipeline` connection, verify serving write privileges, authorization SELECT, and lack of authorization INSERT/UPDATE/DELETE/TRUNCATE, table ownership, and schema/database CREATE. Verify `cks_prod_web` has no authorization-table access. Do not insert a release authorization or select V5.
6. Complete the original contract's code review, focused tests, Preview rehearsal, runbooks, and implementation log. Record actual role/migration evidence there. Keep the plan In Progress until both the original and amended definition-of-done checks pass.

### Additional acceptance and validation

- Negative tests cover owner, migrator, web, wrong-branch, and `SET ROLE`/changed-role production V5 connections at publisher and selection boundaries; each failure leaves prediction and selection tables unchanged. Tests also prove the restricted production role can perform required serving writes but cannot modify the authorization table, and V4 publish/rollback remains usable.
- Run the original contract's focused Python tests, Ruff, `make contracts-check`, strict MkDocs, and `git diff --check`; repeat the actual production grant and zero-row readback after migration. Inspect the migration list before applying, because production was at 0012 during planning and the runner applies all pending files.
- Production V5 authorization creation and activation still require a later, separate exact-packet decision. Do not treat role provisioning or schema migration as that decision.
