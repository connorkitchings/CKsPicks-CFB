# Session: V5-10a Audit Harness Implementation

## TL;DR
- **Worked On:** Implemented Contract 10a (audit config, lineage register, no-write harness, independence checker, audit verifier, runner + verifier CLIs, 44 new tests).
- **Outcome:** 55-test baseline reproduced; 44 new audit tests pass; full suite 1106 passed / 2 skipped; three byte-identical no-write Preview preflights; independent verifier passes; zero R2 writes confirmed.
- **Plan Contract:** `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md`
- **Approval / Status:** Explicit user handoff for the exact path; contract stays **In Progress** (Draft per authority gate) pending the user-executed code commit + post-commit preflight rerun.
- **Blockers:** User git commit outstanding (see Handoff Notes).
- **Next:** User commits the 10a code checkpoint; then rerun one preflight under the new HEAD to confirm identical evidence before 10b.

## Context and Decisions
- Branch `main`; worktree held only the plan-package files plus new 10a code. Nothing staged, committed, or discarded; no broad formatting.
- Planning confirmed `CFB_STORAGE_BACKEND=r2`; preflights read Preview R2 only (4 parent manifests + nested refs + existence probes, no dataset bytes).
- New isolated `src/cks_picks_cfb/audit/` namespace; harness restates (never imports) producer-mixed modules. Audit verifier (`verification.py`) uses stdlib + audit constants only.
- Amendment 1 (contract): status stays Draft under explicit handoff — the initial Approved label broke `test_historical_first_contracts_are_draft_and_gate_2026_application`; reverted with approval recorded.
- Preflight evidence digest `29235642…` (file SHA `f83fd876…` ×3). Timing/progress excluded from signed evidence by construction (elapsed only on stdout/stderr).

## Work Completed
- `conf/research/data_first_football_v1/historical_audit_v1.yaml` — Preview-only config, exact four parents + per-stage config paths, runtime caps, activation false.
- `src/cks_picks_cfb/audit/__init__.py` — schemas, seasons, severities/dispositions, restated stage/role contracts, sealed Repair counts, two seeded findings.
- `src/cks_picks_cfb/audit/register.py` — config validation, manifest reads, parent-URI graph (parents/identity keys only), register rows, Git-object-database code/config verification (no checkout).
- `src/cks_picks_cfb/audit/checks.py` — signature/identity/state/flags/parent-link/output-ref/row-count/season/code-config checks + provisional seeded findings.
- `src/cks_picks_cfb/audit/independence.py` — AST import-boundary scans (harness + 4 verifiers), Repair-import and forecast-reconstruction condition checks, verifier classifier.
- `src/cks_picks_cfb/audit/verification.py` — evidence + published-prefix verifiers, gate arithmetic.
- `scripts/research/run_data_first_historical_audit.py` + `verify_data_first_historical_audit.py` — dry-run/apply/verify CLIs with standard gates.
- `tests/test_data_first_historical_audit.py` — 44 tests: config, register, negatives, season fixtures, independence, verification, runner gates, published round-trip.
- Fixed during implementation: manifest mutation breaking signatures (runner no longer annotates manifests); parent-link SHA keys per real identity fields; season gate skipping the `forbidden_seasons` declaration; forecast `read_bytes(manifest_uri)` classified as metadata validation.

## Files Modified
- `conf/research/data_first_football_v1/historical_audit_v1.yaml` — new.
- `src/cks_picks_cfb/audit/{__init__,register,checks,independence,verification}.py` — new.
- `scripts/research/{run,verify}_data_first_historical_audit.py` — new.
- `tests/test_data_first_historical_audit.py` — new (44 tests).
- `docs/plans/2026-09-18/10a-…md` — status/amendment/DoD state; `10-…md`, `10b-…md`, `docs/plans/index.md` — Draft labels.

## Validation
- [x] 55-test baseline reproduced before new coverage (55 passed).
- [x] New audit tests: 44 passed; focused set 50 passed with `-W error`.
- [x] Full suite: 1106 passed, 2 skipped.
- [x] `ruff format --check` + `ruff check` clean on all 8 new/changed code files.
- [x] `contracts/validation.py` passed; `mkdocs build --strict` passed; `git diff --check` clean.
- [x] Three identical no-write preflights (`--run-id historical-audit-10a-20260918-preflight`, cutoff `2026-09-18T12:00:00Z`, code `d3a2deb…`): 44 checks, only expected `independence.repair.boundary` fail; both seeded conditions confirmed; register reconciles pinned SHAs (`b55af0dd…`, `18fb0aa…`, `7568c910…`, `4600ddd…`) and 8936-game population agreement.
- [x] Independent verifier passes on preflight evidence; gate correctly reports `contract11_permitted: false` (forecast findings pending).
- [x] Zero R2 writes confirmed (audit prefix lists empty).
- [ ] Committed 10a code checkpoint (user git) + post-commit preflight rerun.

## Amendments and Blockers
- Amendment 1 in 10a contract (Draft status under explicit handoff; authority gate preserved).
- Blocker: none for code. Procedural: the code commit is user-executed. Committing changes HEAD, which changes the evidence identity's `code_sha`, so after the commit Terra must rerun the preflight (one run suffices to confirm byte-identical evidence modulo the new SHA) before 10b's evidence-bound apply.

## Handoff Notes
- **Resume at:** User commits 10a files, then fresh Terra task: rerun preflight under new HEAD, confirm digest stability, proceed to `docs/plans/2026-09-18/10b-v5-full-corpus-audit-execution.md` (still Draft; needs its own authorization).
- **Watch out for:** Preflight evidence lives at `/var/folders/b5/wrh935896v148pd_2rvkcbz00000gn/T/opencode/audit-10a-preflight-{1,2,3}.json` (local only, digest `29235642…`). Do not publish anything to R2 during 10a. Never check out the worktree during historical commit hashing.

**tags:** ["v5", "contract-10a", "audit", "implementation"]
