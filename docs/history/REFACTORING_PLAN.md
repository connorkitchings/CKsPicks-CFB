# CFB Model Refactoring Plan

> **Status:** Phase 2 Complete, Phase 6 Ready | **Duration:** 12 Days | **Drive Access:** Needed only during migration (completed)

**Created:** 2026-02-13  
**Goal:** Modernize cfb_model project using Vibe-Coding template patterns and migrate data to cloud storage

---

## 📋 Quick Navigation

| Section | Purpose |
|---------|---------|
| [Executive Summary](#executive-summary) | TL;DR of the plan |
| [Phase Overview](#phase-overview) | High-level timeline |
| [Current Session](#current-session) | Track ongoing work |
| [Phase Details](#phase-details) | Day-by-day breakdown |
| [Data Storage Strategy](#data-storage-strategy) | Cloud migration plan |
| [Success Criteria](#success-criteria) | How we know we're done |

---

## Executive Summary

### 🎯 Objective
Transform cfb_model into a modern, cloud-native project with:
- ✅ Multi-tool AI support (Claude, Gemini, Codex)
- ✅ Cloud-based data storage (no external drive needed)
- ✅ Automated quality gates and health checks
- ✅ Streamlined documentation
- ✅ Legacy code cleanup

### ⏱️ Timeline
**12 days total** - Can be spread across multiple sessions

### 💰 Costs
- Cloud storage: ~$2-5/month (Cloudflare R2 recommended)
- One-time migration: Free

### 🔴 Critical Requirements
- [x] Cloudflare or AWS account for Phase 2
- [x] External drive connected for migration/cutover
- [ ] Git branch: `refactor/template-adoption`

### ⚠️ V2 Modeling Workflow Status

**Status:** PAUSED for infrastructure refactoring

The V2 4-phase experimentation workflow (see `docs/process/experimentation_workflow.md`) is temporarily suspended while we modernize infrastructure. Modeling work will resume after:
- Phase 6 completion (integration validated)
- Cloud storage operational
- AI tooling modernized

**Next modeling milestone:** Post-refactoring baseline validation

---

## Phase Overview

```
Day 0:      Phase 0 - Context Capture (NO DRIVE NEEDED)
Days 1-2:   Phase 1 - Foundation & AI Tooling (NO DRIVE NEEDED)          ✅ COMPLETE
Days 3-5:   Phase 2 - Data Storage Migration (DRIVE REQUIRED)            ✅ COMPLETE
Days 6-7:   Phase 3 - Documentation Consolidation (NO DRIVE NEEDED)     ✅ COMPLETE
Days 8-9:   Phase 4 - Quality Gates & Automation (NO DRIVE NEEDED)      ✅ COMPLETE
Day 10:     Phase 5 - Legacy Cleanup (NO DRIVE NEEDED)                   ✅ COMPLETE
Days 11-12: Phase 6 - Integration & Validation (NO DRIVE NEEDED)         ▶️ READY
```

**Dependency Note:** Phase 6 requires Phase 2 completion (data migration) for full integration testing.

**Current Status:**  
✅ Phases 0-5: Complete (including Phase 2 cloud migration)  
▶️ Phase 6: Ready to execute

---

## Current Session

**Session Date:** 2026-02-14
**Phase:** Phase 2 ✅ Complete
**Branch:** `refactor/template-adoption`
**Status:** Cloud migration verified; Phase 6 unblocked ✅

### Completed Phases
- [x] Phase 0: Baseline tests, branch creation, test fixes
- [x] Phase 1: AGENTS.md, .agent/, .codex/ structure
- [x] Phase 3: README.md trim, mkdocs.yml update, docs consolidation
- [x] Phase 4: Health checks, Makefile, pre-commit hooks, security scanning
- [x] Phase 5: Legacy audit, 189MB archived, test discovery fixed
- [x] Phase 2: Cloud migration complete (raw/processed parity verified)
- [x] All tests passing (51 tests)
- [x] All quality gates operational
- [x] Session logs created for each phase

### Migration Verification Notes (2026-02-14)
- [x] Verified `raw/` parity: local=5300, cloud=5300, no diffs
- [x] Verified `processed/` parity: local=26557, cloud=26557, no diffs
- [x] Safe cleanup completed: removed 21,642 macOS `._*` files from external drive
- [x] Preserved local manifests (`manifest.json`) by policy (local-only)

**Status update:** Phase 2 is complete. Phase 6 can proceed with cloud-backed validation.

### Current Status
✅ **Infrastructure ready:** AI tooling, docs, quality gates, legacy cleanup all complete  
✅ **Cloud migration ready:** canonical data reconciled between local and R2  
📋 **Next steps:**
1. Phase 6: Full integration testing
2. Final docs/cleanup pass
3. Merge `refactor/template-adoption` branch to main

### Next Session
**When:** Next integration session  
**Focus:** Phase 6 - Integration & Validation

---

## Phase Details

### Phase 0: Context Capture (Day 0)
**Status:** ✅ Complete
**Drive Required:** ❌ No
**Effort:** 1 session

#### Goals
- Document current state before making changes
- Establish baseline metrics
- Create branch and commit initial plan

#### Checklist
- [x] Run `uv run pytest -q` and record baseline (52 tests passing ✅)
- [x] Create branch: `git checkout -b refactor/template-adoption` ✅
- [x] Commit this updated REFACTORING_PLAN.md ✅
- [x] Verify CLAUDE.md content inventory (822 lines to migrate) ✅
- [x] Fix test infrastructure issues (src/utils/__init__.py, pytest config) ✅

#### Session Handoff Pattern
**If ending session mid-phase:**
1. Update "Current Session" section with checkpoint
2. Create session log in `session_logs/YYYY-MM-DD/`
3. Note: "Resume at: [specific checklist item]"

---

### Phase 1: Foundation & AI Tooling (Days 1-2)
**Status:** ✅ Complete
**Drive Required:** ❌ No
**Effort:** 2 days

#### Goals
- Restructure AI entry points (AGENTS.md as universal entry)
- Create session management system (`.agent/` directory)
- Add quick reference system (`.codex/` directory)
- Set up multi-tool support (Claude, Gemini, Codex)

#### Key Files to Create/Modify
```
AGENTS.md (rewrite - universal entry point)
CLAUDE.md (convert to redirect)
GEMINI.md (create - redirect)
.agent/CONTEXT.md (create)
.agent/skills/CATALOG.md (create)
.agent/skills/start-session/SKILL.md (create)
.agent/skills/end-session/SKILL.md (create)
.codex/README.md (create)
.codex/MAP.md (create)
.codex/QUICKSTART.md (create)
```

#### CLAUDE.md Content Migration Plan

The current CLAUDE.md (822 lines) will be split across multiple files:

| Section (Lines) | Target Location | Priority | Notes |
|-----------------|-----------------|----------|-------|
| Data Root Config (1-70) | AGENTS.md: Critical Rules | CRITICAL | MUST keep CFB_MODEL_DATA_ROOT warnings |
| Session Management (71-100) | .agent/skills/start-session/SKILL.md | High | Adapt to Vibe-Coding pattern |
| V2 Workflow Rules (101-200) | Link to docs/process/experimentation_workflow.md | Medium | Already exists, link from AGENTS.md |
| Essential Commands (201-300) | .codex/QUICKSTART.md | High | Quick reference for AI assistants |
| Architecture Overview (301-450) | .agent/CONTEXT.md | High | Project-specific domain knowledge |
| Hydra Config System (451-520) | .codex/HYDRA.md (new) | Medium | Hydra-specific quick ref |
| Data Storage Patterns (521-580) | AGENTS.md: Data Guardrails | CRITICAL | Storage safety rules |
| Development Guidelines (581-680) | docs/development_standards.md | Low | Already exists, reference from AGENTS.md |
| Common Pitfalls (681-750) | AGENTS.md: Troubleshooting | High | Critical for AI assistants |
| Quick Reference (751-822) | .codex/MAP.md | Medium | File locations and shortcuts |

**Target Distribution:**
- AGENTS.md: ~300 lines (Critical Rules + Data Guardrails + Troubleshooting)
- .agent/CONTEXT.md: ~200 lines (Architecture + Domain Knowledge)
- .codex/QUICKSTART.md: ~100 lines (Commands + Essential Patterns)
- .codex/MAP.md: ~100 lines (File locations + Navigation)
- .codex/HYDRA.md: ~80 lines (Config system quick ref)
- CLAUDE.md: ~20 lines (Redirect to AGENTS.md)

#### Checklist
- [x] Create AGENTS.md using Vibe-Coding template structure ✅
- [x] Migrate critical content per table above ✅
- [x] Convert CLAUDE.md to redirect (keep as "See AGENTS.md" stub) ✅
- [x] Update GEMINI.md redirect to point to AGENTS.md ✅
- [x] Create .agent/CONTEXT.md with project-specific knowledge ✅
- [x] Create .agent/skills/CATALOG.md ✅
- [x] Create .agent/skills/start-session/SKILL.md ✅
- [x] Create .agent/skills/end-session/SKILL.md ✅
- [x] Create .codex/MAP.md with project tree ✅
- [x] Create .codex/QUICKSTART.md with essential commands ✅
- [x] Create .codex/HYDRA.md with config system guide ✅
- [x] Test: Can start session by reading AGENTS.md only (verified) ✅

#### Session Handoff
**If ending session mid-phase:**
1. Note which files have been created in "Current Session" section
2. Create session log documenting migration progress
3. List which content sections still need migration

---

### Phase 2: Data Storage Migration (Days 3-5)
**Status:** ✅ Complete  
**Drive Required:** ✅ Yes  
**Effort:** 3 days

#### Goals
- Set up Cloudflare R2 or AWS S3 bucket
- Create storage abstraction layer
- Migrate data from external drive to cloud
- Implement dual-write mode (shadow migration)

#### Key Files to Create/Modify
```
.env (add cloud storage config)
pyproject.toml (add s3fs, boto3)
src/data/storage.py (create - abstraction layer)
scripts/migration/migrate_to_cloud.py (create)
```

#### Configuration Changes
```bash
# Add to .env
CFB_STORAGE_BACKEND=s3
CFB_S3_BUCKET=cfb-model-data
CFB_S3_REGION=us-east-1
# Keep existing:
CFB_MODEL_DATA_ROOT=/Volumes/CK SSD/Coding Projects/cfb_model/
```

#### Migration Steps
1. **Day 3:** Create bucket, set up credentials
2. **Day 4:** Copy historical data (2019-2024)
3. **Day 5:** Implement dual-write, test reads

#### Checklist
- [x] Create S3/R2 bucket with versioning
- [x] Set up lifecycle policies
- [x] Create storage abstraction class
- [x] Copy all raw/ data to cloud
- [x] Copy all processed/ data to cloud
- [x] Test: Can read data without external drive
- [x] Reconcile canonical files (`.csv`, `.parquet`) local vs cloud
- [x] Remove macOS metadata (`._*`) from local source to simplify future sync

---

### Phase 3: Documentation Consolidation (Days 6-7)
**Status:** ✅ Complete
**Drive Required:** ❌ No
**Effort:** 2 days

#### Goals
- Verify CLAUDE.md content migration (completed in Phase 1)
- AGENTS.md is now primary entry (~300 lines max)
- CLAUDE.md becomes redirect (like current AGENTS.md pattern)
- .codex/ provides quick lookups for commands, config, map
- .agent/CONTEXT.md holds project-specific domain knowledge
- Update MkDocs navigation to reference new structure

#### Key Files to Create/Modify
```
README.md (trim to 150 lines)
docs/development_standards.md (create from template)
docs/checklists.md (create from template)
docs/implementation_schedule.md (create from template)
docs/project_charter.md (create from template)
mkdocs.yml (update navigation)
```

#### Checklist
- [x] Verify all CLAUDE.md content has been migrated (Phase 1 complete) ✅
- [x] Trim README.md to essentials (381 → 222 lines) ✅
- [x] Update mkdocs.yml navigation to reference new structure ✅
- [x] Update docs/guide.md references (CLAUDE.md → AGENTS.md) ✅
- [x] Test: mkdocs build works (builds successfully) ✅
- [x] Test: New AI assistant can onboard in <30 mins (verified) ✅
- [x] Keep architecture in .agent/CONTEXT.md (no separate file needed) ✅

#### Session Handoff
**If ending session mid-phase:**
1. Document which docs have been updated
2. Note any broken links to fix next session

---

### Phase 4: Quality Gates & Automation (Days 8-9)
**Status:** ✅ Complete
**Drive Required:** ❌ No
**Effort:** 2 days

#### Goals
- Create health check script
- Set up pre-commit hooks
- Update session log templates
- Add automated validation

#### Key Files to Create/Modify
```
.agent/workflows/health-check.sh (create)
.pre-commit-config.yaml (update)
session_logs/TEMPLATE.md (update from template)
```

#### Checklist
- [x] Create .agent/workflows/health-check.sh (ruff format, ruff lint, pytest) ✅
- [x] Make health-check.sh executable: `chmod +x .agent/workflows/health-check.sh` ✅
- [x] Update .pre-commit-config.yaml (add ruff format + lint) ✅
- [x] Update session_logs/TEMPLATE.md to match Vibe-Coding pattern ✅
- [x] Test: health checks pass (`sh .agent/workflows/health-check.sh`) ✅
- [x] Test: pre-commit hooks work (`pre-commit run --all-files`) ✅

#### Session Handoff
**If ending session mid-phase:**
1. Note which automation scripts are complete
2. Document any pre-commit hook issues

---

### Phase 5: Legacy Deletion (Day 10)
**Status:** ✅ Complete
**Drive Required:** ❌ No
**Effort:** 1 day

#### Goals
- Delete `legacy/` directory entirely (189MB, 594 files)
- Delete `scripts/archive/` (8 obsolete files)
- Delete `conf/legacy/` (18 old configs)
- Clean break - no archival (Git history serves as backup)

#### Rationale
User decision: Delete permanently. The legacy/ directory has:
- No active imports (verified via grep)
- MLflow history already in artifacts/mlruns/
- Old model artifacts duplicated elsewhere
- No unique valuable code after exploration

#### Checklist
- [x] Verify no imports from legacy/: `grep -r "from legacy\|import legacy" src/ scripts/` ✅
- [x] Verify no imports from scripts/archive/: `grep -r "scripts\.archive" src/ scripts/` ✅
- [x] Run tests to confirm no dependencies: `uv run pytest -q` (should pass) ✅
- [x] Delete legacy/: `rm -rf legacy/` ✅
- [x] Delete scripts/archive/: `rm -rf scripts/archive/` ✅
- [x] Delete conf/legacy/: `rm -rf conf/legacy/` ✅
- [x] Run tests again: `uv run pytest -q` (should still pass) ✅
- [x] Commit deletion with message: `chore: Remove 189MB legacy/ directory - clean break, git history preserved` ✅
- [x] Document in session log: what was deleted and rationale ✅

#### Session Handoff
**If ending session mid-phase:**
1. Note which directories have been verified/deleted
2. If deletion fails tests, document the failure for investigation

---

### Phase 6: Integration & Validation (Days 11-12)
**Status:** ▶️ Ready  
**Drive Required:** ❌ No  
**Effort:** 2 days

#### Goals
- Run end-to-end pipeline tests
- Validate cloud storage integration
- Test documentation builds
- Final review and cleanup

#### Checklist
- [ ] Run health check script: `sh .agent/workflows/health-check.sh` (all green)
- [ ] Run full test suite: `uv run pytest -v` (47+ tests pass)
- [ ] Build documentation: `mkdocs build --strict` (no errors)
- [ ] Verify AI entry points:
  - [ ] AGENTS.md → loads in <2 min
  - [ ] .agent/CONTEXT.md → provides project-specific knowledge
  - [ ] .codex/QUICKSTART.md → has essential commands
- [ ] Test cloud storage: Read a sample dataset from R2/S3
- [ ] Verify external drive not needed: Disconnect drive, run health checks
- [ ] Create completion session log documenting:
  - What changed (summary of all 6 phases)
  - New file structure
  - How to onboard new AI assistants
  - V2 workflow resumption plan

#### Session Handoff
**If ending session mid-phase:**
1. Document which validation checks have passed
2. Note any remaining issues or test failures

---

## Data Storage Strategy

### Recommended: Cloudflare R2

**Why R2 over AWS S3:**
- ✅ No egress fees (unlimited downloads)
- ✅ Lower cost ($0.015/GB vs $0.023/GB)
- ✅ S3-compatible API
- ✅ Better for data science workloads

### Bucket Structure
```
s3://cfb-model-data/
├── raw/                    # API responses
│   ├── plays/
│   ├── games/
│   └── teams/
├── processed/              # Aggregated features
│   ├── byplay/
│   ├── drives/
│   ├── team_game/
│   └── team_season/
├── models/                 # Serialized models
├── artifacts/              # MLflow artifacts
└── backups/                # Point-in-time snapshots
```

### Migration Approach: Shadow Mode

**Week 1-2: Dual Write**
```python
# Write to both locations
data.to_parquet(local_path)      # Existing
data.to_parquet(s3_path)         # New
```

**Week 3+: Switch Reads**
```python
# Read from S3 (validated)
data = pd.read_parquet(s3_path)
```

**Week 5+: Cleanup**
- Disconnect external drive
- Keep as emergency backup

### Cost Estimation

| Service | Storage | Egress | Total/Month |
|---------|---------|--------|-------------|
| AWS S3 | $0.023/GB | $0.09/GB | $3-7 |
| Cloudflare R2 | $0.015/GB | Free | $1-2 |

**Estimated data size:** 50-100GB  
**Recommended:** Cloudflare R2 (~$2/month)

---

## Success Criteria

### Must Have (Critical)
- [ ] Can start session by reading `AGENTS.md` only
- [ ] Run `sh .agent/workflows/health-check.sh` → all green
- [ ] Access data without external drive connected
- [ ] All tests pass: `uv run pytest -q`
- [ ] Documentation builds: `mkdocs build --strict`

### Should Have (Important)
- [ ] New AI assistant productive in <30 minutes
- [ ] Pre-commit hooks prevent bad commits
- [ ] Cloud storage has versioning enabled
- [ ] Legacy directory deleted (0MB, down from 189MB)

### Nice to Have (Optional)
- [ ] Automatic session log reminders
- [ ] Slack notifications for validation failures
- [ ] Dashboard for cloud storage metrics

---

## Session Log Template

When working on this refactoring, create session logs in:
```
session_logs/YYYY-MM-DD/NN.md
```

Use this format:
```markdown
# Session: Refactoring Phase X - [Brief Description]

## TL;DR
- **Phase:** X of 6
- **Worked On:** [What was done]
- **Completed:** [What was finished]
- **Blockers:** [Any issues]
- **Next:** [What's next]

## Changes Made
- File 1: [description]
- File 2: [description]

## Testing
- [ ] Health checks pass
- [ ] Tests pass
- [ ] Documentation builds

## Notes for Next Session
[Context to carry forward]
```

---

## Rollback Plan

If anything goes wrong:

1. **Code issues:**
   ```bash
   git checkout main
   git branch -D refactor/template-adoption
   ```

2. **Data issues:**
   - Reconnect external drive
   - Switch `CFB_STORAGE_BACKEND=local`
   - All data still on drive

3. **Cloud issues:**
   - Keep local copies during migration
   - Versioned storage allows rollback
   - External drive as ultimate backup

---

## Resources

### Template Reference
- **Vibe-Coding Template:** https://github.com/connorkitchings/Vibe-Coding
- **Key Files:** AGENTS.md, .agent/skills/, .codex/

### Cloud Storage
- **Cloudflare R2:** https://www.cloudflare.com/developer-platform/r2/
- **AWS S3:** https://aws.amazon.com/s3/

### Project Context
- **Current Entry:** CLAUDE.md (823 lines)
- **Legacy Size:** 189MB
- **Test Data:** 399 files in repo
- **Last Session:** 2026-02-10 (validation service)

---

## Approval & Start

**To begin Phase 1:**
1. Approve this plan
2. Create branch: `git checkout -b refactor/template-adoption`
3. Update "Current Session" section above
4. Begin with Phase 1 checklist

**Ready to start?** ✅

---

---

## Refactoring Decisions Record

**Date:** 2026-02-13
**Decisions Made:**

| Question | Decision | Rationale |
|----------|----------|-----------|
| V2 Workflow Status | Paused for refactoring | Infrastructure must stabilize before modeling work resumes |
| CLAUDE.md Content | Split across AGENTS.md + .codex/ + .agent/ | Maintains detail, follows Vibe-Coding patterns |
| Legacy Directory | Delete permanently (no archive) | Clean break, git history preserves if needed |
| Timeline | Spread across multiple sessions | Realistic for available time, needs context handoffs |

---

**Last Updated:** 2026-02-13 (Critique applied)
**Next Review:** After Phase 0 completion
