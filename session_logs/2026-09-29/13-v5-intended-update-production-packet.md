# Session: Exact V5 intended-update production packet preparation

## TL;DR
- **Worked On:** Constructed the exact production artifact, authorization, selection, and rollback packet after the refreshed p2 Preview rehearsal.
- **Outcome:** A read-only production preflight matches all six current rollback IDs. Six proposed production run manifests, five scored manifests, six authorizations, and the model approval are checksummed in `docs/plans/2026-09-29/v5-intended-update-production-release-packet.json` (SHA-256 `deb1fd34ebd98410eedce6e7ae7088e54da95dd6d36ca6a1d7ac90a595781fcc`). Production has not been changed.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (Task 6).
- **Approval / Status:** Implementation and Preview were authorized. Exact production activation awaits the separate decision required by the contract.
- **Blockers:** Push/deploy reviewed code (local `main` is 12 commits ahead of `origin/main`), then verify deployed SHA; recheck live source and exact rollback state at decision time.
- **Next:** Obtain the user's exact packet decision only after code deployment is verified; then execute the ordered production transaction and readback if approved.

## Context and Decisions
- Preview and production intentionally use the same R2 bucket under launch contract Amendment 2; immutable `artifacts/preview/` and `artifacts/production/` paths distinguish run artifacts. The rating, bridge, forecast, serving, verifier, and Silver source objects are already readable by production. Only production-namespace prediction/scored files are proposed new R2 objects.
- Read-only production Neon shows migration 0018, zero successor authorizations, original selected runs for Weeks 0–5, and 94–105–3 spread / 87–78–0 total. The `.env` admin URL and Keychain restricted pipeline URL resolved to the same host and Week 5 selection; roles were `neondb_owner` and `cks_prod_pipeline` respectively.
- The p2 capture is timestamped `2026-09-29T20:28:55Z`. A `2026-09-30T02:10:51Z` source recheck had complete 112/112 provider quote coverage and six changed quote values across five games. The packet is a p2 snapshot, not a final market freeze; the final refresh remains due before kickoff.

## Work Completed
- Built deterministic production-namespace manifests from the exact signed Preview run/score bytes, changed only their environment-specific output URIs, and verified each proposed prediction artifact against its signed forecast/serving/verifier chain.
- Independently validated six exact production release records against the proposed production prediction bytes and shared immutable source objects. The 1,370-row rating projection passed its verified-source dry run.
- Read-only preflight of the six-week production batch matched every original selected run ID. Prepared the exact reverse rollback packet. No production R2 write, Neon authorization, rating projection, prediction/score publication, or selection was performed.
- Wrote a human-readable release decision document and the complete machine-readable packet with all hashes and run IDs.

## Files Modified
- `docs/plans/2026-09-29/v5-intended-update-production-release-packet.json` — exact proposed payload.
- `docs/plans/2026-09-29/v5-intended-update-production-release-packet.md` — decision summary and ordered execution.
- `docs/plans/2026-09-29/v5-intended-update-preview-rehearsal.md` — final p2 Preview evidence and corrected shared-bucket note.
- `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — implementation log pointer.
- This session log.

## Validation
- [x] Signed source chain and proposed production run/authorization validation for all six weeks.
- [x] 1,370-row rating projection dry run; production batch selector read-only preflight; admin/pipeline branch and role readback.
- [x] No successor production mutation; original selections and scores verified.
- [ ] Reviewed code push/deployment and public deployment SHA/readback.
- [ ] Separate exact release decision; production execution and post-switch readback.
- [ ] Final live market refresh and Week 5 freeze workflow.

## Amendments and Blockers
- The packet does not assert that current live lines equal the p2 snapshot. Six values moved in the later source check; keep the timestamped p2 release separate from the final market refresh.
- Production activation before the reviewed web code deploy would risk a mixed UI. Do not select the new runs until deployment is verified.

## Handoff Notes
- **Resume at:** Commit and push the packet/docs plus the 12 reviewed local commits, verify deployment, then present packet SHA `deb1fd34ebd98410eedce6e7ae7088e54da95dd6d36ca6a1d7ac90a595781fcc` for the user's exact release decision.
- **Watch out for:** The JSON packet's `decision_ref` is a stable reference to the pending decision section; its hash must not change after approval. Rebuild the packet if any game, artifact, or selected rollback ID changes. Do not grade Week 5.

**tags:** ["v5", "ratings", "production", "release", "packet"]
