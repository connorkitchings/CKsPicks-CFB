# V5-10: Historical Foundation Audit (Umbrella)

- **Status:** Draft
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the revised umbrella + 10a/10b plan with "go" on 2026-09-18. Status remains Draft per the documentation-authority gate; see Amendment 1 in the 10a contract.
- **Implementation log:** `session_logs/2026-09-18/05-v5-contract-10-umbrella-planning.md`
- **Commit policy:** Separate plan-package commit; user controls Git operations.

## Goal and entry gate

Audit the complete V5 foundation through 2025 before any 2026 application or
forecast verification. This umbrella refines the former single Contract 10 into
two ordered execution contracts:

- [10a: Audit specification, lineage inventory, and read-only harness](10a-v5-audit-harness-and-lineage.md)
- [10b: Full-corpus execution, independent evidence verification, and findings report](10b-v5-full-corpus-audit-execution.md)

The [common V5 contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
and historical-first reset are binding. The audit covers development seasons
2015–2019 and 2021–2025; 2020 and 2026 are excluded everywhere, and no 2026
data is read as model-development evidence. Contract 10 audits and reports; it
does not repair, retune, reselect, or modify artifacts. Existing artifacts
remain immutable regardless of findings; a failed independence check changes
permitted use, not historical bytes.

Contract 10 completes even when it discovers blockers; unresolved blockers
prevent Contract 11 from starting.

## Frozen audit boundary and evidence interfaces

Exact parents (resolve all source/output references recursively from these
manifests; invent no additional URIs):

| Stage | Run identity |
| --- | --- |
| Repair v2 | `repair-v2-20260909T1417Z` |
| Measurements | `possession-v1-measurements-20260915-18fb0aa-r6` |
| Ratings | `possession-v1-ratings-20260917-d029526-cert` |
| Forecasts | `forecast-v1-20260917-4600ddd-04b` |

Two confirmed structural facts are seeded into the preflight findings set;
their existence is established and is not rediscovered by the audit:

1. Repair v2's verifier imports and calls producer `compute_repair`.
2. Forecast verification does not reconstruct or compare stored forecast
   computations.

Contract 10 determines their affected scope, severity, disposition, and closure
criteria.

Artifact root:

```text
artifacts/research/data-first-football-v1/audits/historical-foundation-v1/runs/<run-id>/
```

Four versioned outputs (compact check summaries, counts, hashes, bounded
examples, and immutable evidence references — never embedded source/output
datasets; row-level exceptions use bounded samples plus the complete
affected-key digest and count):

- `evidence-register.json`: component, role, URI, raw/canonical SHA,
  code/config SHA, seasons, timing class, parent identities, outputs, row
  counts, declared permitted use.
- `check-results.json`: check ID, layer, category, status, expected/observed
  result, population, evidence references.
- `findings.json`: finding ID, severity, affected artifacts, evidence,
  permitted use, required action, closure criteria, blocking dependencies.
- `audit-manifest.json`: identity, exact parents, output hashes/counts,
  overall disposition, `production_activation_authorized: false`; written last.

Preview-only audit configuration and runner. Dry-run is the default; apply
requires committed code, a clean tracked worktree, matching code/config
hashes, and reviewed preflight evidence. No catalog, Neon, production, web,
V4, or historical-artifact writes are permitted.

Publication boundary: 10a may emit candidate check results and provisional
findings in local preflight evidence. It writes nothing to R2. Only 10b
publishes the final evidence register, check results, findings, and terminal
audit manifest.

Code/config verification resolves files from each artifact's recorded Git
commit, not from current working-tree bytes. Use the local Git object database
to hash the exact committed paths. A missing commit, missing historical path,
or hash mismatch is a blocking lineage finding. Never check out or modify the
worktree during this process.

## Findings, dispositions, and next gate

Severities:

- `blocker`: leakage, incorrect football meaning/population, untraceable
  lineage, unreproducible selection, missing required final fit, or verifier
  dependence where independent certification is claimed.
- `major`: material coverage/fallback/uncertainty weakness that could change
  interpretation.
- `minor`: bounded defect that does not change permitted artifact use.
- `info`: limitation or evidence note.

Dispositions: `eligible_for_next_contract`, `historical_evidence_only`,
`prohibited_until_closed`.

Contract 10 is complete when the audit evidence is published and every finding
has a disposition and closure criterion, even if blockers remain.

[Contract 11](11-v5-forecast-verification-closure.md) may begin only when:

- No upstream Repair, measurement, or rating blocker remains open.
- Forecast-related findings are either resolved by separately approved
  corrective contracts or explicitly incorporated into Contract 11.
- The audit manifest and independent audit-verification record agree exactly.

Required execution sequence:

1. Committed 10a code checkpoint.
2. Three identical no-write Preview preflights (same run ID, cutoff, expected
   code SHA, config SHA, parent URIs; canonical bytes/digests compared;
   elapsed time and progress events excluded from signed evidence; 3,600s cap).
3. Reviewed evidence-bound 10b apply (600s cap).
4. Independent re-read of all audit outputs and source hashes.
5. Idempotent repeat returning `already_applied`.
6. Human-readable report under `docs/research/`.
7. Lifecycle, roadmap, index, and session-log update.

Exceeding a runtime limit blocks publication and requires a performance
amendment. Separate corrective contracts are required for any blocker
involving code, methodology, schemas, or artifact replacement. Contract 01
remains an unrelated V4 diagnostic.

## Definition of done and amendments

- [ ] 10a harness built; three byte-identical no-write preflights pass.
- [ ] 10b full-corpus audit executed; four versioned outputs published in Preview.
- [ ] Every finding has severity, disposition, and closure criteria.
- [ ] Contract 11 entry gate explicitly evaluated and recorded.
- [ ] Report, lifecycle, roadmap, index, and session log updated.

Any change to boundary, parents, outputs, severities/dispositions, or gate
conditions requires a separately approved amendment before implementation.
