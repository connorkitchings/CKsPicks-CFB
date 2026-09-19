# Session: V5-10B Full-Corpus Audit Execution (part 1, incomplete)

## TL;DR
- **Worked On:** Began authorized 10B execution: corpus streaming engine, findings policy, `--full-corpus` runner mode, bounded-fixture tests, first full local dry run.
- **Outcome:** Engine runs end-to-end (562s, 92 checks) but the mandatory pre-apply review caught bugs in the new audit checks — no findings accepted, nothing published, no R2 writes. Work intentionally left uncommitted.
- **Plan Contract:** `docs/plans/2026-09-18/10b-v5-full-corpus-audit-execution.md` (Status: In Progress)
- **Approval / Status:** User authorized task 2; 10B remains In Progress with its DoD untouched.
- **Blockers:** Check-logic fixes required before rerun (see below); then review → apply → verify → report.
- **Next:** Fix the five check defects, rerun `--full-corpus` dry run, review every finding, then apply.

## Context and Decisions
- Corpus scale ~28.7M rows: only adjusted_history (24.2M), rating_states (2.1M), team_states (1M) truly stream; observations/possessions/scoring/priors/snapshots fit in memory but use the same streaming code path. Partition keys come from root manifests (output refs omit them for small sets).
- Design: `audit/corpus.py` (readers, population/ledger checks, findings policy), `audit/corpus_ratings.py` (adjustment/rating/forecast checks, orchestration), `--full-corpus` flag on the existing runner; full mode finalizes seeded findings, adds reconstruction record, enforces publication rules in apply.
- First dry run (`historical-audit-10b-20260918-full`, digest `a704e135…` — NOT accepted as evidence): 8 failed checks / 12 findings, of which review shows most are audit-side defects, plus one orchestration bug (seeded findings appended twice → 12 instead of 10; fix: assemble all findings in the runner, orchestrator returns corpus-only).
- Confirmed real data facts for the fixes: team names consistent; scoring categories are eligible/excluded/non-offense/OT/unresolved; duplicate source_event_ids are split-team attributions (not double counts); only 20 of 3,256 unresolved keys are nonzero; rating `cutoff_utc` uses `T` format vs space-format kickoffs.

## Work Completed
- `src/cks_picks_cfb/audit/corpus.py` (new): hash-verified readers, population/ledger checks, findings policy (severity/disposition/closure), behavioral finalization.
- `src/cks_picks_cfb/audit/corpus_ratings.py` (new): adjustment/rating/forecast checks, full-corpus orchestration, final-fit existence check.
- Runner `--full-corpus` mode + finalized-apply enforcement (provisional/severity/boundary/preflight-state refusal); config `rejected_seasons`.
- `tests/test_data_first_historical_audit_corpus.py` (new, 12 tests); fixed latent fixture digest bug it exposed.
- 10b contract Status → In Progress.

## Files Modified
- `src/cks_picks_cfb/audit/corpus.py`, `corpus_ratings.py` — new, uncommitted.
- `scripts/research/run_data_first_historical_audit.py` — uncommitted.
- `conf/research/data_first_football_v1/historical_audit_v1.yaml` — uncommitted.
- `tests/test_data_first_historical_audit.py`, `test_data_first_historical_audit_corpus.py` — uncommitted.
- `docs/plans/2026-09-18/10b-…md` — uncommitted (status only).
- `session_logs/2026-09-18/09-v5-10b-historical-audit.md` — this log, uncommitted.

## Validation
- [x] Focused: 73 passed (`-W error` equivalent run without coverage).
- [x] Ruff format + check clean on touched files; `git diff --check` clean.
- [x] Full-corpus dry run completes (562s, within 3600s cap); zero R2 writes (dry-run reads + local evidence only).
- [ ] Check-defect fixes + rerun + finding review (next session).
- [ ] Apply, independent verification, `already_applied` repeat, report, lifecycle updates (all pending).

## Amendments and Blockers
- Required check fixes (all in new code, none in 10a harness): (1) parse timestamps for cutoff/kickoff compare; (2) role pairing via opponent join; (3) unresolved leak only on nonzero sums; (4) score reconciliation as exceed-vs-shortfall (ledger must never exceed finals; shortfalls reported by season); (5) centering tolerance methodology (small early groups); (6) snapshot/terminal structural check + divergence as info; (7) single findings assembly in runner.
- Blocker: none structural. 10B DoD unchanged.

## Handoff Notes
- **Resume at:** Fix the seven items above, rerun `--full-corpus` dry run with `--run-id historical-audit-10b-<date>-full`, review every finding against raw data before any apply.
- **Watch out for:** Do not publish the `a704e135…` evidence — its findings are unreviewed and partly audit-side artifacts. Seeded 001/002 remain the only confirmed findings so far. Forecast final-fit absence (`max_training_season=2024`) is the one failure that survived scrutiny and is expected to become a real blocker.

**tags:** ["v5", "contract-10b", "implementation"]

## Continuation: accuracy-recovery checkpoint

- Corrected the first-run audit-side defects: UTC timestamp comparison,
  opponent-based offense/defense pairing, nonzero-only unresolved quarantine,
  excess-versus-shortfall score reconciliation, denominator-weighted league
  centering, snapshot/terminal structural assurance, and two-team team-state
  pairing.
- Finding generation now uses code-owned stage routing and stable IDs instead
  of text inference and ordinal execution order. The corpus orchestrator no
  longer adds duplicate seeded/forecast reconstruction findings; the runner
  owns final seeded-finding assembly.
- Added bounded regression coverage for the corrected cases. Focused audit,
  corpus, and documentation-authority tests pass (`107 passed`); scoped Ruff
  format/check and `git diff --check` pass.
- The next full-corpus dry run must wait for the user-controlled 10B code
  checkpoint. It must use a clean worktree and the new committed SHA; the
  earlier run bound to `c7ef6c8` remains diagnostic-only because the 10B code
  was then uncommitted.

## Continuation: direct-CLI import recovery

- The user committed the accuracy-recovery checkpoint as `b304b39`. A fresh
  read-only `--full-corpus` attempt bound to that exact SHA reached the frozen
  R2 parents, then stopped before corpus checks when the behavioral harness
  could not resolve its repository-qualified `scripts.*` verifier imports
  under direct CLI execution. It made no R2 writes and produced no accepted
  evidence.
- Moved the import-root guarantee to the generic behavioral harness, where it
  covers both direct runner execution and isolated harness invocation. Added a
  regression test that removes the root from `sys.path` before a dynamic
  verifier import.
- Validation: direct runner `--help`, `git diff --check`, scoped Ruff check
  and format check pass; the focused audit and corpus suites pass (`72
  passed`). A second user-controlled code checkpoint is required before the
  accepted full-corpus dry run can be bound to a clean SHA.

## Continuation: committed full-corpus dry run review

- A fresh read-only full-corpus run bound to clean checkpoint `f538ace`
  completed in local temporary storage with 92 checks and seven findings. It
  did not write R2. Its candidate evidence digest is
  `1d9f108d5ff3792c31e203c6a382cd78ecea204a0b49d085d1f9128296015571` and
  remains rejected diagnostic evidence because review found three more
  audit-engine errors.
- Corrected the audit checks rather than altering the candidate evidence:
  unresolved scoring now follows the offensive owner for defense rows;
  weighted four-pass centering preserves the iteration-zero league baseline
  rather than asserting a zero mean; and a rating state correctly uses its
  target game's kickoff as its cutoff. Added focused regression cases for all
  three conditions.
- The candidate score-ledger excess is a genuine data finding, not an audit
  error: 2015 Kentucky game `400603867` records 28 ledger points against the
  repaired final of 26, including two distinct two-point non-offense ledger
  increments. The Repair import-boundary blocker and forecast final-fit and
  reconstruction findings also remain candidates for the rerun.
- Validation after the corrections: focused audit and corpus suites with
  warnings as errors (`76 passed`), scoped Ruff check and format check, and
  `git diff --check` pass. The next accepted dry run requires a new clean
  user-controlled checkpoint and must not reuse the rejected candidate file.

## Continuation: bounded-memory centering recovery

- Replacement full-corpus attempts bound to `a59e451` stopped before emitting
  either a Python exception or candidate evidence, while the shared R2
  preflight completed successfully. The regression coincided with retaining
  separate baseline and adjusted numeric vectors in the 24M-row adjustment
  stream, so it is treated as an audit-engine memory defect, not historical
  evidence.
- The centering accumulator now retains only the exposure-weighted
  iteration-four-minus-iteration-zero delta. This is algebraically identical
  to the preserved-baseline test and avoids materializing both numeric vectors
  for each streamed group.
- Validation after the memory correction: focused suites with warnings as
  errors (`76 passed`), scoped Ruff check/format, and `git diff --check` pass.
  A clean committed checkpoint remains required before the next accepted full
  run.

## Continuation: streamed-path alignment

- The persistent-terminal full run bound to `ca4537b` completed in 499.52
  seconds and produced local candidate evidence
  `ec17c3805670238a94408b2d44edafd77059803b4b934a09a72f42968f9aba50`.
  It was not accepted because the streamed rating-state path retained the
  obsolete `cutoff < kickoff` assertion even though the direct check had been
  corrected. It also emitted a pandas `FutureWarning` when concatenating an
  empty partition.
- The streamed path now requires a state cutoff to equal its target kickoff,
  and independently checks that each game/candidate has exactly two team
  participants. Generic concatenation skips empty partitions, eliminating the
  warning without dropping nonempty evidence. Added a warning-as-error
  regression test for the empty-partition case.
- The candidate's other four failed checks remain substantive review
  candidates: Repair verifier dependence, 81 score-ledger excess keys,
  missing through-2025 final forecast fit, and forecast reconstruction
  absence. Validation after this correction: focused suites with warnings as
  errors (`77 passed`), scoped Ruff check/format, and `git diff --check` pass.

## Continuation: evidence-interface and target-semantics recovery

- The full-corpus check-results interface now requires explicit affected stages
  and fails closed when a check omits them. Final findings carry their stable
  source check ID and affected-artifact references; evidence verification
  rejects either field when absent.
- Population summaries now retain the per-season schedule, valid-outcome,
  forecast-eligible, and measurement-usable counts. Ledger checks now retain
  stable event-team and possession identities without rejecting legitimate
  split-team event attribution.
- Forecast checks now reconcile stored `actual` values to the repaired final:
  `margin = home_points - away_points` and `total = home_points + away_points`.
  This is a stored-output semantic check only; feature, offset, fitted-head,
  and calibration reconstruction remain assigned to Contract 11.
- Added regression coverage for duplicate ledger identities, forecast target
  semantics, and missing check-stage rejection. Focused audit suites pass with
  warnings as errors (`81 passed`); scoped Ruff format/check and
  `git diff --check` pass.
- **Next:** user-controlled code checkpoint, followed by a clean-SHA
  read-only full-corpus run and review of every result before any Preview
  publication. No R2 write occurred in this continuation.

## Continuation: pause and results-path clarification (2026-09-19)

- User requested that the full-corpus audit pause while the V5 path is
  reconciled against the actual goal: a defensible historical scorecard through
  2025 before any 2026 application. Two in-progress read-only runner processes
  bound to `787ae715` were stopped before either produced candidate evidence.
- The clean 10B code checkpoint is `787ae715`
  (`fix(research): harden V5 historical audit evidence checks`). The small
  read-only probe passed its 61 boundary checks except for the known Repair
  verifier-dependence condition; it made no R2 write. No full-corpus candidate
  is accepted and no audit artifact exists under the Preview audit prefix.
- The retained forecast artifact has stored historical prediction fields for
  2022–2025, including `actual`, `prediction`, `absolute_error`, and
  `gaussian_crps`. It is not independently reconstructed, so no V5 2025 metric
  is currently authoritative. Contract 12 is the scorecard contract, after 10B
  and Contract 11; 2026 remains deferred.
- Canonical roadmap, contract index, documentation home, and this execution
  contract now state this status explicitly. Next work should be replanned
  around the shortest defensible path to verified 2025 results, rather than
  continuing unconstrained full-corpus audit iteration.
