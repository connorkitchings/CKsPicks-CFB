# Session: Advance Mode and registered-release rollback for the Week 7 cutover

## TL;DR
- **Worked On:** the cutover packet could not open Week 7 (no selection yet) or roll back to the real old runs; both fixed per the user's approved design.
- **Outcome:** Advance Mode (select 0..N, move `current_week` N-1 to N; rollback deletes the Week N selection, owner login only); rollback packets carry the runs' registered authorizations and up to two registered bundle approvals, with no fresh finals certification; read-only export tool for the registered rows.
- **Plan Contract:** `docs/plans/2026-10-08/02-repair-track-certification-and-closure.md` Amendments 5 and 6.
- **Approval / Status:** user approved Advance Mode, the owner-login rollback and the rollback-authorization update in-session (2026-10-10); not yet exercised in Preview.
- **Blockers:** Preview registered rows unchecked; Week 6 market-sources lock still has no tool.
- **Next:** Preview rehearsal on Monday; Week 6 pins and 6A/6B extension once finals stabilize.

## Context and Decisions
- Production already holds an authorization for every selected run and two bundle approvals (Weeks 0-5 `30c4f1eb…` first live 5; Week 6 `a507d0c7…` first live 6). The "none exist" note in the repair-track contract was wrong; the gap was carrying them into a packet (read-only check as `cks_prod_pipeline`).
- Rollback packets drop completed-week certifications: restoring history needs no fresh finals, and the display-only Week 6 can never be certified.

## Files Modified
- `src/cks_picks_cfb/ops/v5_batch_selection_v2.py`, `public_selection.py` (`deselect_week_run`), `v5_packet_builder.py`; `scripts/pipeline/build_v5_cutover_packets.py`, `export_v5_registered_releases.py` (new).
- Tests: `tests/test_v5_advance_mode.py`, `tests/test_v5_rollback_registered.py` (new); `tests/test_v5_batch_selection_v2.py` (helper skips weeks absent from the before-state).
- Docs: contract Amendments 5-6, `docs/plans/2026-10-10/01-week7-cutover-run-sheet.md`.

## Validation
- [x] `ruff check`, `ruff format --check`, `make contracts-check`.
- [x] Parallel suite with `-W error`: 2,438 passed, 3 skipped.
- [x] Postgres integration files against a scratch PostgreSQL 14: 28 passed, 1 failed. `test_publish_null_lean_database.py::test_null_lean_with_quotes_persists_no_selection` fails ("conflicting immutable market snapshot") on the committed baseline too, so it is not from this work (CI uses PostgreSQL 16; cause not investigated).
- [ ] 6B flow test, web checks, Preview rehearsal.

## Handoff Notes
- **Resume at:** run `export_v5_registered_releases.py --environment preview` for the Preview selected runs; build Preview advance and rollback packets for the rehearsal.
- **Watch out for:** the advance rollback must run under the owner/migrator login; the scratch Postgres used for tests lives in the session scratchpad.

**tags:** ["week7", "cutover", "release", "rollback"]
