# Decision Log

**Status**: Active (Post-Reorganization)
**Started**: 2025-12-04
**Legacy Archive**: See [`archive/decision_log_legacy.md`](../../archive/decision_log_legacy.md) for pre-reorganization history

---

## Purpose

This log records all major modeling, architecture, and process decisions made during development. Each entry should include:

- **Date**: When the decision was made
- **Context**: What problem or situation prompted the decision
- **Decision**: What was decided (be specific)
- **Rationale**: Why this was chosen over alternatives
- **Impact**: What changed as a result
- **Artifacts**: Links to code, configs, experiments, or session logs

---

## Template

```markdown
## YYYY-MM-DD: [Decision Title]

- **Context**: [What prompted this decision?]
- **Decision**: [What was decided?]
- **Rationale**: [Why was this chosen?]
  1. Point 1
  2. Point 2
- **Impact**: [What changed?]
- **Artifacts**: [Links to related files, experiments, session logs]
```

---

## Decisions

### 2025-12-04: Repository Reorganization

- **Context**: The repository had grown organically with scattered documentation, multiple overlapping doc directories (operations/, project_org/, guides/), and no clear entry point. The decision log itself had 185 entries spanning rapid November 2024 development cycles, making it difficult to find current state.
- **Decision**:
  1. **Create `docs/guide.md`** as the canonical single source of truth for all documentation
  2. **Reorganize docs** into clear buckets:
     - `docs/process/` — How we work (ML workflow, dev standards, AI templates)
     - `docs/modeling/` — What we build (baseline, features, betting policy, evaluation)
     - `docs/ops/` — How we run (weekly pipeline, MLflow, data paths)
     - `docs/planning/` — Where we're going (roadmap, active initiatives)
     - `docs/research/` — Exploratory work (PPR PRDs, prototypes)
     - `docs/archive/` — Historical/obsolete docs
  3. **Create `archive/` at repo root** for unused scripts, configs, and notebooks
  4. **Archive legacy decision log** and start fresh with clearer structure
  5. **Purge stale artifacts** (MLflow runs, old predictions) while preserving 2025 Week 15 predictions
- **Rationale**:
  1. **Single source of truth** reduces cognitive load for developers and AI assistants
  2. **Clear buckets** make it obvious where to find and add documentation
  3. **Fresh decision log** allows us to focus on current state without historical baggage
  4. **Artifact cleanup** removes confusion from old experiments and failed approaches
- **Impact**:
  - All documentation now navigable from `docs/guide.md`
  - Old directories (`operations/`, `project_org/`, `guides/`) removed
  - Decision log reset to focus on post-reorg decisions
  - Artifacts directory cleaned (except Week 15 predictions)
- **Artifacts**:
  - Plan: `docs/repo_cleanup_plan.md`
  - Session: `session_logs/2025-12-04/02.md`
  - Legacy decisions: `archive/decision_log_legacy.md`

---

<!-- New decisions go here, most recent at top -->
