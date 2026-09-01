"""Sealed selection mechanics for successor-v2 R2, R3, and R4 tournaments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.data.season_lineage import SeasonLineagePolicy

TOURNAMENT_CONTRACT_VERSION = "rating_successor_v2_tournaments_v2"


class SuccessorTournamentError(ValueError):
    """Raised for invalid inputs, folds, or sealed-selection violations."""


@dataclass(frozen=True)
class TournamentCandidate:
    candidate_id: str
    complexity: int
    requires_admitted_context: bool = False


@dataclass(frozen=True)
class TournamentConfig:
    stage: str
    baseline_id: str
    candidates: tuple[TournamentCandidate, ...]
    tie_fraction: float
    maximum_full_season_mae_ratio: float | None = None
    maximum_early_season_mae_ratio: float | None = None


def load_tournament_configs(path: str | Path) -> dict[str, TournamentConfig]:
    """Load the sealed candidate roster without evaluating any outcomes."""

    raw = yaml.safe_load(Path(path).read_text())
    if raw.get("tournament_contract_version") != TOURNAMENT_CONTRACT_VERSION:
        raise SuccessorTournamentError("Unsupported successor-v2 tournament contract")
    configs: dict[str, TournamentConfig] = {}
    for stage, values in raw.items():
        if stage in {
            "tournament_contract_version",
            "season_lineage_policy",
            "research_prefix",
        }:
            continue
        if not isinstance(values, Mapping):
            continue
        candidates = tuple(
            TournamentCandidate(
                candidate_id=str(item["id"]),
                complexity=int(item["complexity"]),
                requires_admitted_context=bool(item.get("requires_admitted_context")),
            )
            for item in values["candidates"]
        )
        ids = [candidate.candidate_id for candidate in candidates]
        if len(ids) != len(set(ids)) or values["baseline_id"] not in ids:
            raise SuccessorTournamentError(f"Invalid candidate roster for {stage}")
        configs[stage] = TournamentConfig(
            stage=stage,
            baseline_id=str(values["baseline_id"]),
            candidates=candidates,
            tie_fraction=float(values["tie_fraction"]),
            maximum_full_season_mae_ratio=(
                float(values["maximum_full_season_mae_ratio"])
                if "maximum_full_season_mae_ratio" in values
                else None
            ),
            maximum_early_season_mae_ratio=(
                float(values["maximum_early_season_mae_ratio"])
                if "maximum_early_season_mae_ratio" in values
                else None
            ),
        )
    return configs


def expected_selection_folds(
    policy: SeasonLineagePolicy, stage: str
) -> tuple[int, ...]:
    """Return target seasons allowed for the stage's expanding-fold selection."""

    if stage == "between_season":
        return policy.prior_selection_target_seasons
    if stage == "within_season":
        return policy.update_selection_target_seasons
    if stage == "structured_predictor":
        return policy.update_selection_target_seasons
    raise SuccessorTournamentError(f"Unknown successor-v2 tournament stage {stage}")


def _candidate_map(config: TournamentConfig) -> dict[str, TournamentCandidate]:
    return {candidate.candidate_id: candidate for candidate in config.candidates}


def _validate_results(
    results: pd.DataFrame,
    *,
    policy: SeasonLineagePolicy,
    config: TournamentConfig,
    admitted_context_families: Sequence[str],
) -> pd.DataFrame:
    required = {
        "candidate_id",
        "season",
        "early_margin_mae",
        "early_total_mae",
        "full_margin_mae",
        "full_total_mae",
    }
    missing = required - set(results.columns)
    if missing:
        raise SuccessorTournamentError(
            f"Tournament results missing columns {sorted(missing)}"
        )
    expected = set(expected_selection_folds(policy, config.stage))
    candidates = _candidate_map(config)
    if set(results["candidate_id"]) - set(candidates):
        raise SuccessorTournamentError(
            "Tournament results contain an unsealed candidate"
        )
    if set(results["season"].astype(int)) - expected:
        raise SuccessorTournamentError(
            "Tournament results include a non-selection season"
        )
    if results["season"].astype(int).eq(2020).any():
        raise SuccessorTournamentError("2020 cannot appear in tournament results")
    expected_rows = {
        (candidate_id, season)
        for candidate_id, candidate in candidates.items()
        if not candidate.requires_admitted_context
        or "continuity" in set(admitted_context_families)
        for season in expected
    }
    observed_rows = {
        (str(row.candidate_id), int(row.season)) for row in results.itertuples()
    }
    if observed_rows != expected_rows:
        raise SuccessorTournamentError(
            "Tournament result coverage does not match sealed folds"
        )
    numeric = results[list(required - {"candidate_id", "season"})]
    if not np.isfinite(numeric.to_numpy(float)).all():
        raise SuccessorTournamentError("Tournament metrics must be finite")
    return results.copy()


def select_from_fold_metrics(
    results: pd.DataFrame,
    *,
    policy: SeasonLineagePolicy,
    config: TournamentConfig,
    admitted_context_families: Sequence[str] = (),
) -> dict[str, Any]:
    """Select one stage winner from complete expanding-fold metric rows.

    R2 ranks early-season state/downstream accuracy while enforcing full-season
    non-regression against fixed rho. R3 ranks full-season quality while
    enforcing the Games 1–3 non-regression rule. Ties inside the configured
    fraction select the simpler sealed candidate.
    """

    frame = _validate_results(
        results,
        policy=policy,
        config=config,
        admitted_context_families=admitted_context_families,
    )
    grouped = frame.groupby("candidate_id", observed=True)[
        ["early_margin_mae", "early_total_mae", "full_margin_mae", "full_total_mae"]
    ].mean()
    baseline = grouped.loc[config.baseline_id]
    records: list[dict[str, Any]] = []
    candidates = _candidate_map(config)
    for candidate_id, metrics in grouped.iterrows():
        full_checks = {
            "margin_full_non_regression": config.maximum_full_season_mae_ratio is None
            or metrics["full_margin_mae"]
            <= baseline["full_margin_mae"] * config.maximum_full_season_mae_ratio,
            "total_full_non_regression": config.maximum_full_season_mae_ratio is None
            or metrics["full_total_mae"]
            <= baseline["full_total_mae"] * config.maximum_full_season_mae_ratio,
        }
        early_checks = {
            "margin_early_non_regression": config.maximum_early_season_mae_ratio is None
            or metrics["early_margin_mae"]
            <= baseline["early_margin_mae"] * config.maximum_early_season_mae_ratio,
            "total_early_non_regression": config.maximum_early_season_mae_ratio is None
            or metrics["early_total_mae"]
            <= baseline["early_total_mae"] * config.maximum_early_season_mae_ratio,
        }
        primary = (
            metrics["early_margin_mae"] + metrics["early_total_mae"]
            if config.stage == "between_season"
            else metrics["full_margin_mae"] + metrics["full_total_mae"]
        )
        records.append(
            {
                "candidate_id": candidate_id,
                "complexity": candidates[candidate_id].complexity,
                "primary_mae": float(primary),
                **{key: float(value) for key, value in metrics.items()},
                "checks": {**full_checks, **early_checks},
                "eligible": all(full_checks.values()) and all(early_checks.values()),
            }
        )
    eligible = [record for record in records if record["eligible"]]
    if not eligible:
        return {"winner": None, "candidates": records, "all_checks_passed": False}
    best = min(record["primary_mae"] for record in eligible)
    tied = [
        record
        for record in eligible
        if record["primary_mae"] <= best * (1 + config.tie_fraction)
    ]
    winner = min(
        tied, key=lambda record: (record["complexity"], record["candidate_id"])
    )
    return {
        "winner": winner["candidate_id"],
        "winner_record": winner,
        "candidates": records,
        "all_checks_passed": True,
        "selection_folds": list(expected_selection_folds(policy, config.stage)),
    }


def paired_early_mae_bootstrap(
    predictions: pd.DataFrame, *, samples: int = 2000, seed: int = 42
) -> dict[str, float]:
    """Compare candidate-v1 and candidate-v2 Games 1–3 errors by paired bootstrap."""

    required = {
        "season",
        "game_id",
        "target",
        "completed_games",
        "actual",
        "candidate_v1_prediction",
        "candidate_v2_prediction",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise SuccessorTournamentError(
            f"Bootstrap predictions missing {sorted(missing)}"
        )
    rows = predictions[predictions["completed_games"].astype(int).between(1, 3)].copy()
    if rows.empty or rows["season"].astype(int).eq(2020).any():
        raise SuccessorTournamentError("Early bootstrap needs non-2020 Games 1–3 rows")
    if not {"margin", "total"}.issubset(set(rows["target"])):
        raise SuccessorTournamentError(
            "Early bootstrap must include both margin and total"
        )
    difference = np.abs(
        rows["candidate_v2_prediction"].to_numpy(float) - rows["actual"].to_numpy(float)
    ) - np.abs(
        rows["candidate_v1_prediction"].to_numpy(float) - rows["actual"].to_numpy(float)
    )
    if not np.isfinite(difference).all():
        raise SuccessorTournamentError("Bootstrap predictions must be finite")
    rng = np.random.default_rng(seed)
    means = np.array(
        [
            difference[rng.integers(0, len(difference), len(difference))].mean()
            for _ in range(samples)
        ]
    )
    return {
        "combined_early_mae_difference": float(difference.mean()),
        "lower_95": float(np.quantile(means, 0.025)),
        "upper_95": float(np.quantile(means, 0.975)),
        "samples": samples,
        "seed": seed,
    }


def candidate_v2_gate(
    predictions: pd.DataFrame,
    *,
    locked_2025_passed: bool,
    existing_quality_gates_passed: bool,
) -> dict[str, Any]:
    """Apply the non-negotiable successor-v2 freeze gates to paired predictions."""

    bootstrap = paired_early_mae_bootstrap(predictions)
    full = predictions[predictions["completed_games"].astype(int) >= 1].copy()
    full_checks: dict[str, bool] = {}
    for target, rows in full.groupby("target", observed=True):
        v1 = np.abs(rows["candidate_v1_prediction"] - rows["actual"]).mean()
        v2 = np.abs(rows["candidate_v2_prediction"] - rows["actual"]).mean()
        full_checks[f"{target}_full_season_non_regression"] = v2 <= v1 * 1.01
    checks = {
        "existing_quality_gates": existing_quality_gates_passed,
        "combined_early_bootstrap_upper_below_zero": bootstrap["upper_95"] < 0,
        "margin_full_season_non_regression": full_checks.get(
            "margin_full_season_non_regression", False
        ),
        "total_full_season_non_regression": full_checks.get(
            "total_full_season_non_regression", False
        ),
        "locked_2025": locked_2025_passed,
    }
    return {
        "checks": checks,
        "bootstrap": bootstrap,
        "all_checks_passed": all(checks.values()),
    }
