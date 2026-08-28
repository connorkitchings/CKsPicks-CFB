# Session: R1 Legacy 2019 Comparison-Evidence Restoration

## TL;DR

- **Worked On:** Planning the approved exact-archive restoration required to
  unblock R1 comparison evidence.
- **Outcome:** Approved implementation contract created.
- **Plan Contract:**
  `docs/plans/2026-08-27/r1-legacy-comparison-evidence-restoration.md`
- **Approval / Status:** User explicitly approved the narrow Preview-only
  restoration in Codex on 2026-08-27.
- **Blockers:** None for the restoration; R1 recapture remains gated on its
  successful completion.
- **Next:** Implement the exact allowlisted source-to-comparison-ref path,
  commit it, and run it only through the Preview wrapper.

## Evidence

- R1's automatic catalog preflight published a valid terminal failure report
  because no 2019 legacy versions were cataloged.
- Read-only inventory located the exact games and teams archives and verified
  their row counts and SHA-256 values recorded in the contract.
- Games contain final scores, allowing deterministic `game_outcomes` Silver
  derivation without a new external source.
- The first Preview execution registered the exact games Bronze capture but
  stopped before any source-set/ref publication because the import primitive
  returned its pre-registration in-memory state. The catalog row itself is
  registered and matches the pinned source URI/checksum. The restoration now
  rereads that catalog row before accepting an imported capture.
- The second attempt built a validated immutable `games` ref, then stopped
  before outcomes/teams/final manifest because its manifest reports the normal
  `seasons: [2019]` partition shape rather than scalar `season: 2019`. The
  catalog resolver already accepts this shape; restoration validation now does
  too. That partial output remains unreferenced by any restoration manifest.

## Boundaries

- Restored refs are comparison-only and never successor source-set parents.
- The operation writes no `raw/*` path and never touches production or V4.
- The fixed source allowlist excludes 2020 and all optional data.

**tags:** ["r1", "lineage", "legacy-comparison", "preview"]
