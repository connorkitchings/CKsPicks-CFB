"""Pure Phase 4B contracts and context tournament behavior."""

from __future__ import annotations

import runpy
import warnings
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.linear_model import Ridge

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
    PHASE4A_ATTRIBUTION_DATASET,
    PHASE4A_ATTRIBUTION_SCHEMA,
    PHASE4A_PREDICTION_DATASET,
    PHASE4A_PREDICTION_SCHEMA,
    PHASE4A_RATING_STATE_DATASET,
    PHASE4A_RATING_STATE_SCHEMA,
    PHASE4A_RETAINED_RATING_SCHEMA,
    PHASE4A_TEAM_STATE_DATASET,
    PHASE4A_TEAM_STATE_SCHEMA,
    phase4a_identity,
)
from cks_picks_cfb.data.data_first_phase4b import (
    ALL_CONTEXT_CANDIDATES,
    CONTEXT_FAMILIES,
    NO_CONTEXT_FAMILY,
    Phase4BError,
    phase4b_identity,
    select_context,
    validate_phase4b_config,
    verify_phase2e_parent,
    verify_phase3_parent,
    verify_phase4a_parent,
)
from cks_picks_cfb.ratings.phase4b import (
    _fit_predict_ridge,
    _standardize,
    paired_bootstrap_interval,
    validate_tournament_evidence,
)

ROOT = Path(__file__).resolve().parents[1]


def _attribution(target: str = "margin") -> pd.DataFrame:
    from cks_picks_cfb.data.data_first_phase4b import CONTEXT_FAMILY_FEATURES

    rows = []
    for family in ALL_CONTEXT_CANDIDATES:
        feature_count = (
            4
            if family == NO_CONTEXT_FAMILY
            else 4 + len(CONTEXT_FAMILY_FEATURES[family])
        )
        rows.append(
            {
                "target": target,
                "family": family,
                "feature_count": feature_count,
                "pooled_mae": 10.0 if family == NO_CONTEXT_FAMILY else 9.90,
                "baseline_mae": 10.0,
                "improvement_pct": 0.0 if family == NO_CONTEXT_FAMILY else 1.0,
                "bootstrap_excludes_zero": family != NO_CONTEXT_FAMILY,
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


def _phase4a_parent() -> dict:
    identity = phase4a_identity(
        run_id="phase4a",
        environment="preview",
        as_of="2026-03-01T00:00:00+00:00",
        code_sha="phase4a-code",
        config_sha="phase4a-config",
        phase3_retained_uri="phase3.json",
        phase3_retained_sha256="phase3-sha",
    )
    outputs = {
        "rating_states": (PHASE4A_RATING_STATE_DATASET, PHASE4A_RATING_STATE_SCHEMA),
        "team_states": (PHASE4A_TEAM_STATE_DATASET, PHASE4A_TEAM_STATE_SCHEMA),
        "fold_predictions": (PHASE4A_PREDICTION_DATASET, PHASE4A_PREDICTION_SCHEMA),
        "attribution_coverage": (
            PHASE4A_ATTRIBUTION_DATASET,
            PHASE4A_ATTRIBUTION_SCHEMA,
        ),
    }
    return signed_payload(
        {
            "schema_version": PHASE4A_RETAINED_RATING_SCHEMA,
            "state": "frozen",
            "selected_candidate": "rho_0_60__exposure",
            "reference_candidate": "rho_0_60__exposure",
            "auxiliary_context_consumed": False,
            "production_activation_authorized": False,
            "neon_activation_authorized": False,
            "publication_authorized": False,
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


def _phase2e_parent() -> dict:
    return signed_payload(
        {
            "schema_version": "data_first_phase2e_eligibility_v1",
            "state": "eligible_reconstructed_only",
            "activation_eligible": False,
            "production_activation_authorized": False,
            "model_selection_authorized": False,
            "permitted_uses": {
                "recruiting": ["phase3_context_research_only"],
                "returning_production": ["phase3_context_research_only"],
                "coaching": ["phase3_context_research_only"],
                "roster_continuity": ["phase3_context_research_only"],
                "lagged_rankings": ["phase3_context_research_only"],
                "market_references": ["post_phase5_diagnostic_only"],
            },
        }
    )


def test_phase4b_config_and_parents_are_closed_to_preview_evidence():
    config = yaml.safe_load(
        (
            ROOT / "conf/research/data_first_football_v1/phase4b_target_context_v1.yaml"
        ).read_text()
    )
    validate_phase4b_config(config)
    drifted = deepcopy(config)
    drifted["selection"]["ridge_alpha"] = 5
    with pytest.raises(Phase4BError, match="selection scaffold"):
        validate_phase4b_config(drifted)
    drifted2 = deepcopy(config)
    drifted2["context_families"] = list(CONTEXT_FAMILIES[:-1])
    with pytest.raises(Phase4BError, match="context family registry"):
        validate_phase4b_config(drifted2)
    assert verify_phase3_parent(_phase3_parent())["selected_candidate"] == "epa_only"
    assert (
        verify_phase4a_parent(_phase4a_parent())["selected_candidate"]
        == "rho_0_60__exposure"
    )
    assert (
        verify_phase2e_parent(_phase2e_parent())["state"]
        == "eligible_reconstructed_only"
    )
    broken_4a = _phase4a_parent()
    broken_4a["selected_candidate"] = "neutral__exposure"
    broken_4a = signed_payload(broken_4a)
    with pytest.raises(Phase4BError, match="rho_0_60__exposure"):
        verify_phase4a_parent(broken_4a)
    broken_2e = _phase2e_parent()
    broken_2e["activation_eligible"] = True
    broken_2e = signed_payload(broken_2e)
    with pytest.raises(Phase4BError, match="activation-ineligible"):
        verify_phase2e_parent(broken_2e)


def test_identity_binds_all_three_parent_checksums():
    first = phase4b_identity(
        run_id="one",
        environment="preview",
        as_of="2026-03-01T00:00:00+00:00",
        code_sha="a",
        config_sha="b",
        phase4a_retained_uri="phase4a.json",
        phase4a_retained_sha256="c",
        phase3_retained_uri="phase3.json",
        phase3_retained_sha256="d",
        phase2e_eligibility_uri="phase2e.json",
        phase2e_eligibility_sha256="e",
    )
    second = phase4b_identity(
        run_id="one",
        environment="preview",
        as_of="2026-03-02T00:00:00+00:00",
        code_sha="a",
        config_sha="b",
        phase4a_retained_uri="phase4a.json",
        phase4a_retained_sha256="c",
        phase3_retained_uri="phase3.json",
        phase3_retained_sha256="d",
        phase2e_eligibility_uri="phase2e.json",
        phase2e_eligibility_sha256="e",
    )
    assert first["identity_sha256"] != second["identity_sha256"]
    with pytest.raises(Phase4BError, match="Preview-only"):
        phase4b_identity(
            run_id="one",
            environment="production",
            as_of="x",
            code_sha="a",
            config_sha="b",
            phase4a_retained_uri="phase4a.json",
            phase4a_retained_sha256="c",
            phase3_retained_uri="phase3.json",
            phase3_retained_sha256="d",
            phase2e_eligibility_uri="phase2e.json",
            phase2e_eligibility_sha256="e",
        )


def test_selection_uses_simplicity_only_after_all_gates_pass():
    selected = select_context(_attribution(), target="margin")
    assert selected == "pace"
    blocked = _attribution()
    blocked.loc[blocked["family"] == "pace", "bootstrap_excludes_zero"] = False
    assert select_context(blocked, target="margin") == "coaching"
    none_pass = _attribution()
    none_pass.loc[none_pass["family"] != NO_CONTEXT_FAMILY, "pooled_mae"] = 9.99
    assert select_context(none_pass, target="margin") == NO_CONTEXT_FAMILY


def test_bootstrap_is_paired_at_season_then_week():
    rows = []
    for family, error in ((NO_CONTEXT_FAMILY, 10.0), (CONTEXT_FAMILIES[0], 9.0)):
        for week in (1, 2):
            rows.append(
                {
                    "family": family,
                    "target": "margin",
                    "season": 2024,
                    "week": week,
                    "game_id": week,
                    "absolute_error": error,
                }
            )
    mean, lower, upper = paired_bootstrap_interval(
        pd.DataFrame(rows), CONTEXT_FAMILIES[0], replicates=20, confidence=0.90, seed=7
    )
    assert (mean, lower, upper) == (1.0, 1.0, 1.0)


def test_fold_standardization_uses_the_scale_floor():
    train = pd.DataFrame(
        [
            {
                feature: 0.0
                for feature in (
                    "home_offense",
                    "home_defense",
                    "away_offense",
                    "away_defense",
                )
            }
        ]
    )
    validate = train.copy()
    _, _, metadata = _standardize(train, validate, tuple(train.columns))
    assert set(metadata["scale"].values()) == {0.05}


def test_fold_standardization_rejects_numerically_unstable_features():
    train = pd.DataFrame(
        [
            {feature: 1e308 for feature in ("home_offense", "home_defense")},
            {feature: 1e308 for feature in ("home_offense", "home_defense")},
        ]
    )
    with pytest.raises(Phase4BError, match="numerically unstable"):
        _standardize(train, train.copy(), tuple(train.columns))


def test_ridge_fit_warnings_fail_closed_with_fold_context(
    monkeypatch: pytest.MonkeyPatch,
):
    x_train = np.ascontiguousarray(np.array([[0.0], [1.0]], dtype=np.float64))
    y_train = np.ascontiguousarray(np.array([0.0, 1.0], dtype=np.float64))
    x_validate = np.ascontiguousarray(np.array([[0.5]], dtype=np.float64))

    def warn_on_fit(self: Ridge, values: np.ndarray, target: np.ndarray) -> Ridge:
        warnings.warn("synthetic numerical warning", RuntimeWarning)
        self.coef_ = np.array([1.0], dtype=np.float64)
        self.intercept_ = 0.0
        return self

    monkeypatch.setattr(Ridge, "fit", warn_on_fit)
    with pytest.raises(
        Phase4BError,
        match=(
            "Ridge fit numerical failure.*family=field_position, validation_season=2024, target=margin"
        ),
    ):
        _fit_predict_ridge(
            x_train=x_train,
            y_train=y_train,
            x_validate=x_validate,
            family="field_position",
            validation_season=2024,
            target="margin",
            ridge_alpha=10,
        )


@pytest.mark.parametrize("failure", ["coefficients", "predictions"])
def test_ridge_nonfinite_outputs_fail_closed_with_fold_context(
    monkeypatch: pytest.MonkeyPatch, failure: str
):
    x_train = np.ascontiguousarray(np.array([[0.0], [1.0]], dtype=np.float64))
    y_train = np.ascontiguousarray(np.array([0.0, 1.0], dtype=np.float64))
    x_validate = np.ascontiguousarray(np.array([[0.5]], dtype=np.float64))
    if failure == "coefficients":
        original_fit = Ridge.fit

        def fit_with_nan(self: Ridge, values: np.ndarray, target: np.ndarray) -> Ridge:
            fitted = original_fit(self, values, target)
            self.coef_ = np.array([np.nan], dtype=np.float64)
            return fitted

        monkeypatch.setattr(Ridge, "fit", fit_with_nan)
    else:
        original_matmul = np.matmul

        def matmul_with_inf(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            result = original_matmul(a, b)
            return np.full_like(result, np.inf)

        monkeypatch.setattr(np, "matmul", matmul_with_inf)
    with pytest.raises(
        Phase4BError,
        match=("family=field_position, validation_season=2024, target=margin"),
    ):
        _fit_predict_ridge(
            x_train=x_train,
            y_train=y_train,
            x_validate=x_validate,
            family="field_position",
            validation_season=2024,
            target="margin",
            ridge_alpha=10,
        )


def _numeric_attribution() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "target": "margin",
                "family": NO_CONTEXT_FAMILY,
                "feature_count": 4,
                "pooled_mae": 10.0,
                "baseline_mae": 10.0,
                "improvement_pct": 0.0,
                "bootstrap_mean_improvement": 0.0,
                "bootstrap_90_lower": 0.0,
                "bootstrap_90_upper": 0.0,
                "maximum_seasonal_regression_pct": 0.0,
            }
        ]
    )


def _numeric_prediction() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "family": NO_CONTEXT_FAMILY,
                "target": "margin",
                "season": 2024,
                "actual": 3.0,
                "prediction": 2.5,
                "absolute_error": 0.5,
                "ridge_intercept": 0.0,
                "ridge_coefficients": "[0.1, 0.2, 0.3, 0.4]",
            }
        ]
    )


@pytest.mark.parametrize("value", [np.nan, np.inf])
def test_selection_and_evidence_reject_nonfinite_tournament_values(value: float):
    attribution = _attribution()
    attribution.loc[0, "pooled_mae"] = value
    with pytest.raises(Phase4BError, match="invalid baseline MAE|non-finite"):
        select_context(attribution, target="margin")

    prediction = _numeric_prediction()
    prediction.loc[0, "prediction"] = value
    with pytest.raises(Phase4BError, match="non-finite prediction"):
        validate_tournament_evidence(prediction, _numeric_attribution())


def test_independent_verifier_rejects_nonfinite_tournament_evidence():
    verifier = runpy.run_path(
        str(ROOT / "scripts/research/verify_data_first_phase4b.py")
    )
    prediction = _numeric_prediction()
    attribution = _numeric_attribution()
    attribution.loc[0, "bootstrap_90_lower"] = np.inf
    with pytest.raises(Phase4BError, match="non-finite"):
        verifier["_validate_numeric_artifact_evidence"](prediction, attribution)
