# Archive Manifest

This directory contains unused, legacy, or deprecated scripts, configs, and notebooks that are not part of the active codebase but are preserved for historical reference.

**Created**: 2025-12-04 (Repository Reorganization)

---

## Contents

### Scripts

_To be populated during script archiving phase_

### Configs

_To be populated during config archiving phase_

### Notebooks

_To be populated during notebook archiving phase_

### Decision Log

- `decision_log_legacy.md` — Pre-reorganization decision history (2025-11-20 through 2025-12-03)
  - **Reason**: Archived to start fresh decision log post-reorganization
  - **Reference**: Contains important historical context for model development decisions

---

## Archiving Policy

### When to Archive

Items are moved to `archive/` when they meet ANY of these criteria:

1. **Unused**: Not referenced by any active pipeline, script, or documentation
2. **Superseded**: Replaced by newer, better implementation
3. **Deprecated**: Explicitly marked for removal in decision log
4. **Experimental**: One-off experiments or prototypes not adopted for production

### What NOT to Archive

- Active production scripts (even if rarely used)
- Core configuration files (even if not currently selected)
- Documentation that's still referenced
- Test files (tests live in `tests/`, not `archive/`)

### Restoration Process

If an archived item is needed again:

1. Review the manifest entry to understand why it was archived
2. Check if a newer alternative exists
3. If still needed, move back to appropriate location
4. Update manifest with restoration date and reason
5. Update docs to reflect restoration

---

## Archived Items Log

### 2025-12-04: Initial Reorganization

**Decision Log**: `decision_log_legacy.md`

- **Original Location**: `docs/decisions/decision_log.md`
- **Reason**: Repository reorganization — starting fresh post-reorg
- **Size**: ~185 decision entries (2025-11-20 through 2025-12-03)
- **Restore If**: Need to reference historical model development context

---

### 2025-12-05: V2 Documentation Alignment

**Model Documentation**: `model_history.md`

- **Original Location**: `docs/models/model_history.md`
- **Reason**: V2 reorganization — legacy model timeline no longer relevant
- **Size**: Historical model progression documentation
- **Restore If**: Need to reference pre-V2 model development timeline

**Model Architecture**: `points_for.md`

- **Original Location**: `docs/models/points_for.md`
- **Reason**: Points-for architecture rejected (see decision log 2025-XX-XX)
- **Size**: Architectural documentation
- **Restore If**: Reconsidering points-for approach (unlikely)

**Ridge Baseline (Legacy)**: `ridge_baseline_legacy.md`

- **Original Location**: `docs/models/ridge_baseline.md`
- **Reason**: Replaced by V2 baseline.md with new philosophy
- **Size**: Legacy ridge documentation
- **Restore If**: Reference for comparison to V2 baseline

**Experiments (Legacy)**: `experiments_legacy.md`

- **Original Location**: `docs/experiments/index.md`
- **Reason**: V2 workflow reset — starting fresh experiment tracking
- **Size**: Pre-V2 experiments (SPR-001, TOT-001, etc.)
- **Restore If**: Need to reference legacy model performance benchmarks

---

## Notes

- This manifest is manually maintained
- Each archive entry should include: item name, original location, archive reason, and restoration conditions
- Large archived items (>10MB) may be compressed (.tar.gz)
- Review this archive quarterly; delete items > 1 year old with no reference
