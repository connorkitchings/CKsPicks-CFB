"""Versioned temporal policy for the 2026 model family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd


@dataclass(frozen=True)
class TemporalFold:
    train_years: tuple[int, ...]
    validation_year: int


@dataclass(frozen=True)
class TrainingPolicy:
    schema_version: str
    labeled_years: tuple[int, ...]
    selection_folds: tuple[TemporalFold, ...]
    locked_test_train_years: tuple[int, ...]
    locked_test_year: int
    production_refit_years: tuple[int, ...]
    prior_source_overrides: Mapping[int, int]
    excluded_years: tuple[int, ...]

    def validate(self) -> None:
        if self.schema_version != "training_policy_2026_v1":
            raise ValueError(f"Unsupported training policy: {self.schema_version}")
        if self.labeled_years != (2021, 2022, 2023, 2024, 2025):
            raise ValueError("Labeled seasons must be exactly 2021-2025")
        expected_folds = (
            TemporalFold((2021,), 2022),
            TemporalFold((2021, 2022), 2023),
            TemporalFold((2021, 2022, 2023), 2024),
        )
        if self.selection_folds != expected_folds:
            raise ValueError("Selection folds must walk forward from 2021 through 2024")
        if self.locked_test_train_years != (2021, 2022, 2023, 2024):
            raise ValueError("The locked 2025 test must train on 2021-2024")
        if self.locked_test_year != 2025:
            raise ValueError("The locked test season must be 2025")
        if self.production_refit_years != self.labeled_years:
            raise ValueError("The production refit must use 2021-2025")
        if dict(self.prior_source_overrides) != {2021: 2019}:
            raise ValueError("The only prior override must map 2021 to 2019")
        if set(self.excluded_years) != {2020}:
            raise ValueError("2020 must be the only globally excluded season")


def policy_from_mapping(raw: Mapping[str, Any]) -> TrainingPolicy:
    folds = tuple(
        TemporalFold(
            tuple(int(year) for year in item["train_years"]),
            int(item["validation_year"]),
        )
        for item in raw["selection_folds"]
    )
    policy = TrainingPolicy(
        schema_version=str(raw["schema_version"]),
        labeled_years=tuple(int(year) for year in raw["labeled_years"]),
        selection_folds=folds,
        locked_test_train_years=tuple(
            int(year) for year in raw["locked_test"]["train_years"]
        ),
        locked_test_year=int(raw["locked_test"]["test_year"]),
        production_refit_years=tuple(
            int(year) for year in raw["production_refit_years"]
        ),
        prior_source_overrides={
            int(year): int(source)
            for year, source in raw["prior_source_overrides"].items()
        },
        excluded_years=tuple(int(year) for year in raw["excluded_years"]),
    )
    policy.validate()
    return policy


def validate_feature_lineage(
    frame: pd.DataFrame,
    policy: TrainingPolicy,
    *,
    labeled: bool = True,
) -> None:
    """Reject forbidden labeled seasons and prior-season lineage."""
    policy.validate()
    required = {"season", "prior_source_season", "prior_season_gap"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Feature dataset is missing lineage columns: {missing}")
    seasons = pd.to_numeric(frame["season"], errors="raise").astype(int)
    priors = pd.to_numeric(frame["prior_source_season"], errors="raise").astype(int)
    gaps = pd.to_numeric(frame["prior_season_gap"], errors="raise").astype(int)
    if labeled and not set(seasons).issubset(policy.labeled_years):
        raise ValueError("Labeled rows may only contain seasons 2021-2025")
    if set(seasons) & set(policy.excluded_years):
        raise ValueError("Feature dataset contains an excluded season")
    if set(priors) & set(policy.excluded_years):
        raise ValueError("Feature lineage references excluded 2020 data")
    expected_priors = seasons.map(
        lambda year: policy.prior_source_overrides.get(year, year - 1)
    )
    if not (priors.to_numpy() == expected_priors.to_numpy()).all():
        raise ValueError("Feature dataset uses an unexpected prior source season")
    expected_gaps = seasons - expected_priors
    if not (gaps.to_numpy() == expected_gaps.to_numpy()).all():
        raise ValueError("prior_season_gap does not match prior source lineage")


def labeled_training_frame(frame: pd.DataFrame, policy: TrainingPolicy) -> pd.DataFrame:
    """Return the policy-approved labeled rows from a mixed training/live frame.

    Gold datasets intentionally include future scheduled games for inference.  Those
    rows still need lineage validation, but must never be treated as labeled model
    training data simply because they share the same immutable dataset version.
    """
    if "season" not in frame:
        raise ValueError("Feature dataset is missing season")
    validate_feature_lineage(frame, policy, labeled=False)
    seasons = pd.to_numeric(frame["season"], errors="raise").astype(int)
    labeled = frame.loc[seasons.isin(policy.labeled_years)].copy()
    validate_feature_lineage(labeled, policy)
    return labeled


def selection_years(policy: TrainingPolicy) -> tuple[int, ...]:
    return tuple(fold.validation_year for fold in policy.selection_folds)


def ensure_training_precedes_prediction(
    train_years: Sequence[int], prediction_year: int
) -> None:
    if not train_years or max(int(year) for year in train_years) >= prediction_year:
        raise ValueError("Training seasons must strictly precede prediction season")
