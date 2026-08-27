# Session: R1 play-capture reliability hardening

## TL;DR

- **Worked On:** Implementing the approved Preview-only reliability amendment
  for successor R1 CFBD play capture.
- **Plan Contract:**
  `docs/plans/2026-08-27/r1-play-capture-reliability-hardening.md`
- **Approval / Status:** User explicitly authorized implementation in Codex on
  2026-08-27; implementation is in progress.
- **Blockers:** Full R1 capture remains paused until the new weekly capture-set
  path, migration, and verification gates are complete.

## Starting Evidence

- The old all-or-nothing 2015 play step stalled in CFBD TLS reads and left no
  completed-week capture evidence.
- The current Preview diagnostics include two user-terminated and two timed-out
  2015 play operations; their outer pipeline steps failed while their inner
  catalog ingestion runs remained `running`.
- No partial 2015 plays projection, Silver ref, V4 bundle, production state, or
  protected 2026 outcome was created.

## Handoff Notes

- **Implementation progress:** Added migration `0009`, deterministic request
  identities, a Preview-only sequential worker profile, request-attempt ledger,
  complete capture-set manifest, exact-manifest Silver dependency, and guarded
  reconciliation interface. Added the read-only 2015 Week 1 / 15,369-play
  compatibility probe; it uses the same worker but cannot write a capture,
  projection, or Silver ref.
- **Validation:** Focused catalog/ingestion/history-play/ops tests pass (35);
  full suite passes (554 passed, 2 skipped); coverage is 64% against the 60%
  gate; scoped Ruff, contracts synchronization, strict MkDocs, CLI help smoke,
  and `git diff --check` pass.
- **Not run:** Migration `0009`, abandoned-run reconciliation, Week 1 probe,
  and all CFBD historical capture remain intentionally unrun. The implementation
  must receive the user-controlled commit before any Preview data mutation.
- **Resume at:** Run the remaining contract-wide validation, then hand the
  implementation to the user for the required commit before any new Preview
  CFBD play capture.
- **Watch out for:** Do not reconcile a running ingestion record unless its
  owning outer R1 pipeline step is already failed; never use broad ingestion-run
  capture queries for successor R1 Silver construction. Do not use
  `--skip-capture` to resume an incomplete capture set.

**tags:** ["r1", "ingestion", "cfbd", "immutable-lake", "preview"]
