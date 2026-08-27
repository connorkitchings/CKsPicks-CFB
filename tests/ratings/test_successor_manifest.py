"""Candidate-v2 protected-evidence manifest tests."""

from __future__ import annotations

import pytest

from cks_picks_cfb.ratings.successor_manifest import (
    SuccessorManifestError,
    candidate_v2_manifest,
    load_successor_v2_prospective_policy,
)


def test_candidate_v2_manifest_requires_passing_r4_and_fresh_policy():
    policy = load_successor_v2_prospective_policy(
        "conf/ratings/successor_v2_prospective_policy.yaml"
    )
    with pytest.raises(SuccessorManifestError, match="failed predictor"):
        candidate_v2_manifest(
            code_sha="abc",
            history_ref_set_uri="history",
            history_ref_set_sha256="history-sha",
            prior_report_uri="prior",
            prior_report_sha256="prior-sha",
            update_report_uri="update",
            update_report_sha256="update-sha",
            predictor_report_uri="predictor",
            predictor_report_sha256="predictor-sha",
            predictor_gates_passed=False,
            prediction_ref={"version_id": "predictions", "content_sha": "sha"},
            policy=policy,
        )
    manifest = candidate_v2_manifest(
        code_sha="abc",
        history_ref_set_uri="history",
        history_ref_set_sha256="history-sha",
        prior_report_uri="prior",
        prior_report_sha256="prior-sha",
        update_report_uri="update",
        update_report_sha256="update-sha",
        predictor_report_uri="predictor",
        predictor_report_sha256="predictor-sha",
        predictor_gates_passed=True,
        prediction_ref={"version_id": "predictions", "content_sha": "sha"},
        policy=policy,
    )
    assert manifest["candidate_v1_evidence_transferred"] is False
    assert manifest["retrospective_freeze_allowed"] is False
