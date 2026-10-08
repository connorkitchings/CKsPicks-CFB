# Repair-track certification and closure

- **Status:** In Progress
- **Approval:** User explicitly requested implementation of the complete updated plan after `04cd53ce` in this chat. This contract persists that approved scope; it does not authorize automatic Production activation.
- **Baseline:** `04cd53ce`; Stage 1 is closed. B2 successor chain, provider names, packet/staging tools, display-only Week 6 and frame-week policies already exist.
- **Implementation log:** `session_logs/2026-10-08/02-repair-track-certification.md`
- **Commit policy:** User-run commits; preserve unrelated work. No automatic merge, deployment or serving change.

## Goal and constraints

Complete the October 4 data-repair objective, independently certify the corrected chain, and prepare the Week 7 cutover. A separately approved limited release does not close this track. All six quality follow-ups and all incorrect values must be resolved for closure; verified missingness with correct exclusion and disclosure is acceptable. Retain the model design, B2 production fitting recipe, original prospective evidence and immutable source history. Do not include 2020 or fit/tune on 2026 outcomes.

## Ordered work and acceptance

1. Read c2 directly from R2: verify manifests, parent hashes, B2 bundle, predictions, selections, grades and release inputs. Replace scratchpad-only evidence; retain B1/c1 as superseded. Verify exact-commit CI/database jobs and deployed revisions. Run Production staging dry run and verify namespace, identity, bytes and rollback sources.
2. Exercise a successful Week 7 packet with verified Week 5 prospective evidence. Prove Week 6 cannot enter the prospective record, freeze or close; no other week is exempt. Preserve Week 5 exactly.
3. Add a seven-week integration fixture. After Week 6 certified finals stabilize, ingest/pin sources, extend 6A and Task 4, and build Weeks 0–6 frames. Preserve earlier content unless an attributed revision explains a change. Use successor B2 for Week 6 reconstruction, independently verify outcomes/quotes/grades/completeness/certification, and never fabricate an original run or post-kickoff historical quote. Do not use the original-run reconciliation stages for an unserved week.
4. Build pending Week 7 with fresh coverage. Rehearse Preview authorization, staging, selection, freeze, readback, rollback and matchup database gates against corrected snapshots/statistics. Production remains a separate exact decision; missed kickoff requires a revised operating decision.
5. Complete independent expected-request inventory (including never-scheduled requests), ingestion enforcement, ambiguous-version resolution, Gold checks/Silver receipts, blocking policy, durable receipts and legacy validation disposition. Resolve duplicate-play loss and scoring defects; independently verify all metric populations and values, reconcile the 95 database-only adjusted rows by key, complete 2025 matchup backfill, and add database-level null-lean publication coverage.
6. Reconcile status, decision brief, issue register and contracts into one completion matrix distinguishing delivered code, published artifacts, Preview selection, deployment and Production activation.

## Interfaces and validation

Retain delivered plan policies and packet/staging CLIs; add only needed Week 6 certification integration, with no public API redesign. Validate wrong bundle/parents, time boundaries, missing and conflicting sources, ambiguous pins, zero versus missing PPA, duplicate plays, null leans, seven-week operation, display-only exclusions and successful packet application/rollback. Run focused tests as each component changes, then applicable full Python/contract/web checks and exact-commit CI, including warnings-as-errors and database integration. Cloud evidence requires readback and idempotence; hashes alone do not prove numerical correctness.

## Completion matrix

| Requirement | State | Evidence / next gate |
|---|---|---|
| Direct c2 readback and B2 certification | Verified | 408 objects; six serving recomputations; independent B2 verifier; see `repair-track-evidence/` |
| Exact-commit CI and deployments | Historical baseline verified | `04cd53ce` CI passed and Production deployment `dpl_C32B…` was READY at that SHA. `main` has since advanced through PRs #5 and #6 to `07c53045` (web-only); CI and deploy verification for `07c53045` and the next commit are still open |
| Production staging dry run / rollback | Partial | Six replay staging dry run passed with no writes; complete cutover rollback/readback still open |
| Positive Week 7 packet / Week 6 exclusion | Partial | Signed synthetic Week 5 receipt passes packet validation and survives unchanged; actual Week 5 evidence and real Preview rehearsal still required |
| Seven-week fixture and Week 6 reconstruction | Partial | Seven-week frame build and independent verifiers pass; no original Week 6 artifact fabricated. Successor certification integration and stabilized live finals still required |
| Preview cutover and matchup database gates | Open | Pending Week 7 and corrected snapshot bindings |
| Six quality follow-ups | Partial | Independent-inventory input, required-check blocking, Gold schema/semantics and opt-in R2 readback delivered; inventory generation, automatic enforcement, ambiguity resolution, Silver receipts and legacy disposition remain |
| Duplicate plays / scoring / complete metrics | Open | Independently verified repair or truthful missingness. A draft play-identity design is saved at `drafts/byplay-play-identity.patch` and is **not applied**: it keeps distinct plays that share `(game_id, drive_number, play_number)`, which `byplay_v1` rejects as duplicate keys, and adds a `source_play_id` column that changes byplay content for every season. Adoption needs a read-only count over pinned Bronze plays for every B2 season, a `byplay_v2` identity schema, and attribution of every downstream change |
| 2025 matchup backfill | Open | Corrected lineage and serving gates |
| Null-lean database regression | Verified locally | Real PostgreSQL publication with quoted null/No Bet rows and valid controls; legacy model exercises shared persistence path, not V5 authorization |
| Documentation reconciliation | In progress | This matrix tracks remaining work |

## Decisions (2026-10-08 review)

- **Release gating:** a limited Production release is allowed once the corrected chain is certified and the Preview rehearsal passes, with open integrity items disclosed. Full track closure is a separate, later bar.
- **Week 7 checkpoint:** Sunday Oct 11 evening. If the successor Week 6 certification integration is not built and tested by then, move the cutover to Week 8; no gate is compressed.
- **Open, recommended default:** build rollback authorizations for the old runs as part of the Preview rehearsal (none exist today).
- **Open, recommended default:** Week 6 games whose only quotes are post-kickoff (the d2 snapshot was captured after some kickoffs; no Week 6 market-sources lock exists) are verified gaps with no selection or grade.
- **Quality gates:** Gold checks start at `warn`; releases promote them with `--require-check`. Requiring `ingest.capture_completeness` needs `--request-inventory`; without one the check uses the attempt ledger and is labelled `request_basis = attempt_ledger`.

## Amendment policy

Record mechanical findings here without changing acceptance. Material model, lineage, release, or evidence-policy changes require a new decision; never weaken a gate merely to finish. Mark Implemented only after all closure requirements pass. If future source availability prevents execution, retain In Progress and record the exact resume gate.

## Certification evidence and limits (2026-10-08)

The `repair-track-evidence/` directory replaces scratchpad-only c2 claims with
fresh immutable-object readback. The B2 verifier independently checked 35,740 states,
170,379 source game-role contributions, 377 FCS fallback states, and 7,192 calibration
rows per target. It exited successfully but emitted sklearn matrix arithmetic warnings;
this is not a warnings-as-errors pass. Six serving verifiers recomputed selections and
grades for 271 games. No cloud objects, database rows, authorizations or serving pointers
were changed. Production deployment identity is verified; live database selection and
matchup lineage are separate, still-open checks. B1 and c1 remain superseded evidence.

Stage 1 closure stands. This contract remains In Progress. Week 6 reconstruction waits
for certified finals and stabilization; software and broader audit work remain actionable
before that gate. No missing historical quote may be replaced by a later capture. Week 7
remains the target; missing its readiness/kickoff window requires a new operating decision.

### Local validation at this checkpoint

- 86 focused tests passed with warnings as errors, including real PostgreSQL transactions.
- All 35 6B flow tests passed with warnings as errors, including the seven-week fixture.
- Four audit-scope tests passed; the new receipt corruption regression passed in the 11-test library run.
- Whole-repository Ruff lint/format, shared contracts and registry validation passed.
- This is not full new-change CI, live database certification or production activation.
