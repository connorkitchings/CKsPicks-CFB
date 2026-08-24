# Repository Documentation and 2026 Ratings Realignment

- **Status:** Implemented
- **Created:** 2026-08-23
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact plan on 2026-08-23.
- **Implementation log:** `session_logs/2026-08-23/07-repository-documentation-and-2026-ratings-realignment.md`
- **Commit policy:** Separate plan commit recommended; git operations remain user-controlled.

## Goal

Review every project-owned Markdown file and make the rating-centric architecture
the explicit 2026 goal. Keep V4 in production while its successor is developed
in isolated shadow paths. Complete initial rating-system requirements, the
measurement catalog, evaluation rules, and the transition roadmap before Week 0.

## Current State

V4 is the live 2026 production champion and the approved benchmark. The prior
rating transition documentation was framed around a possible 2027 promotion.
The repository contains valuable but conflicting V2 and probabilistic-rating
history, duplicated docs hubs, stale navigation, and an unarchived body of old
session logs.

## Proposed Approach

Establish a small current authority set, archive historical evidence, delete
misleading or duplicate prose, and publish requirements for a ratings-first
successor. Historical 2021–2025 data supports temporal development; frozen
2026 shadow evidence controls any promotion decision.

## Scope

### Included

- Markdown, `mkdocs.yml`, archive organization, documentation audit, the
  replacement contract, and its implementation session log.
- Moving all session logs before 2026-08-09 into the normalized archive.

### Excluded

- Source, schemas, configuration, datasets, bundles, storage, deployment, and
  production behavior.
- Selecting or implementing a rating estimator, rating scale, prior model,
  uncertainty mechanism, special-teams component, residual model, or artifact
  schema.

## Affected Components and Contracts

- Current authority: repository onboarding, roadmap, model architecture,
  evaluation, operations, data-platform documentation, and MkDocs navigation.
- Historical evidence: V2, old rating research, old schema snapshots,
  completed strategic plans, and session logs.
- No public APIs or runtime contracts change.

## Implementation Tasks

### Task 1 — Establish current documentation authority

- Make `docs/index.md` the sole docs home; remove `docs/guide.md`.
- Align onboarding, roadmap, operations, and navigation with the 2026
  ratings-first direction and V4 production posture.
- Record every Markdown-file disposition in the documentation audit.

### Task 2 — Publish rating requirements and transition policy

- Create the canonical measurement catalog and rating-system requirements.
- Define the target responsibility boundaries, conceptual team state, protected
  prospective evaluation, six-full-slate promotion gate, and open decisions.
- Update cross-linked modeling, roadmap, decision, and experiment authorities.

### Task 3 — Archive and delete stale content

- Archive useful V2, rating-research, refactoring, completed-plan, and schema
  history with an archive index.
- Delete only the resolved list of duplicate, nonexistent, or misleading docs.
- Normalize the session-log archive and retain every actual session log.

### Task 4 — Validate and close

- Require a strict MkDocs build with no warnings, active-link validation,
  terminology checks, changed-path review, and `git diff --check`.

## Testing Strategy

This is documentation-only work. Validate documentation rendering, active local
links, terminology consistency, and changed-path scope; runtime tests are not
required because no runtime behavior changes.

## Risks and Edge Cases

- Future-state prose must not imply an implemented or activation-eligible
  rating system.
- Historical links may become stale after archival; preserve evidence and make
  the current authority navigable instead of rewriting historical claims.
- 2026 outcomes must not be reused as an untracked iterative test set.

## Definition of Done

- [x] Current authority documents agree on the 2026 rating transition and V4
  production role.
- [x] Initial measurement and rating requirements are published before Week 0.
- [x] Every project-owned Markdown file is accounted for by the audit.
- [x] Session logs before 2026-08-09 are archived without loss.
- [x] Required validation passes.
- [x] Documentation and session log are updated.
- [x] Plan status is updated to `Implemented`.

## Amendments

### Amendment 1 — Preserve archive moves in Git

**Reason:** The repository’s broad `archive/` ignore rule also matched
`docs/archive/` and `session_logs/archive/`, hiding the requested archival
moves as untracked content.

**Original approach:** Move historical Markdown into the documentation and
session-log archives without changing non-documentation files.

**Revised approach:** Add narrow `.gitignore` exceptions for those two archive
trees only.

**Impact:** The archival history is reviewable and committable. Runtime,
storage, model, schema, and deployment behavior remain unchanged.
