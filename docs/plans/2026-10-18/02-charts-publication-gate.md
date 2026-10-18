# Keep Charts unpublished behind an explicit flag

- **Status:** Implemented
- **Created:** 2026-10-18
- **Planner:** Sol, review chat
- **Approval source:** Owner's explicit “PLEASE IMPLEMENT THIS PLAN” request reproducing this plan in chat on 2026-10-18; off-everywhere default selected during planning.
- **Implementation log:** `session_logs/2026-10-18/05-charts-publication-gate-implementation.md`
- **Commit policy:** Owner-controlled; may commit with the existing uncommitted expansion after review. No staging, commits, integration or pushes by this implementation.

## Goal and acceptance

Allow Charts code to follow normal `dev` → `main` integration while Charts remains publicly unpublished pending owner manual review. `CFB_CHARTS_ENABLED` enables the UI only for the exact string `1`; unset, empty, `0` and invalid values disable it in every environment, including local development, Preview and fixtures.

A disabled deployment has no Charts navigation item or initial-render flash, four evenly spaced mobile items, and an actual HTTP 404 for direct `/charts` requests including query parameters. It must reject before chart parameters or data are loaded. Enabled local/Preview review has five navigation items and all existing Charts behavior. This publication flag does not change chart data production, model calculations, release projection sets or schema requirements.

## Baseline and constraints

Continue the dirty expansion worktree `.claude/worktrees/connorkitchings-charts-expansion` on `connorkitchings/charts-expansion`, based on `23621eb3`. Preserve all prior code, documentation, ignored receipts and the pre-existing staged static-file deletion. Primary `dev` has newer Week 8 operational commits through `1e821052`; do not integrate or overwrite them here.

Use the existing pure gate-helper/server-layout pattern. `SiteNav` is a client component, so resolve the flag on the server and pass a boolean; do not use a public client environment variable or an effect to hide links. The root loading boundary can stream responses, so verify actual HTTP status rather than merely asserting a not-found message.

No Vercel configuration changes, migrations, cloud-data reads, serving release operations or git mutations are in scope. Backend migrations and owner release approval remain separate. A published Charts UI remains explicitly unapproved.

## Ordered changes

1. Add one pure gate helper and truth-table unit tests; register them with publication tests.
2. Pass the server boolean from the root layout to `SiteNav`, defaulting closed. Hide Charts and use explicit four/five mobile grid classes. Preserve other navigation labels, links, active state and desktop alignment.
3. Gate `/charts` before awaits or queries. Keep rejection synchronous ahead of streaming where necessary for HTTP 404; retain the complete enabled implementation.
4. Explicitly enable the normal fixture test server. Add a separate disabled-mode production-build/browser test configuration, executed sequentially without reusing another server, and wire it into CI after the enabled suite. Use fixture data throughout.
5. Document explicit local/Preview opt-in, disabled Production settings and rebuild/redeploy requirements. Update the expansion contract, index and recovery handoff to supersede the prior blanket no-merge warning with this publication gate. Do not imply that migrations or Charts activation have been approved.

## Validation

- Unit cases: absent/empty/`0`/invalid/`1`, development/Production/Preview/fixture environments; only exact `1` enables.
- Enabled browser suite: five navigation items, Charts reachable, all existing chart tests pass.
- Disabled production-build suite: real HTTP 404 for `/charts` and query variants; no chart content or chart query errors; four correct desktop/mobile links and equal mobile widths; Picks, Results, Ratings and Performance work.
- Run publication tests, lint, typecheck, fixture production build and scoped/browser gate checks; strict documentation validation and `git diff --check`.
- Review the final flag diff, including default-closed behavior, streaming status, client serialization, CI process environment and server reuse. No Python/data revalidation is needed unless those components change.

## Handoff/amendments

After all local checks pass, this gate contract may be Implemented independently of the parent expansion's pending Preview acceptance. The parent remains In Progress and Charts manual/publication approval remains withheld. Retain exact validation evidence and proposed commit in the implementation log.

The gate supersedes the prior requirement for a charts-free source branch: code may merge with the flag off, subject to owner-controlled integration, required backend migration decisions and clean committed prepare/release rules. Before the weekly Production release, reconcile the newer Week 8 operational changes and validate the actual combined commit. This task does not perform that release.

Material architecture/scope/acceptance changes require owner review; mechanical adjustments preserving the contract are recorded here. Delegate implementation according to repository instructions and keep reviewers' ownership separate.
