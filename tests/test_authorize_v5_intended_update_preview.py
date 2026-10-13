import pytest

from cks_picks_cfb.ops.v5_intended_update_release import AUTH_COLUMNS
from scripts.pipeline.authorize_v5_intended_update_preview import (
    APPROVAL_COLUMNS,
    authorization_record,
    register_authorization,
)

BUNDLE = "a507d0c7cba5" + "0" * 52
APPROVAL = {
    "approval_id": "preview-intended-update-a507d0c7cba5",
    "model_id": "v5-intended-update-2026-v1",
    "inference_bundle_sha256": BUNDLE,
    "first_live_season": 2026,
    "first_live_week": 5,
    "decision_ref": "preview-rehearsal-display-only-week6",
}
EXPECTED = {
    "approval_id": APPROVAL["approval_id"],
    "approval_bundle_sha256": BUNDLE,
    "approval_decision_ref": APPROVAL["decision_ref"],
}


class FakeCursor:
    """In-memory approvals and authorizations keyed like the Preview tables."""

    def __init__(self, approvals):
        self.approvals = [dict(row) for row in approvals]
        self.authorizations = {}
        self.writes = 0
        self._result = []

    def execute(self, sql, params):
        if sql.startswith("SELECT") and "v5_model_bundle_approvals" in sql:
            approval_id, model_id, bundle = params
            self._result = [
                tuple(row[key] for key in APPROVAL_COLUMNS)
                for row in self.approvals
                if row["approval_id"] == approval_id
                or (
                    row["model_id"] == model_id
                    and row["inference_bundle_sha256"] == bundle
                )
            ]
        elif sql.startswith("SELECT"):
            row = self.authorizations.get(params[0])
            self._result = [] if row is None else [row]
        elif sql.startswith("INSERT"):
            if params[0] not in self.authorizations:
                self.authorizations[params[0]] = params
                self.writes += 1
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None


def week7_record(decision_ref="week7-display-only-2026-10-13"):
    manifest = {
        "run_id": "2026w7-v5repair-20261013-p1",
        "week": 7,
        "evidence_class": "pending",
        "model_id": APPROVAL["model_id"],
        "inference_bundle_sha256": BUNDLE,
        "v5_rating_replay_manifest_sha256": "b" * 64,
        "v5_live_forecast_manifest_uri": "r2://forecast.json",
        "v5_live_forecast_manifest_sha256": "c" * 64,
        "v5_intended_update_serving_manifest_uri": "r2://serving.json",
        "v5_intended_update_serving_manifest_sha256": "d" * 64,
        "v5_intended_update_verifier_uri": "r2://verifier.json",
        "v5_intended_update_verifier_sha256": "e" * 64,
        "artifact_uri": "r2://predictions.parquet",
        "artifact_sha256": "f" * 64,
    }
    return authorization_record(manifest, decision_ref=decision_ref)


def test_matching_approval_writes_week7_authorization_with_its_own_ref():
    cur = FakeCursor([APPROVAL])
    record = week7_record()

    assert register_authorization(cur, record, **EXPECTED) is True

    stored = dict(zip(AUTH_COLUMNS, cur.authorizations[record["authorization_id"]]))
    assert stored["decision_ref"] == "week7-display-only-2026-10-13"
    assert cur.approvals == [APPROVAL]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("approval_id", "preview-intended-update-other"),
        ("model_id", "v5-other-model"),
        ("inference_bundle_sha256", "1" * 64),
        ("first_live_season", 2025),
        ("decision_ref", "some-other-decision"),
    ],
)
def test_stored_approval_identity_mismatch_refuses(field, value):
    cur = FakeCursor([{**APPROVAL, field: value}])
    with pytest.raises(ValueError):
        register_authorization(cur, week7_record(), **EXPECTED)
    assert cur.writes == 0


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("approval_id", "preview-intended-update-other"),
        ("approval_bundle_sha256", "1" * 64),
        ("approval_decision_ref", "some-other-decision"),
    ],
)
def test_reviewed_identity_argument_mismatch_refuses(argument, value):
    cur = FakeCursor([APPROVAL])
    with pytest.raises(ValueError):
        register_authorization(cur, week7_record(), **{**EXPECTED, argument: value})
    assert cur.writes == 0


def test_non_preview_record_refuses():
    cur = FakeCursor([APPROVAL])
    record = {**week7_record(), "environment": "production"}
    with pytest.raises(ValueError, match="Preview"):
        register_authorization(cur, record, **EXPECTED)
    assert cur.writes == 0


@pytest.mark.parametrize("first_live_week", [5, 6, 7])
def test_approval_live_at_or_before_week7_is_eligible(first_live_week):
    cur = FakeCursor([{**APPROVAL, "first_live_week": first_live_week}])
    assert register_authorization(cur, week7_record(), **EXPECTED) is True


def test_approval_live_after_week7_refuses():
    cur = FakeCursor([{**APPROVAL, "first_live_week": 8}])
    with pytest.raises(ValueError, match="after requested week 7"):
        register_authorization(cur, week7_record(), **EXPECTED)
    assert cur.writes == 0


def test_two_matching_approvals_refuse():
    duplicate = {**APPROVAL, "approval_id": "legacy-v5-" + BUNDLE}
    cur = FakeCursor([APPROVAL, duplicate])
    with pytest.raises(ValueError, match="found 2"):
        register_authorization(cur, week7_record(), **EXPECTED)
    assert cur.writes == 0


def test_missing_approval_refuses():
    cur = FakeCursor([])
    with pytest.raises(ValueError, match="found 0"):
        register_authorization(cur, week7_record(), **EXPECTED)
    assert cur.writes == 0


def test_identical_retry_writes_nothing():
    cur = FakeCursor([APPROVAL])
    register_authorization(cur, week7_record(), **EXPECTED)

    assert register_authorization(cur, week7_record(), **EXPECTED) is False
    assert cur.writes == 1


def test_retry_with_different_week7_decision_ref_refuses():
    cur = FakeCursor([APPROVAL])
    register_authorization(cur, week7_record(), **EXPECTED)

    with pytest.raises(ValueError, match="conflicts"):
        register_authorization(
            cur, week7_record(decision_ref="another-week7-decision"), **EXPECTED
        )
    assert cur.writes == 1
