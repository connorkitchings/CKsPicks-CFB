"""Pure Phase 4A contracts and analytic rating behavior."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_phase3 import (
    PHASE3_ADJUSTED_DATASET,
    PHASE3_ADJUSTED_SCHEMA,
    PHASE3_ATTRIBUTION_DATASET,
    PHASE3_ATTRIBUTION_SCHEMA,
    PHASE3_OBSERVATION_DATASET,
    PHASE3_OBSERVATION_SCHEMA,
    PHASE3_PREDICTION_DATASET,
    PHASE3_PREDICTION_SCHEMA,
    REQUIRED_CORE_ELIGIBILITY_SHA256,
    phase3_identity,
)
from cks_picks_cfb.data.data_first_phase4a import (
    RATING_CANDIDATES,
    Phase4AError,
    phase4a_identity,
    select_rating,
    validate_phase4a_config,
    verify_phase3_parent,
)
from cks_picks_cfb.ratings.phase4a import (
    analytic_posterior,
    fcs_partial_pool,
    paired_bootstrap_interval,
)

ROOT = Path(__file__).resolve().parents[1]


def _attribution() -> pd.DataFrame:
    rows = []
    for candidate in RATING_CANDIDATES:
        rows.append(
            {
                "candidate": candidate,
                "pooled_mae": 10.0 if candidate == "rho_0_60__exposure" else 9.90,
                "bootstrap_excludes_zero": candidate != "rho_0_60__exposure",
                "coverage_equal": True,
                "seasonal_gate_passed": True,
            }
        )
    return pd.DataFrame(rows)


def _phase3_parent() -> dict:
    identity = phase3_identity(
        run_id="phase3",
        environment="preview",
        as_of="2026-03-01T00:00:00+00:00",
        code_sha="phase3-code",
        config_sha="phase3-config",
        core_eligibility_uri="core.json",
        core_eligibility_sha256=REQUIRED_CORE_ELIGIBILITY_SHA256,
    )
    outputs = {
        "observations": (PHASE3_OBSERVATION_DATASET, PHASE3_OBSERVATION_SCHEMA),
        "adjusted_measurements": (PHASE3_ADJUSTED_DATASET, PHASE3_ADJUSTED_SCHEMA),
        "fold_predictions": (PHASE3_PREDICTION_DATASET, PHASE3_PREDICTION_SCHEMA),
        "attribution_coverage": (PHASE3_ATTRIBUTION_DATASET, PHASE3_ATTRIBUTION_SCHEMA),
    }
    return signed_payload(
        {
            "schema_version": "data_first_phase3_retained_core_v1",
            "state": "frozen",
            "selected_candidate": "epa_only",
            "selected_components": ["epa_per_play"],
            "auxiliary_context_consumed": False,
            "production_activation_authorized": False,
            "identity": identity,
            "output_refs": {
                name: {
                    "dataset": dataset,
                    "version_id": name,
                    "schema_version": schema,
                    "content_sha": f"sha-{name}",
                    "uri": f"lake/{name}",
                }
                for name, (dataset, schema) in outputs.items()
            },
        }
    )


def test_analytic_posterior_has_the_closed_form_100_play_precision():
    mean, variance, prior_precision, observed_precision = analytic_posterior(
        0.0, 1.0, 2.0, 100.0
    )
    assert (mean, variance, prior_precision, observed_precision) == (1.0, 0.5, 1.0, 1.0)
    assert analytic_posterior(0.5, 0.25, None, 0.0)[:2] == (0.5, 0.25)
    with pytest.raises(Phase4AError):
        analytic_posterior(0.0, 0.0, 1.0, 1.0)


def test_selection_uses_simplicity_only_after_all_gates_pass():
    selected = select_rating(_attribution())
    assert selected == "neutral__exposure"
    blocked = _attribution()
    blocked.loc[
        blocked["candidate"].eq("neutral__exposure"), "bootstrap_excludes_zero"
    ] = False
    assert select_rating(blocked) == "neutral__half_life_2"
    none = _attribution()
    none.loc[none["candidate"] != "rho_0_60__exposure", "pooled_mae"] = 9.99
    assert select_rating(none) == "rho_0_60__exposure"


def test_phase4a_config_and_parent_are_closed_to_epa_only_preview_evidence():
    config = yaml.safe_load(
        (
            ROOT / "conf/research/data_first_football_v1/phase4a_rating_v1.yaml"
        ).read_text()
    )
    validate_phase4a_config(config)
    drifted = deepcopy(config)
    drifted["selection"]["equivalent_exposure"] = 99
    with pytest.raises(Phase4AError, match="selection scaffold"):
        validate_phase4a_config(drifted)
    assert verify_phase3_parent(_phase3_parent())["selected_candidate"] == "epa_only"
    broken = _phase3_parent()
    broken["selected_candidate"] = "quality_core_equal"
    broken["selected_components"] = [
        "epa_per_play",
        "success_rate",
        "explosive_rate_20",
        "points_per_scoring_opportunity",
    ]
    broken = signed_payload(broken)
    with pytest.raises(Phase4AError, match="EPA-only"):
        verify_phase3_parent(broken)


def test_identity_binds_parent_checksum_and_as_of_cutoff():
    first = phase4a_identity(
        run_id="one",
        environment="preview",
        as_of="2026-03-01T00:00:00+00:00",
        code_sha="a",
        config_sha="b",
        phase3_retained_uri="parent",
        phase3_retained_sha256="c",
    )
    second = phase4a_identity(
        run_id="one",
        environment="preview",
        as_of="2026-03-02T00:00:00+00:00",
        code_sha="a",
        config_sha="b",
        phase3_retained_uri="parent",
        phase3_retained_sha256="c",
    )
    assert first["identity_sha256"] != second["identity_sha256"]
    with pytest.raises(Phase4AError, match="Preview-only"):
        phase4a_identity(
            run_id="one",
            environment="production",
            as_of="x",
            code_sha="a",
            config_sha="b",
            phase3_retained_uri="parent",
            phase3_retained_sha256="c",
        )


def test_bootstrap_is_paired_at_season_then_week():
    rows = []
    for candidate, error in (("rho_0_60__exposure", 10.0), ("neutral__exposure", 9.0)):
        for week in (1, 2):
            rows.append(
                {
                    "candidate": candidate,
                    "season": 2024,
                    "week": week,
                    "game_id": week,
                    "target": "margin",
                    "absolute_error": error,
                }
            )
    mean, lower, upper = paired_bootstrap_interval(
        pd.DataFrame(rows), "neutral__exposure", replicates=20, confidence=0.90, seed=7
    )
    assert (mean, lower, upper) == (1.0, 1.0, 1.0)


def test_unseen_fcs_fallback_uses_only_preceding_named_fcs_evidence():
    history = pd.DataFrame(
        [
            {
                "classification": "fcs",
                "kickoff_utc": "2024-09-01T00:00:00Z",
                "offense_rating": 1.0,
                "offense_sd": 0.7,
            },
            {
                "classification": "fcs",
                "kickoff_utc": "2024-09-15T00:00:00Z",
                "offense_rating": 99.0,
                "offense_sd": 0.1,
            },
        ]
    )
    mean, sd, reason = fcs_partial_pool(
        history,
        rating_column="offense_rating",
        sd_column="offense_sd",
        cutoff="2024-09-08T00:00:00Z",
    )
    assert reason == "preceding_fcs_partial_pool"
    assert 0 < mean < 1
    assert sd >= 0.7
    assert fcs_partial_pool(
        history.iloc[0:0],
        rating_column="offense_rating",
        sd_column="offense_sd",
        cutoff="2024-09-08T00:00:00Z",
    ) == (0.0, 1.0, "neutral_no_preceding_fcs_cohort")
