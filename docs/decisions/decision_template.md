# Decision Template

Use this structure when adding entries to `docs/decisions/decision_log.md`
(newest entries go at the top of the log):

```markdown
## YYYY-MM-DD: Short Decision Title

- **Context**: The situation or evidence that forced a decision.
- **Decision**: What was decided, stated precisely (include identifiers,
  config paths, or flags when they anchor the decision).
- **Impact**: What changed or is now permitted/blocked as a result.
- **Source**: Plan contract, session log, or experiment that records it.
```

Notes:

- One decision per entry; split coupled-but-distinct decisions.
- Record irreversible or governance-relevant choices (architecture, data
  policy, model selection, production posture), not routine task completion.
- Link related docs with `[LOG:YYYY-MM-DD]` or a relative path.
