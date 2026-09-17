"""Sealed fitting-history policies and paired horizon selection."""

from __future__ import annotations

import numpy as np
import pandas as pd


class HorizonError(ValueError):
    """Raised when horizon evidence is incomplete or incomparable."""


def fitting_seasons(
    season: int, development_seasons: tuple[int, ...], horizon: str
) -> tuple[int, ...]:
    earlier = tuple(value for value in development_seasons if value < season)
    if horizon == "expanding":
        return earlier
    if horizon == "latest_five":
        return earlier[-5:]
    raise HorizonError(f"unknown horizon: {horizon}")


def paired_bootstrap_lower(
    candidate: pd.DataFrame, reference: pd.DataFrame, *, seed: int, samples: int
) -> tuple[float, float, float]:
    keys = ["season", "week", "game_id", "target"]
    merged = candidate.merge(
        reference, on=keys, suffixes=("_candidate", "_reference"), validate="one_to_one"
    )
    if len(merged) != len(candidate) or len(merged) != len(reference) or merged.empty:
        raise HorizonError("paired comparison needs identical non-empty populations")
    difference = merged["absolute_error_reference"].to_numpy(float) - merged[
        "absolute_error_candidate"
    ].to_numpy(float)
    rng = np.random.default_rng(seed)
    groups = [
        group.index.to_numpy()
        for _, group in merged.groupby(["season", "week"], sort=True)
    ]
    if not groups:
        raise HorizonError("paired bootstrap lacks season/week groups")
    estimates = []
    for _ in range(samples):
        selected = rng.integers(0, len(groups), size=len(groups))
        sampled = np.concatenate(
            [
                groups[index][rng.integers(0, len(groups[index]), len(groups[index]))]
                for index in selected
            ]
        )
        estimates.append(float(difference[sampled].mean()))
    return (
        float(difference.mean()),
        float(np.quantile(estimates, 0.05)),
        float(np.quantile(estimates, 0.95)),
    )


def select_horizon(
    expanding: pd.DataFrame, latest_five: pd.DataFrame, *, seed: int, samples: int
) -> tuple[str, pd.DataFrame]:
    """Choose one shared policy; latest-five must pass every contract gate."""
    required = {
        "season",
        "week",
        "game_id",
        "target",
        "absolute_error",
        "gaussian_crps",
        "completed_game_stage",
    }
    if required - set(expanding) or required - set(latest_five):
        raise HorizonError("horizon predictions lack comparison columns")
    rows: list[dict[str, object]] = []
    latest_passes = True
    for target in ("margin", "total"):
        reference = expanding[expanding["target"].eq(target)].copy()
        candidate = latest_five[latest_five["target"].eq(target)].copy()
        mean_gain, lower, upper = paired_bootstrap_lower(
            candidate, reference, seed=seed, samples=samples
        )
        ref_mae, cand_mae = (
            float(reference.absolute_error.mean()),
            float(candidate.absolute_error.mean()),
        )
        ref_crps, cand_crps = (
            float(reference.gaussian_crps.mean()),
            float(candidate.gaussian_crps.mean()),
        )
        improvement = 100.0 * (ref_mae - cand_mae) / ref_mae if ref_mae else 0.0
        slices = pd.concat(
            [
                reference.assign(policy="expanding"),
                candidate.assign(policy="latest_five"),
            ]
        )
        regressions_ok = True
        for _, group in slices.groupby(["season", "completed_game_stage"], sort=True):
            base = group[group.policy.eq("expanding")]
            short = group[group.policy.eq("latest_five")]
            if (
                len(base) != len(short)
                or base.empty
                or float(short.absolute_error.mean())
                > float(base.absolute_error.mean()) * 1.05
            ):
                regressions_ok = False
        passes = (
            improvement >= 0.5
            and lower > 0
            and cand_mae <= ref_mae * 1.01
            and cand_crps <= ref_crps * 1.01
            and regressions_ok
        )
        latest_passes &= passes
        rows.append(
            {
                "target": target,
                "metric": "mae",
                "expanding": ref_mae,
                "latest_five": cand_mae,
                "improvement_pct": improvement,
                "bootstrap_90_lower": lower,
                "bootstrap_90_upper": upper,
                "passes": passes,
            }
        )
        rows.append(
            {
                "target": target,
                "metric": "gaussian_crps",
                "expanding": ref_crps,
                "latest_five": cand_crps,
                "improvement_pct": 100.0 * (ref_crps - cand_crps) / ref_crps
                if ref_crps
                else 0.0,
                "bootstrap_90_lower": lower,
                "bootstrap_90_upper": upper,
                "passes": passes,
            }
        )
    return ("latest_five" if latest_passes else "expanding"), pd.DataFrame.from_records(
        rows
    )
