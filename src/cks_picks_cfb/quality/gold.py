"""Gold contract gates. No reconstruction or value imputation occurs here."""

from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.metrics import contracts
from cks_picks_cfb.quality.checks import WARN, Outcome, register_check

DATASETS = (
    "team_game_metrics",
    "football_possessions",
    "football_scoring_ledger",
    "scoring_attribution_evidence",
)


@register_check(
    "gold.schema_contract",
    stage="gold",
    severity=WARN,
    description="All four Gold measurement datasets satisfy their versioned schemas",
)
def schema_contract(ctx):
    results = []
    for name in DATASETS:
        if name not in ctx:
            results.append(
                Outcome(
                    False,
                    detail=f"missing Gold dataset: {name}",
                    scope={"dataset": name},
                )
            )
            continue
        try:
            validate_frame(ctx[name], schema_for(name, name + "_v1"))
            results.append(
                Outcome(True, observed=len(ctx[name]), scope={"dataset": name})
            )
        except ValueError as exc:
            results.append(Outcome(False, detail=str(exc), scope={"dataset": name}))
    return results


@register_check(
    "gold.metric_semantics",
    stage="gold",
    severity=WARN,
    description="Metric ratios, coverage, missingness and offense/defense mirrors reconcile",
)
def metric_semantics(ctx):
    frame = ctx.get("team_game_metrics")
    if frame is None:
        return Outcome(False, detail="team_game_metrics missing")
    problems = contracts.team_game_metrics_problems(
        frame
    ) + contracts.defense_mirror_problems(frame)
    return Outcome(
        not problems,
        observed=len(problems),
        expected=0,
        detail="; ".join(problems[:30]),
    )


@register_check(
    "gold.ledger_semantics",
    stage="gold",
    severity=WARN,
    description="Possessions, scoring admission and evidence satisfy the shared contracts",
)
def ledger_semantics(ctx):
    if any(name not in ctx for name in DATASETS[1:]):
        return Outcome(
            False, detail="possessions, scoring ledger or attribution evidence missing"
        )
    problems = contracts.possessions_problems(ctx["football_possessions"])
    problems += contracts.scoring_ledger_problems(
        ctx["football_scoring_ledger"], ctx["football_possessions"]
    )
    problems += contracts.evidence_problems(ctx["scoring_attribution_evidence"])
    return Outcome(
        not problems,
        observed=len(problems),
        expected=0,
        detail="; ".join(problems[:30]),
    )
