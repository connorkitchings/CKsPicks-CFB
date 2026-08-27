"""Successor-v2 expanded historical season-policy tests."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from cks_picks_cfb.data.season_lineage import (
    SeasonLineageError,
    load_season_lineage_policy,
)

POLICY_PATH = "conf/ratings/successor_v2_season_lineage.yaml"


def _write(tmp_path, payload):
    path = tmp_path / "season-policy.yaml"
    path.write_text(yaml.safe_dump(payload))
    return path


def test_successor_v2_season_policy_has_exact_scopes_and_folds():
    policy = load_season_lineage_policy(POLICY_PATH)
    assert policy.historical_development_seasons == (
        2015,
        2016,
        2017,
        2018,
        2019,
        2021,
        2022,
        2023,
        2024,
        2025,
    )
    assert policy.forbidden_seasons == (2020,)
    assert policy.prior_selection_target_seasons == (2018, 2019, 2022, 2023, 2024)
    assert policy.update_selection_target_seasons == (
        2017,
        2018,
        2019,
        2021,
        2022,
        2023,
        2024,
    )
    assert policy.prior_locked_season == policy.update_locked_season == 2025


def test_2015_is_seed_and_2021_is_two_year_gap():
    policy = load_season_lineage_policy(POLICY_PATH)
    assert policy.prior_transition_for(2015) is None
    assert policy.prior_transition_for(2016).source_season == 2015
    gap = policy.prior_transition_for(2021)
    assert gap is not None
    assert (
        gap.source_season,
        gap.target_season,
        gap.annual_decay_steps,
        gap.normal,
    ) == (
        2019,
        2021,
        2,
        False,
    )


def test_2020_and_unknown_seasons_fail_closed():
    policy = load_season_lineage_policy(POLICY_PATH)
    with pytest.raises(SeasonLineageError, match="forbidden"):
        policy.assert_allowed(2020)
    with pytest.raises(SeasonLineageError, match="outside"):
        policy.assert_allowed(2014)
    with pytest.raises(SeasonLineageError, match="no permitted"):
        policy.prior_transition_for(2026)


def test_policy_rejects_relaxed_covid_or_fold_configuration(tmp_path):
    payload = yaml.safe_load(Path(POLICY_PATH).read_text())
    relaxed = copy.deepcopy(payload)
    relaxed["seasons"]["forbidden"] = []
    with pytest.raises(SeasonLineageError, match="2020"):
        load_season_lineage_policy(_write(tmp_path, relaxed))

    changed_fold = copy.deepcopy(payload)
    changed_fold["between_season"]["selection_target_seasons"].append(2025)
    with pytest.raises(SeasonLineageError, match="fold"):
        load_season_lineage_policy(_write(tmp_path, changed_fold))
