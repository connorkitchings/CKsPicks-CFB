"""Pure Phase 4A contracts and analytic rating behavior."""

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
    RATING_CANDIDATES,
    Phase4AError,
    phase4a_identity,
    select_rating,
    validate_phase4a_config,
    verify_phase3_parent,
)
from cks_picks_cfb.ratings.phase4a import (
    _fit_predict_ridge,
    _standardize,
    analytic_posterior,
    fcs_partial_pool,
    paired_bootstrap_interval,
    validate_tournament_evidence,
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


def test_fold_standardization_uses_the_rating_scale_floor():
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
    _, _, metadata = _standardize(train, validate)
    assert set(metadata["scale"].values()) == {0.05}


def test_fold_standardization_converts_nullable_features_to_native_float64():
    train = pd.DataFrame(
        {
            feature: pd.Series([0.0, 1.0], dtype="Float64")
            for feature in (
                "home_offense",
                "home_defense",
                "away_offense",
                "away_defense",
            )
        }
    )
    x_train, x_validate, _ = _standardize(train, train.copy())
    for matrix in (x_train, x_validate):
        assert matrix.dtype == np.float64
        assert matrix.flags.c_contiguous
        assert np.isfinite(matrix).all()


def test_fold_standardization_rejects_numerically_unstable_features():
    train = pd.DataFrame(
        [
            {
                feature: 1e308
                for feature in (
                    "home_offense",
                    "home_defense",
                    "away_offense",
                    "away_defense",
                )
            },
            {
                feature: 1e308
                for feature in (
                    "home_offense",
                    "home_defense",
                    "away_offense",
                    "away_defense",
                )
            },
        ]
    )
    with pytest.raises(Phase4AError, match="numerically unstable"):
        _standardize(train, train.copy())


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
        Phase4AError,
        match=(
            "Ridge fit numerical failure.*candidate=neutral__exposure, validation_season=2024, target=margin"
        ),
    ):
        _fit_predict_ridge(
            x_train=x_train,
            y_train=y_train,
            x_validate=x_validate,
            candidate="neutral__exposure",
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
        Phase4AError,
        match=("candidate=neutral__exposure, validation_season=2024, target=margin"),
    ):
        _fit_predict_ridge(
            x_train=x_train,
            y_train=y_train,
            x_validate=x_validate,
            candidate="neutral__exposure",
            validation_season=2024,
            target="margin",
            ridge_alpha=10,
        )


def _numeric_attribution() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate": "rho_0_60__exposure",
                "pooled_mae": 10.0,
                "reference_mae": 10.0,
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
                "candidate": "rho_0_60__exposure",
                "season": 2024,
                "target": "margin",
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
    with pytest.raises(Phase4AError, match="non-finite"):
        select_rating(attribution)

    prediction = _numeric_prediction()
    prediction.loc[0, "prediction"] = value
    with pytest.raises(Phase4AError, match="non-finite prediction"):
        validate_tournament_evidence(prediction, _numeric_attribution())


def test_independent_verifier_rejects_nonfinite_tournament_evidence():
    verifier = runpy.run_path(
        str(ROOT / "scripts/research/verify_data_first_phase4a.py")
    )
    prediction = _numeric_prediction()
    attribution = _numeric_attribution()
    attribution.loc[0, "bootstrap_90_lower"] = np.inf
    with pytest.raises(Phase4AError, match="non-finite"):
        verifier["_validate_numeric_artifact_evidence"](prediction, attribution)
