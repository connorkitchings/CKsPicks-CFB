# 2026 holdout replay readiness

- **Status:** In Progress (Phase 1 Tasks 1 and 3 implemented 2026-11-18; Task 2 and Task 4 pending). Approved (Phase 1: Tasks 1 and 3 approved 2026-11-18 for read-only in-season execution; Task 2 live-controller per-manifest exception pinning deferred to post-2026-12-13 alongside [Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md); Task 4 export runs after the 2026-12-13 final close)
- **Created:** 2026-11-12
- **Amended:** 2026-11-18 (split in-season read-only Tasks 1 & 3 from post-season live-controller Task 2 to isolate `weekly_automation.py` and `refresh_score_exceptions.py` during Weeks 13–15; see [repository review](../2026-11-18/repo-review-and-offseason-engineering.md))
- **Planner:** Sol
- **Approval source:** Owner approved Phase 1 (Tasks 1 & 3) and the Task 2 post-Dec-13 deferral in chat on 2026-11-18 ("1) A1 - yes, A2 - yes").
- **Implementation log:** `session_logs/2026-11-18/03-holdout-replay-readiness-impl.md` (Tasks 1 and 3; the check now covers 12 manifests, adding `w12_v1` and `w12_v2` at exceptions version `8145ebe8`, the sixth git version of the file)
- **Commit policy:** Commit on local `dev` with implementation. Tooling (Tasks 1 & 3), controller cutover (Task 2, post-2026-12-13) and the export (Task 4, post-2026-12-13) are separate steps.

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

Approval and resume gate: on 2026-11-18 the owner approved **Phase 1 (Tasks 1 and 3 only)** for in-season execution. Do not edit `scripts/ops/weekly_automation.py`, `scripts/pipeline/refresh_score_exceptions.py`, or `scripts/pipeline/build_season_revision.py` during Weeks 13–15: **Task 2** is explicitly deferred until after the 2026-12-13 final regular-season close alongside [Data architecture Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md). **Task 4** waits for the 2026-12-13 final close and the research bucket.

- **Amendment (2026-11-18):**
  - *Reason:* Keep the live weekly automation on `dev` completely untouched for the final three regular-season closes (Weeks 13–15), since git history already preserves every week's committed `score_reconciliation_exceptions.json` bytes.
  - *Previous approach:* Task 2 could land in any midweek window outside Sunday/Monday runs.
  - *Revised approach:* Split into Phase 1 (Tasks 1 and 3: read-only git-pin recovery verification and standalone read-only holdout export tool, authorized now) and Phase 2 (Task 2 controller/builder per-manifest exception pinning + [Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md), deferred until after 2026-12-13).
  - *Impact:* Zero live-pipeline blast radius in-season while preparing the holdout exporter ahead of 2026-12-13.

### 2026-11-19 export preflight

- The current export CLI rejects `w7_v1` before writing output. Of the 12 manifests through `w12_v2`, it is the only manifest whose top-level `captured_at` (October 14, 14:42 UTC) is later than its newest declared pre-week cutoff (October 13, 18:00 UTC). The November 18 pin recovery check proves the inputs can be recovered. This separate check concerns when an input was available. The other 11 manifests passed the exporter's current checks with the Preview reader, including hash and capture-time validation for their pinned market quotes.
- Preview R2 readback of the hash-pinned Week 7 schedule and quotes confirmed that all 610 Week 7 quote rows, covering 59 games, were captured after the cutoff. Four rows were at or after their game's actual kickoff. The exporter guard is still in force.
- Before Task 4, resolve Week 7 explicitly in this contract. Retain the original manifest and hashes as replay provenance. For a forecast-time market view, require each quote to meet its game's applicable cutoff and leave Week 7 market coverage missing unless earlier quotes with proven identity and timestamps are recovered. Verify football-input timing independently. Add a real-manifest regression test before rerunning the final export twice and recording its hash.

Related: [near-kickoff line capture](01-near-kickoff-line-capture.md) (the captures included in the export), the [research protocol](02-offseason-research-protocol.md), and the [2026-11-18 repository review](../2026-11-18/repo-review-and-offseason-engineering.md).
