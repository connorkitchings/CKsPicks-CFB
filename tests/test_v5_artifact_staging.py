import hashlib
import json

import pytest

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.ops import v5_artifact_staging as staging
from cks_picks_cfb.ratings_lab.artifacts import canonical_json


class Store:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.writes = []

    def exists(self, uri):
        return uri in self.objects

    def read_bytes(self, uri):
        return self.objects[uri]

    def write_bytes(self, raw, uri):
        self.writes.append(uri)
        self.objects[uri] = raw


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _source(week=0, run_id="r-0"):
    pred_raw, scored_raw = b"game_id\n1\n", b"game_id,result\n1,w\n"
    pdir = f"artifacts/preview/predictions/year=2026/week={week}/run_id={run_id}"
    sdir = f"artifacts/preview/scored/year=2026/week={week}/run_id={run_id}"
    manifest = {
        "schema_version": "prediction_run_v1",
        "run_id": run_id,
        "week": week,
        "artifact_uri": f"{pdir}/predictions.csv",
        "artifact_sha256": _sha(pred_raw),
    }
    scored = {
        "schema_version": "scored_run_v1",
        "run_id": run_id,
        "week": week,
        "artifact_uri": f"{sdir}/scored.csv",
        "artifact_sha256": _sha(scored_raw),
        "prediction_artifact_sha256": _sha(pred_raw),
    }
    return Store(
        {
            manifest["artifact_uri"]: pred_raw,
            f"{pdir}/manifest.json": canonical_json(manifest),
            scored["artifact_uri"]: scored_raw,
            f"{sdir}/manifest.json": canonical_json(scored),
        }
    )


def test_dry_run_plans_without_writing_and_signs_a_receipt():
    source, target = _source(), Store()
    receipt = staging.stage_runs(
        source, target, {0: "r-0"}, source="preview", target="production", apply=False
    )
    verify_signed_payload(receipt)
    assert target.writes == []
    states = {o["state"] for o in receipt["runs"][0]["objects"]}
    assert states == {"would_write"}
    assert all("/production/" in o["uri"] for o in receipt["runs"][0]["objects"])


def test_apply_rewrites_only_artifact_uri_and_keeps_csv_bytes():
    source, target = _source(), Store()
    staging.stage_runs(
        source, target, {0: "r-0"}, source="preview", target="production", apply=True
    )
    manifest = json.loads(
        target.objects[
            "artifacts/production/predictions/year=2026/week=0/run_id=r-0/manifest.json"
        ]
    )
    assert manifest["artifact_uri"].startswith("artifacts/production/")
    assert manifest["artifact_sha256"] == _sha(target.objects[manifest["artifact_uri"]])
    original = json.loads(
        source.objects[
            "artifacts/preview/predictions/year=2026/week=0/run_id=r-0/manifest.json"
        ]
    )
    assert {k: v for k, v in manifest.items() if k != "artifact_uri"} == {
        k: v for k, v in original.items() if k != "artifact_uri"
    }


def test_rerun_is_idempotent_and_a_conflicting_object_stops_everything():
    source, target = _source(), Store()
    args = (source, target, {0: "r-0"})
    kw = dict(source="preview", target="production", apply=True)
    staging.stage_runs(*args, **kw)
    first = len(target.writes)
    again = staging.stage_runs(*args, **kw)
    assert len(target.writes) == first
    assert {o["state"] for o in again["runs"][0]["objects"]} == {"present"}
    key = "artifacts/production/scored/year=2026/week=0/run_id=r-0/scored.csv"
    target.objects[key] = b"tampered"
    with pytest.raises(staging.StagingError, match="differs"):
        staging.stage_runs(*args, **kw)


def test_corrupt_source_and_bad_environments_are_refused():
    source = _source()
    key = "artifacts/preview/predictions/year=2026/week=0/run_id=r-0/predictions.csv"
    source.objects[key] = b"changed"
    with pytest.raises(staging.StagingError, match="checksums"):
        staging.stage_runs(
            source,
            Store(),
            {0: "r-0"},
            source="preview",
            target="production",
            apply=True,
        )
    with pytest.raises(staging.StagingError, match="different"):
        staging.stage_runs(
            _source(),
            Store(),
            {0: "r-0"},
            source="preview",
            target="preview",
            apply=False,
        )


def test_nothing_is_written_when_a_later_run_is_invalid():
    source, target = _source(), Store()
    with pytest.raises(KeyError):
        staging.stage_runs(
            source,
            target,
            {0: "r-0", 1: "missing"},
            source="preview",
            target="production",
            apply=True,
        )
    assert target.writes == []
