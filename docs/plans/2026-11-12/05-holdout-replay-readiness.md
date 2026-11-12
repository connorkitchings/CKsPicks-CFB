# 2026 holdout replay readiness

- **Status:** Draft
- **Created:** 2026-11-12
- **Planner:** Sol
- **Approval source:** Pending. The owner approved drafting this contract on 2026-11-12; exact-path approval to implement is the next gate. The export part cannot run before the 2026-12-13 final close.
- **Implementation log:** Pending (`session_logs/YYYY-MM-DD/NN-holdout-replay-readiness-impl.md`)
- **Commit policy:** Commit on local `dev` with implementation. Tooling and the export are separate steps: the tooling may land before the season ends; the export runs only after the final close.

## Goal and acceptance

The [research protocol](02-offseason-research-protocol.md) scores a frozen offseason candidate on 2026 exactly once, week by week, at the information available then. That needs every 2026 week's pre-kickoff inputs, the outcomes and the captured lines to be reproducible and hash-pinned. This contract makes that true without changing the 2026 record, any release or any model.

Acceptance:

1. **Every 2026 revision manifest can be re-prepared from its own pins.** For each of `w7_v1`, `w8_v1` to `w8_v3`, `w9_v1` to `w9_v3`, `w10_v1`, `w11_v1`, `w11_v2` (and the final close manifest once it exists), the exact score-reconciliation-exceptions file the manifest pins is recoverable and a prepare dry run reaches the pinned inputs without an `input checksum changed` failure.
2. **From the 2027 season on, each manifest pins its own immutable exceptions file**, so no in-place edit can invalidate an earlier revision.
3. **A frozen 2026 holdout export exists after the final close**, with a manifest of hashes: per week the pre-kickoff inputs the V5 run used (the revision manifest and every pinned input), the outcomes, and the captured lines (the early-week lines the record uses; the near-kickoff captures are included separately and labelled analysis only).
4. The export contains no information dated after its week's cutoff in the inputs for that week, and a test shows it.

## Baseline and constraints

- The limitation today ([weekly runbook](../../ops/weekly_runbook.md), step 1d, "Known limitation", owner-accepted 2026-10-25): `conf/season/2026/score_reconciliation_exceptions.json` is edited in place, and each manifest pins its SHA-256, so prepare fails for any manifest but the newest.
- **Verified 2026-11-12 (read-only):** the file's git history holds 5 commits and 5 distinct versions, and every manifest's pinned SHA-256 matches one of them (`w7_v1` at `2807e087`, `w8_*` at `fa1b2b61`, `w9_*` at `d8c5ac35`, `w10_v1` at `c3ee43ee`, `w11_*` at `e613add3`). The inputs are therefore recoverable. What has not been tried is a prepare dry run from a restored version.
- Released weeks are stored and unaffected; rollback reuses stored releases without reading the manifest. Out of scope: changing any 2026 release, the exceptions content, the Production database, or how the 2026 weeks run from here.
- The score-attribution repair under consideration ([contract 04 report](../../modeling/score_attribution_investigation_2026.md)) would change observations for the next model. A holdout export that holds the original inputs lets that repair be applied on top, without altering the frozen inputs.
- Stop gates: if a manifest's other pins (not the exceptions file) also fail to resolve, stop and report which; if a re-prepare needs a provider call, stop and ask.

## Ordered changes

1. **Recovery check (read-only).** For each manifest, restore its pinned exceptions version from git into a scratch path and verify the hash; run `run_season.py prepare` as a dry run in a disposable checkout (as the repo's release-parity tests do) and record the result. Output: a table in the implementation log, one row per manifest.
2. **Per-manifest exceptions pin (2027 and later).** Change the builder and the weekly controller so each new manifest pins a versioned file (for example `conf/season/<year>/score_reconciliation_exceptions_w<N>_v<K>.json`) that is written once and never edited. Acceptance: existing 2026 behavior and tests pass unedited; a new test proves an earlier manifest still prepares after a later week's exceptions change. This touches the weekly controller, so it lands only outside the Sunday and Monday windows and is validated in the 2027 Preview rehearsal before it is used in Production.
3. **Holdout export tool.** A read-only script that, for a given manifest list, copies or references each pinned input with its hash, adds the final outcomes and the captured lines, and writes an export manifest. Acceptance: running it twice yields identical bytes; the export carries no input timestamped after its week's cutoff.
4. **The export (after 2026-12-13).** Run the tool against the final close, store the export in the research bucket (blocked on provisioning `CFB_R2_LAB_*`; otherwise a local copy with its manifest hash recorded in the repository), and record the manifest SHA-256 in this contract and the backlog.

## Validation

- Task 1: each of the 10 current manifests either reproduces its pins or is listed with the reason.
- Task 2: tests for the builder and controller; `make check`; a Preview rehearsal before 2027 Production.
- Task 3: determinism and cutoff tests on a fixture season; `git diff --check`; `uv run mkdocs build --strict`.
- Task 4: re-run the export tool and compare hashes; confirm the near-kickoff captures are listed separately and flagged analysis only.

## Handoff/amendments

Approval and resume gate: the owner approves this path for implementation. Task 1 can run any time. Task 2 waits for a window outside the weekly runs. Task 4 waits for the 2026-12-13 final close and the research bucket. Record amendments here with reason, previous approach, revised approach and impact. Related: [near-kickoff line capture](01-near-kickoff-line-capture.md) (the captures included in the export), the [research protocol](02-offseason-research-protocol.md).
