# V5-10a: Audit Specification, Lineage Inventory, and Read-Only Harness

- **Status:** In Progress
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User approved the revised umbrella + 10a/10b plan with "go" on 2026-09-18, explicitly authorized 10a implementation, and on 2026-09-18 approved the 10a-reclosure plan (Amendment 2) with four corrections.
- **Implementation log:** `session_logs/2026-09-18/06-v5-10a-audit-harness.md` (code checkpoint `bdf3ba7`; post-commit preflight rerun confirms byte-identical evidence under the committed SHA)
- **Commit policy:** Separate code checkpoint; user controls Git operations.

## Goal

Build the audit specification, complete lineage inventory, and read-only
harness for the Contract 10 historical-foundation audit. The
[umbrella](10-v5-historical-foundation-audit.md) and
[common V5 contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
are binding. 10a ends with three deterministic, byte-identical read-only
preflights. It does not publish findings or repair code.

## Current state

Parent identities, artifact root, output names, publication boundary, and the
two seeded structural findings are frozen by the umbrella. Established
precedent to reuse: generic storage readers (`data/lake.py`,
`data/storage/`, `data/schema_contracts.py`), hash-pinned signing
(`data_first_phase2d.signed_payload` / `verify_signed_payload`), manifest
conventions, and dry-run-default runners. The focused foundation baseline is
55 passing tests:

```bash
uv run pytest -q --no-cov \
  tests/test_data_first_repair_v2.py \
  tests/ratings/test_possession_verification.py \
  tests/test_possession_rating_verification.py \
  tests/test_data_first_forecasts.py \
  tests/test_forecast_calibration.py \
  tests/test_forecast_verification.py
```

Reproduce those 55 before adding audit coverage; new audit tests increase
that count.

## Proposed approach

New isolated `src/cks_picks_cfb/audit/` namespace plus Preview-only
`scripts/research/run_data_first_historical_audit.py` (runner) and
`verify_data_first_historical_audit.py` (audit verifier), with configuration
`conf/research/data_first_football_v1/historical_audit_v1.yaml`. The harness
uses generic storage readers, schema contracts, and signing utilities only.

## Scope

### Included

- Audit configuration, runner, and read-only harness.
- Evidence-register builder and parent/output graph (source eligibility
  through forecasts).
- Manifest/signature/hash/parent/schema/row-count/digest verification.
- Season gate and verifier-independence checks.
- Candidate check results and provisional findings in local preflight
  evidence only.

### Excluded

- Any R2 write (10a writes nothing to R2; only 10b publishes final outputs).
- Full-corpus check execution beyond what preflight needs (belongs to 10b).
- Repair, retuning, reselection, or artifact modification.
- Catalog, Neon, production, web, V4, or historical-artifact writes.

## Affected components and contracts

- New: `src/cks_picks_cfb/audit/`, `scripts/research/run_data_first_historical_audit.py`,
  `scripts/research/verify_data_first_historical_audit.py`,
  `conf/research/data_first_football_v1/historical_audit_v1.yaml`.
- Read: Repair v2, R6 measurement, retained-rating, and 04b forecast
  manifests plus their recursive parents; `data/lake.py`,
  `data/schema_contracts.py`, `data/data_first_phase2d.py` (signing).
- Tests: import-boundary tests for the harness and every assessed verifier;
  negative and deterministic-fixture tests listed below.

## Implementation tasks

### Task 1 — Audit configuration and runner skeleton

**Files:**

- `conf/research/data_first_football_v1/historical_audit_v1.yaml`
- `scripts/research/run_data_first_historical_audit.py`

**Changes:**

- Preview-only config: schema version, environment `preview`, exact four
  parent URIs, eligible seasons 2015–2019 and 2021–2025, forbidden 2020/2026,
  artifact root, runtime caps (preflight 3,600s; apply/verify 600s each),
  `production_activation_authorized: false`.
- Runner with standard flags (`--run-id`, `--expected-code-sha`,
  `--environment preview`, `--as-of`, `--config`, parent URI flags);
  dry-run default; `--apply` requires committed code, clean tracked worktree,
  matching code/config hashes, and `--preflight-evidence` of reviewed
  byte-identical preflights.

**Acceptance criteria:**

- Non-Preview environment is rejected; apply without all four gates is refused.
- Three preflights with the same run ID, cutoff, expected code SHA, config
  SHA, and parent URIs produce byte-identical canonical evidence.

**Validation:**

- CLI gate tests; `git diff --check`.

### Task 2 — Lineage inventory and evidence register

**Files:**

- `src/cks_picks_cfb/audit/register.py` (new)

**Changes:**

- Recursively resolve every source/output reference from the four parent
  manifests into a complete parent/output graph from source eligibility
  through forecasts.
- Emit candidate `evidence-register.json` rows: component, role, URI,
  raw/canonical SHA, code/config SHA, seasons, timing class, parent
  identities, outputs, row counts, declared permitted use.
- Code/config SHAs resolve files from each artifact's recorded Git commit via
  the local Git object database — never current working-tree bytes. Missing
  commit, missing historical path, or hash mismatch is a blocking lineage
  finding. Never check out or modify the worktree.

**Acceptance criteria:**

- Every claimed input, transformation, output, cutoff, and artifact maps to
  executable code at its recorded commit and an immutable source ref.
- Unregistered or identity-mismatched evidence fails closed.

**Validation:**

- Register unit tests with deterministic manifest fixtures; missing-commit
  and hash-mismatch negatives.

### Task 3 — No-write verification harness

**Files:**

- `src/cks_picks_cfb/audit/checks.py` (new)

**Changes:**

- Verify every manifest signature, identity, code/config hash, parent URI,
  output reference, schema, row count, and digest.
- Enforce eligible seasons and reject 2020/2026 in every reference, including
  nested ones.
- Stream large partitioned datasets; never embed full datasets in JSON —
  compact summaries, counts, hashes, bounded examples, and immutable refs;
  row-level exceptions use bounded samples plus complete affected-key digest
  and count.
- Fail closed on missing, unreadable, unsigned, unregistered, or
  identity-mismatched evidence.
- Seed the two confirmed structural findings (Repair verifier producer
  import; forecast-output reconstruction absent) into the provisional
  findings set; 10a determines no severity — 10b does.

**Acceptance criteria:**

- All negative cases (wrong parents, changed hashes, missing partitions,
  corrupt records, forbidden seasons, score-ledger imbalance, role reversal,
  duplicate games) are detected.
- 10a emits only local preflight evidence; zero R2 writes.

**Validation:**

- Negative tests for each case; deterministic fixtures for FBS–FBS, FBS–FCS,
  missing measurements, first-season fallback, 2019→2021 carryover,
  OT/non-offense scoring, calibration chronology.

### Task 4 — Verifier-independence checker

**Files:**

- `src/cks_picks_cfb/audit/independence.py` (new)

**Changes:**

- Static import-boundary scan: the audit harness must not import Repair,
  possession, rating, or forecast producer computations; assessed verifiers
  must not import their producers.
- Behavioral assurance matrix: for each assessed verifier (Repair,
  measurement, rating, forecast), all four cases must execute
  deterministically — wrong parent, missing dataset, corrupted output, and
  self-consistent producer-only perturbation. A case passes when the
  verifier's observed behavior matches the expected behavior for that case;
  Repair and forecast verification are already expected to fail parts of the
  matrix.
- A verifier's classification must match its observed boundary and behavioral
  results; it is independent only when the boundary holds and every
  behavioral case behaves as expected for an independent verifier. Every
  failure is converted into a fully specified provisional finding (severity
  assigned by 10b). A failed assessed verifier never blocks closure of the
  audit harness itself; the audit reports defects but does not repair the
  assessed producers.
- Audit verifier scope (implemented here, exercised in 10b): may import only
  audit schemas/constants, generic storage readers, and signing utilities —
  never the audit runner or check implementations. It verifies exact parent
  bytes, output bytes/hashes, manifest-last publication, internal
  count/findings consistency, source-reference existence, and
  disposition/gate arithmetic. It does not claim to recompute every
  football-semantic check.

**Acceptance criteria:**

- A verifier is classified by matching its classification to its observed
  boundary and behavioral results, per the matrix above. Existing
  certification labels do not override this standard.

**Validation:**

- Import-boundary tests for the harness and every assessed verifier
  (Repair, measurement, rating, forecast); false-certification-claim tests.

## Testing strategy

Reproduce the 55-test baseline first, then add: import-boundary tests,
negatives (wrong parents, changed hashes, missing partitions, corrupt
records, forbidden seasons, future/same-game leakage, ledger imbalance, role
reversal, duplicates, false certification), and deterministic fixtures listed
in Task 3. Focused tests run with warnings as errors; then full Python suite,
scoped Ruff, schema/contract validation, strict MkDocs, `git diff --check`.

## Risks and edge cases

- Comparing against working-tree config instead of recorded commits would
  silently validate the wrong code — blocked by Task 2's Git-object-database rule.
- Embedding row-level evidence would bloat outputs — blocked by the compactness rule.
- Progress timing leaking into digests would break determinism — elapsed time
  and progress events are excluded from signed evidence.

## Definition of done (reclosure)

- [x] 55-test baseline reproduced; new audit tests added and passing (44 new; full suite 1106 passed).
- [x] Committed 10a code checkpoint (`bdf3ba7`) + post-commit preflight rerun under the committed SHA (evidence identical except `code_sha`).
- [x] Header duplication removed (planning step); lineage traversal is cycle-safe and exhaustive with every nested edge preserved; unreadable/untraceable nodes fail closed.
- [x] All 16 behavioral-assurance cases execute deterministically (55 audit tests green); each verifier's classification matches the observed boundary and behavioral results; every failure is converted into a fully specified provisional finding (zero mismatches; dependence carried by seeded findings).
- [x] Publication interface hardened (rejected seasons declared; provisional output rejected; exact idempotence; final-manifest enforcement; verifier rereads parent bytes) without any R2 write.
- [x] Three new byte-identical no-write Preview preflights (61 checks; digest `a26ba122…`; only expected `independence.repair.boundary` fail), independently verified; local candidate evidence only; zero R2 writes.
- [x] No findings published; no code repaired.
- [ ] Session log corrected and extended; user commit + post-commit rerun pending; `git diff --check` clean.

## Amendments

### Amendment 1 — Status lifecycle vs the authority gate

**Reason:** The persistence step initially marked this contract Approved, but
`test_historical_first_contracts_are_draft_and_gate_2026_application` pins the
umbrella 10/11/12 contracts to Draft until their gates clear.

**Original approach:** `Status: Approved` on the persisted contract.

**Revised approach:** The authority pin covers only the umbrella
10/11/12 files, not the 10a/10b execution contracts, so 10a executed under
the explicit user handoff and moved to `Implemented` once every
definition-of-done item passed (committed checkpoint `bdf3ba7` plus
post-commit preflight rerun). The umbrella 10 stays Draft per the gate. No
architecture, scope, or acceptance change.

**Impact:** Authority suite stays green; 10a execution record is closed.

### Amendment 2 — 10a reclosure: assurance gaps (2026-09-18)

**Reason:** Post-close review found the 10a label premature: duplicated
header fields, depth-limited lineage traversal without nested edges, static
only verifier assurance, a publishable non-final manifest, run-only
idempotence, no evidence-digest reconstruction or parent-byte reread in
verification, and gate logic conflating disposition with closure. The
implementation itself was directionally correct; the assurance standard was
not met.

**Original approach:** 10a Implemented at checkpoint `bdf3ba7`; behavioral
tests as an undifferentiated requirement; publication validity and the
Contract 11 gate treated as one decision; only 2020 declared forbidden.

**Revised approach (user-approved with four corrections):**

1. Reopen 10a to `In Progress`; fix the header; preserve the earlier
   completion claim as history. Exhaustive cycle-safe traversal replaces the
   depth limit; every nested manifest, parent, and output edge is recorded.
2. The 16-case behavioral matrix must execute deterministically with
   classifications matching observed results; failures become provisional
   findings and never block harness closure.
3. Publication validity (independent verification agreement) is decided
   separately from the Contract 11 gate (finding closure). The contract
   publishes exactly four outputs; the verification record remains
   local/session-log evidence carrying the verified manifest hash.
4. Findings carry `closure_state` (`open`/`closed`/`incorporated_into_contract_11`)
   alongside severity and disposition. Contract 11 requires all upstream
   blockers closed, all forecast findings closed or incorporated, and exact
   manifest–verification agreement.
5. The config declares `rejected_seasons: [2020, 2026]` alongside the
   unchanged development seasons; the season gate enforces both everywhere.

**Impact:** Terra task 1 closes these gaps with zero R2 writes, then three
new preflights under a new committed SHA return 10a to Implemented. Terra
task 2 (10b) follows. Contract 11 remains Draft throughout.

Mechanical fixes stay in-contract. Changes to boundary, parents, outputs, or
independence standard require a user-approved planning amendment.
