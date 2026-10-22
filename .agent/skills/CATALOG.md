# Skills Catalog

Session workflows for AI assistants. Each skill is `.agent/skills/<name>/SKILL.md`; read it before starting that workflow.

| Skill | Use when | Key steps |
|---|---|---|
| [start-session](start-session/SKILL.md) | Beginning a session or returning after a break | Load `AGENTS.md` and `.codex/QUICKSTART.md`; verify only the storage the task needs, without exposing secrets; review the last three days of session logs; check `git status`; route to a plan contract, contract implementation or the fast path |
| [plan-session](plan-session/SKILL.md) | The request affects architecture, data/model lineage, schemas, production, security or several subsystems | Investigate in Sol Plan Mode; persist the approved contract at `docs/plans/YYYY-MM-DD/`; write the planning session log and a copy-ready Terra prompt |
| [implement-plan](implement-plan/SKILL.md) | The user supplies an Approved plan path, or explicitly authorizes an exact Draft path | Reconcile the contract against the current worktree; execute tasks and validation in order; record safe amendments or stop on material conflicts |
| [end-session](end-session/SKILL.md) | Finishing a task or handing off | Write the session log from `session_logs/TEMPLATE.md`; run session-scoped checks; update docs; propose a commit message; record handoff notes |

## Operational authority

These skills govern session workflow only. The sole recurring operating guide is the [weekly runbook](../../docs/ops/weekly_runbook.md) (`build_season_revision.py`, then `run_season.py` prepare, release and rollback). V5 is the only operational model; [V4](../../docs/modeling/v4_retrospective.md) is historical evidence. Isolated research follows its approved contract and `scripts/research/README.md`.

To add a skill, create `.agent/skills/<name>/SKILL.md` (purpose, when to use, workflow, checklist) and add a row above.
