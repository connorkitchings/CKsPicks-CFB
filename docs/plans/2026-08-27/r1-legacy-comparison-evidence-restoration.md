# R1 Legacy 2019 Comparison-Evidence Restoration

- **Status:** In Progress
- **Created:** 2026-08-27
- **Planner:** Sol
- **Approval source:** User explicitly approved the narrow Preview-only
  restoration described in the active Codex task on 2026-08-27.
- **Implementation log:**
  `session_logs/2026-08-27/14-r1-legacy-comparison-evidence-restoration.md`
- **Commit policy:** Commit with implementation before any Preview write.

## Goal

Restore the exact pre-existing 2019 games and teams archives as immutable,
catalog-validated *legacy comparison-only* refs in Preview, and derive the
corresponding `game_outcomes` ref from the exact games capture. Observable
success is one immutable restoration manifest that records the original source
URIs/checksums, Preview capture IDs, and three validated ref identities so R1's
existing automatic comparison bootstrap can proceed without an override.

## Current State

R1's committed Preview preflight correctly failed before capture because
`catalog.dataset_versions` contains no validated 2019 legacy versions. The
failure report is
`artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260827-95b0456/comparison-ref-set.failure.json`.

The configured read-only historical source still contains exact legacy files:

- `raw/games/year=2019/data.csv`: 848 rows; SHA-256
  `127b0a201b7793d25159a02ecfa29d83f46f40a6899106bb7f61438e660e3db5`.
- `raw/teams/year=2019/data.parquet`: 130 rows; SHA-256
  `655b71a08c510f95db9e81cc6c21aca4052dac889cf8e17cbb00d130ce294c22`.

The games archive contains final home/away points, so `game_outcomes` can be
derived deterministically using the existing Silver builder. This is a
restoration of exact archive evidence, not a CFBD recapture and not a
successor-v2 parent.

## Proposed Approach

Add a Preview-only restoration command with a fixed two-object source allowlist.
It inventories and checksum-verifies those source objects, copies their records
once into immutable Preview Bronze observations using the existing historical
import primitive, and builds `games`, `game_outcomes`, and `teams` solely from
the resulting exact capture IDs. It writes all refs and its manifest under an
isolated `artifacts/preview/legacy-comparison/2019/` namespace. The command
rejects any changed source checksum, duplicate or missing capture, 2020 data,
non-Preview runtime, raw destination, or changed manifest collision.

## Scope

### Included

- Read-only verification of the two exact 2019 source archives.
- Preview Bronze capture registration for only those exact source records.
- Manifest-scoped legacy Silver builds for `games`, `game_outcomes`, and
  `teams`, plus catalog registration and one restoration manifest.
- Tests, R1 contract amendment, runbook/session documentation, and Preview
  execution verification.

### Excluded

- Any source R2 mutation, `raw/*` write, 2020 data, production Neon/R2,
  V4/candidate-v1 changes, market data, recapturing CFBD, or R1 successor
  source-set ancestry.
- Plays, venues, or team-game statistics; they remain optional revision
  diagnostics and are not required for the hard comparison gate.

## Affected Components and Contracts

- New restoration CLI/script and exact-manifest Silver input interface.
- `catalog.source_captures` and `catalog.dataset_versions` on Preview only.
- `artifacts/preview/legacy-comparison/2019/` immutable refs and manifest.
- R1's existing automatic catalog resolver; no CLI override and no change to
  successor source-set parents.

## Implementation Tasks

### Task 1 — Implement exact-archive restoration

**Changes:**

- Encode fixed source URI/SHA-256 expectations for the two source files.
- Require `CFB_STORAGE_BACKEND=r2`, Preview runtime, Preview/source isolation,
  and a clean committed implementation before any write.
- Use the existing historical import primitive only for the allowlisted objects;
  retain their source URI, source checksum, and original source metadata in
  each immutable Bronze observation.
- Emit a `legacy-comparison-2019-source-set-v1` manifest and make Silver
  construction consume only its capture IDs, never broad catalog discovery.

**Acceptance criteria:** A rerun is byte-identical or fails on collision; an
altered source object, wrong environment, missing object, or extra capture
fails before a comparison ref is published.

### Task 2 — Build and freeze comparison refs

**Changes:**

- Build `games`, `game_outcomes`, and `teams` from the manifest-scoped
  captures under `artifacts/preview/legacy-comparison/2019/refs/`.
- Register only validated refs and write a manifest binding source evidence,
  captures, refs, code SHA, and config SHA.
- Verify that all refs have season 2019 partitions and non-successor URIs.

**Acceptance criteria:** The existing R1 comparison bootstrap resolves the
three 2019 refs automatically, while the restored refs do not appear in any
successor R1 source-set or V4 lineage.

### Task 3 — Verify and resume R1 gate

**Changes:**

- Run focused and full validations, then execute the Preview restoration under
  a new committed run ID.
- Rerun R1 preflight under a new R1 run ID and verify it freezes a complete
  comparison manifest before any successor capture begins.

**Acceptance criteria:** The previous failure is superseded by a complete
comparison manifest; subsequent R1 capture remains separately resumable and
still stops on every existing R1 coverage/lineage gate.

## Testing Strategy

- Unit-test source allowlisting/checksum enforcement, Preview-only refusal,
  immutable collisions, exact capture-set selection, and 2020 rejection.
- Integration-test restored ref schemas/partitions, outcome derivation,
  catalog registration, and automatic R1 resolver selection.
- Run focused data/catalog/ops tests, full pytest, Ruff, contract validation,
  strict MkDocs, CLI help, and `git diff --check`.

## Risks and Edge Cases

- Historical archives are 2026-observed reconstruction evidence; manifests
  must not claim historical capture time.
- The restoration must never fall back to a matching catalog capture from
  another source, run, or season.
- A later revised copy of either archive must fail checksum validation rather
  than silently changing comparison evidence.

## Definition of Done

- [ ] Exact source files and checksums are verified.
- [ ] Preview-only immutable captures and three cataloged comparison refs exist.
- [ ] Restoration manifest is immutable and R1 auto-preflight resolves it.
- [ ] Required validation and documentation pass with no raw/V4/production write.
- [ ] This contract and the R1 parent contract record the result.

## Amendments

Material changes to the source allowlist, checksums, lineage role, or use of
restored refs require a new Sol review.
