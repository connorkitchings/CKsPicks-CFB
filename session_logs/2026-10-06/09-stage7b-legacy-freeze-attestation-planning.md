# Session: Stage 7B Legacy Freeze Attestation Amendment Planning

## TL;DR
- **Worked On:** Planned a narrow amendment for missing contemporaneous Week 5 freeze receipts.
- **Outcome:** Contract 04 Amendment 4, Appendix B's Week 5 attestation rule, and Stage 7B Amendment 1 are persisted for implementation review.
- **Plan Contract:** `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`
- **Approval / Status:** User approved the Option 1 amendment plan by saying “proceed”; contract amendment is approved for implementation planning, while all live operations remain separately gated.
- **Blockers:** Implement and verify the environment-specific retrospective attestation path; Production migrations 0023/0024, full release preflight, dynamic `N`, authorizations, rehearsal and cutover remain open.
- **Next:** User reviews and commits the contract changes. A fresh implementation task resumes the Stage 7B plan at the attestation implementation and evidence gates.

## Context and Decisions
- The Stage 7B preflight found contemporaneous database records for the original Week 5 live selection and freeze, but the historical freeze implementation did not create an immutable signed receipt. A bounded R2 search found no original receipt.
- The user approved Option 1, preserving the documented pre-kickoff evidence through a clearly retrospective `v5_legacy_freeze_attestation_v1` for Week 5 only.
- The repository's `signed_payload()` implements a canonical content checksum, not cryptographic signer authentication. The amendment names this accurately and binds the attestation to the approved decision reference and verified environment-specific registration execution identity.
- Preview and Production require separate source verification and attestations. The creation timestamp is generated at actual registration time; historical run, selection, freeze, and kickoff timestamps remain separately bound evidence.
- The existing non-null database columns and migrations 0023/0024 remain. The receipt URI points to the explicit legacy-attestation object for Week 5; the verifier and web provenance must recognize and label this kind. Later weeks keep the ordinary contemporaneous receipt.
- No migration, R2 write, prospective registration, authorization, selection, freeze, matchup publication, serving write, code change, or `docs/status.md` update is authorized by this planning approval.

## Work Completed
- Reviewed the Stage 7B preflight hold, Contract 04 and normative Appendix B, Stage 7B contract, migration 0023 trigger, prospective receipt helper, and v2 packet verifier.
- Recorded the exact payload fields, source re-derivation, user-run registration flow, packet verification, evidence labels, failure cases, and environment boundaries in Contract 04 Amendment 4 and Appendix B.
- Updated the Stage 7B contract with Amendment 1, clarified the original evidence gate, and retained the hold report as an accurate record of the pre-amendment state.

## Files Modified
- `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md` - Contract 04 Amendment 4.
- `docs/plans/2026-10-03/window2/release-schema-and-web.md` - Normative Week 5 legacy attestation requirements.
- `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md` - Stage 7B Amendment 1 and updated evidence gate.
- `session_logs/2026-10-06/09-stage7b-legacy-freeze-attestation-planning.md` - This planning record.

## Validation
- [x] `git diff --check`
- [x] `.venv/bin/python contracts/validation.py`
- [x] `.venv/bin/python -m mkdocs build --quiet`

## Amendments and Blockers
- Contract 04 Amendment 4 is the approved narrow policy change. It does not satisfy the implementation or environment registration gates by itself.
- No cryptographic operator-signature mechanism is claimed or introduced. If one becomes required, return to Contract 04 for a separate decision.

## Handoff Notes
- **Resume at:** Implement `build_legacy_freeze_attestation`, its independent verifier and registration operation in `src/cks_picks_cfb/ops/prospective_records.py`; add `scripts/pipeline/register_v5_legacy_freeze_attestation.py`; verify attestations in v2 packet preflight/apply; add clear Performance provenance labels.
- **Watch out for:** Re-capture the temporary read-only evidence before release packet preparation. Re-derive every source fact in each environment. Current selection does not prove the pre-kickoff designation. Production migration and all serving/authorization operations remain separately authorized.

**tags:** ["release", "stage7b", "attestation", "planning"]
