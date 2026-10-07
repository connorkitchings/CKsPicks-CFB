"""Legacy evidence rejects fabricated timelines, changed bytes and wrong environments."""

import copy
import hashlib
import io
import subprocess

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops import prospective_records as records


class Storage:
    def __init__(self):
        self.objects = {}

    def read_bytes(self, uri):
        return self.objects[uri]

    def ref(self, uri, raw):
        self.objects[uri] = raw
        return dict(uri=uri, sha256=hashlib.sha256(raw).hexdigest())


@pytest.fixture
def evidence(monkeypatch):
    storage = Storage()
    artifact = storage.ref(
        "artifacts/preview/predictions/year=2026/week=5/run_id=original/predictions.csv",
        b"original forecasts",
    )
    schedule = pd.DataFrame([dict(game_id=1, start_date="2026-10-02T00:00:00+00:00")])
    buf = io.BytesIO()
    schedule.rename(columns={"start_date": "kickoff_utc"}).assign(
        __captured_at="2026-09-29T12:00:00+00:00"
    ).to_parquet(buf)
    schedule_ref = storage.ref("lake/original-schedule.parquet", buf.getvalue())
    run = dict(
        run_id="original",
        season=2026,
        week=5,
        model_id="v5-intended-update-2026-v1",
        evidence_class="live",
        state="scored",
        frozen_at="2026-09-30T12:00:00+00:00",
        expected_games=1,
        artifact_uri=artifact["uri"],
        artifact_sha256=artifact["sha256"],
        model_bundle_sha256="b" * 64,
        config_sha="c" * 64,
        data_as_of="2026-09-29T12:00:00+00:00",
        input_dataset_refs=[dict(dataset="games", uri=schedule_ref["uri"])],
    )
    manifest_ref = storage.ref(
        "artifacts/preview/predictions/year=2026/week=5/run_id=original/manifest.json",
        records.canonical_json(run),
    )
    pipeline = dict(
        pipeline_run_id="freeze",
        environment="preview",
        command="freeze-week",
        state="succeeded",
        started_at="2026-09-30T11:59:00+00:00",
        finished_at="2026-09-30T12:01:00+00:00",
    )
    step = dict(
        pipeline_run_id="freeze",
        step_name="freeze",
        state="succeeded",
        error_category=None,
        output_refs=[dict(argv=["scripts/pipeline/freeze_week.py"], returncode=0)],
    )
    sources = dict(
        environment="preview",
        runs=[run],
        schedule=schedule.to_dict("records"),
        selection_history=[
            dict(
                selection_id=1,
                run_id="original",
                prior_run_id=None,
                selected_at="2026-09-30T11:00:00+00:00",
            )
        ],
        activations=[
            dict(
                run_id="original",
                action="freeze",
                environment="preview",
                activated_at=run["frozen_at"],
                metadata=dict(freeze_coverage_complete=True),
            )
        ],
        pipelines=[pipeline],
        steps=[step],
    )
    code_sha = subprocess.check_output(
        ["git", "rev-parse", "446c880^{commit}"], text=True
    ).strip()
    code = dict(
        code_sha=code_sha,
        freeze_source=subprocess.check_output(
            ["git", "show", code_sha + ":scripts/pipeline/freeze_week.py"], text=True
        ),
    )
    refs = [
        storage.ref("source-query.json", records.canonical_json(sources)),
        storage.ref("historical-code.json", records.canonical_json(code)),
    ]
    monkeypatch.setattr(
        records, "read_legacy_freeze_sources", lambda *a, **kw: copy.deepcopy(sources)
    )
    kwargs = dict(
        sources=sources,
        environment="preview",
        run_id="original",
        decision_ref="exact-test-decision",
        historical_freeze_code_sha=code_sha,
        original_prediction_manifest=manifest_ref,
        original_prediction_artifact=artifact,
        contemporaneous_schedule_evidence=schedule_ref,
        source_snapshot_refs=refs,
    )
    return sources, storage, kwargs


def test_independent_source_and_raw_hash_verification(evidence):
    sources, storage, kwargs = evidence
    payload = records.build_legacy_freeze_attestation(**kwargs)
    records.verify_legacy_freeze_attestation(
        payload, cur=None, storage=storage, environment="preview"
    )
    assert payload["evidence_class"] == "legacy_attested_prospective"
    assert records._utc(payload["attested_at"]) > records._utc(
        payload["first_kickoff_utc"]
    )
    raw = records.canonical_json(payload)
    uri = records.legacy_attestation_uri(payload)
    storage.objects[uri] = raw
    row = dict(
        season=2026,
        week=5,
        run_id="original",
        decision_ref=kwargs["decision_ref"],
        frozen_at=payload["run_frozen_at"],
        first_kickoff_utc=payload["first_kickoff_utc"],
        freeze_receipt_uri=uri,
        freeze_receipt_sha256=hashlib.sha256(raw).hexdigest(),
    )
    records.verify_prospective_record(
        row, cur=None, storage=storage, environment="preview"
    )
    storage.objects[kwargs["original_prediction_artifact"]["uri"]] = b"changed"
    with pytest.raises(records.ProspectiveRecordError, match="hash"):
        records.verify_prospective_record(
            row, cur=None, storage=storage, environment="preview"
        )


@pytest.mark.parametrize(
    "change",
    [
        "pipeline",
        "selection",
        "freeze",
        "schedule",
        "returncode",
        "environment",
        "replay",
    ],
)
def test_builder_fails_closed_on_missing_or_conflicting_evidence(evidence, change):
    sources, _, kwargs = evidence
    if change == "pipeline":
        sources["environment"] = "production"
        kwargs["environment"] = "production"
        sources["pipelines"] = []
    if change == "selection":
        sources["selection_history"][0]["run_id"] = "another"
    if change == "freeze":
        sources["activations"][0]["metadata"] = {}
    if change == "schedule":
        sources["schedule"] = []
    if change == "returncode":
        sources["steps"][0]["output_refs"][0]["returncode"] = 1
    if change == "replay":
        sources["runs"][0]["evidence_class"] = "replay"
    if change == "environment":
        sources["environment"] = "production"
    with pytest.raises(records.ProspectiveRecordError):
        records.build_legacy_freeze_attestation(**kwargs)


def test_preview_allows_null_freeze_pipeline_with_disclosure(evidence):
    sources, storage, kwargs = evidence
    sources["pipelines"] = []
    sources["steps"] = []
    kwargs["source_snapshot_refs"][0] = storage.ref(
        "source-query.json", records.canonical_json(sources)
    )
    payload = records.build_legacy_freeze_attestation(**kwargs)
    assert payload["freeze_pipeline"] is None
    assert records.PREVIEW_PIPELINE_LIMITATION in payload["limitations"]
    records.verify_legacy_freeze_attestation(
        payload, cur=None, storage=storage, environment="preview"
    )


def test_rechecksum_does_not_hide_live_drift_or_bad_timestamp(evidence):
    sources, storage, kwargs = evidence
    payload = records.build_legacy_freeze_attestation(**kwargs)
    payload["attested_at"] = "2026-09-30T12:00:00+00:00"
    with pytest.raises(records.ProspectiveRecordError, match="timestamp"):
        records.verify_legacy_freeze_attestation(
            signed_payload(payload), cur=None, storage=storage, environment="preview"
        )
    payload = records.build_legacy_freeze_attestation(**kwargs)
    sources["selection_history"][0]["selected_at"] = "2026-09-30T10:00:00+00:00"
    with pytest.raises(records.ProspectiveRecordError, match="changed"):
        records.verify_legacy_freeze_attestation(
            payload, cur=None, storage=storage, environment="preview"
        )


def test_caller_cannot_supply_creation_time(evidence):
    with pytest.raises(TypeError):
        records.build_legacy_freeze_attestation(**evidence[2], attested_at="2026-09-30")


def test_registration_insert_retry_conflict_and_readback(evidence):
    _, storage, kwargs = evidence
    storage.exists = lambda uri: uri in storage.objects
    storage.write_bytes = lambda raw, uri: storage.objects.__setitem__(uri, raw)
    payload = records.build_legacy_freeze_attestation(**kwargs)

    class Cursor:
        prior = None
        inserts = 0

        def execute(self, sql, params=None):
            if sql.startswith("INSERT"):
                self.prior = params
                self.inserts += 1

        def fetchone(self):
            return self.prior

    cur = Cursor()
    result = records.register_legacy_freeze_attestation(
        cur, storage=storage, environment="preview", payload=payload
    )
    assert not result["idempotent"]
    assert records.register_legacy_freeze_attestation(
        cur, storage=storage, environment="preview", payload=payload
    )["idempotent"]
    assert cur.inserts == 1
    other = dict(payload, decision_ref="different-decision")
    with pytest.raises(records.ProspectiveRecordError, match="conflicts"):
        records.register_legacy_freeze_attestation(
            cur, storage=storage, environment="preview", payload=signed_payload(other)
        )
