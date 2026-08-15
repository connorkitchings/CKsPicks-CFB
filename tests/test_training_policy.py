import re
from pathlib import Path

import pandas as pd
import pytest
from omegaconf import OmegaConf

from cks_picks_cfb.models.training_policy import (
    labeled_training_frame,
    policy_from_mapping,
    selection_years,
    validate_feature_lineage,
)


def _policy():
    return policy_from_mapping(
        OmegaConf.to_container(
            OmegaConf.load("conf/training/week0_2026.yaml"), resolve=True
        )
    )


def test_week0_training_policy_has_locked_chronology():
    policy = _policy()
    assert selection_years(policy) == (2022, 2023, 2024)
    assert policy.locked_test_year == 2025
    assert policy.production_refit_years == (2021, 2022, 2023, 2024, 2025)


def test_2021_uses_2019_prior_and_skips_2020():
    policy = _policy()
    frame = pd.DataFrame(
        {
            "season": [2021, 2022, 2025],
            "prior_source_season": [2019, 2021, 2024],
            "prior_season_gap": [2, 1, 1],
        }
    )
    validate_feature_lineage(frame, policy)


def test_lineage_rejects_2019_labels_and_2020_priors():
    policy = _policy()
    with pytest.raises(ValueError, match="Labeled rows"):
        validate_feature_lineage(
            pd.DataFrame(
                {
                    "season": [2019],
                    "prior_source_season": [2018],
                    "prior_season_gap": [1],
                }
            ),
            policy,
        )


def test_labeled_training_frame_allows_2026_inference_rows_without_training_them():
    policy = _policy()
    frame = pd.DataFrame(
        {
            "season": [2021, 2026],
            "prior_source_season": [2019, 2025],
            "prior_season_gap": [2, 1],
        }
    )
    labeled = labeled_training_frame(frame, policy)
    assert labeled["season"].tolist() == [2021]
    with pytest.raises(ValueError, match="excluded 2020"):
        validate_feature_lineage(
            pd.DataFrame(
                {
                    "season": [2021],
                    "prior_source_season": [2020],
                    "prior_season_gap": [1],
                }
            ),
            policy,
        )


def test_active_training_configs_do_not_label_2019_or_2020():
    pattern = re.compile(r"train_years:\s*\[([^]]*)\]")
    violations = []
    for path in Path("conf").rglob("*.yaml"):
        if "legacy" in path.parts:
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            years = {int(value) for value in re.findall(r"\d{4}", match.group(1))}
            if years & {2019, 2020}:
                violations.append(str(path))
    assert violations == []
