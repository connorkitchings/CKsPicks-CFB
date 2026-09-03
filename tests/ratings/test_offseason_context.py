from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.ratings.offseason_context import (
    REPORT_VERSION,
    ContextAdmissionError,
    admit_offseason_context,
    require_admitted_context,
)


def _universe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2025, 2026],
            "team": ["Alabama", "Alabama"],
            "first_kickoff_utc": ["2025-08-30T00:00:00Z", "2026-08-30T00:00:00Z"],
        }
    )


def _coaches(*, historic_effective: str = "2025-01-01T00:00:00Z") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2025, 2026],
            "team": ["Alabama", "Alabama"],
            "effective_at": [historic_effective, "2026-08-01T00:00:00Z"],
            "retrieved_at": ["2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z"],
            "coach_tenure": [3.0, 4.0],
            "coach_new": [0.0, 0.0],
        }
    )


def test_admission_classifies_complete_pre_kickoff_family_as_strict():
    result = admit_offseason_context(
        {"coaching": _coaches()},
        _universe(),
        permitted_seasons=(2025,),
    )

    assert result.report["feature_track"] == "strict"
    assert result.report["activation_eligible"] is True
    assert result.report["admitted_families"] == ["coaching"]
    assert result.context["feature_track"].eq("strict").all()


def test_late_historical_evidence_is_reconstructed_and_requires_opt_in():
    result = admit_offseason_context(
        {"coaching": _coaches(historic_effective="2025-09-01T00:00:00Z")},
        _universe(),
        permitted_seasons=(2025,),
    )

    assert result.report["feature_track"] == "reconstructed"
    with pytest.raises(ContextAdmissionError, match="explicit research-only"):
        require_admitted_context(result.report, allow_reconstructed=False)
    assert require_admitted_context(result.report, allow_reconstructed=True) == (
        "coaching",
    )


def test_market_columns_reject_the_family_without_admitting_it():
    source = _coaches()
    source["market_line"] = 3.5

    with pytest.raises(ContextAdmissionError, match="No context family passed"):
        admit_offseason_context(
            {"coaching": source},
            _universe(),
            permitted_seasons=(2025,),
        )


def test_report_validator_rejects_invalid_state():
    with pytest.raises(ContextAdmissionError, match="not an admitted"):
        require_admitted_context(
            {"schema_version": REPORT_VERSION, "state": "rejected"},
            allow_reconstructed=True,
        )
