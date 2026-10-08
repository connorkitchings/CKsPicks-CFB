"""The corrected-run loader reads exactly the published frames the successor builders need."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import successor_sources as ss


class _Run:
    def __init__(self):
        self.requested: list[str] = []

    def frame(self, relative: str) -> pd.DataFrame:
        self.requested.append(relative)
        if relative == "eligibility/population_raw.parquet":
            return pd.DataFrame(
                {
                    "season": [2025, 2025],
                    "game_id": [1, 2],
                    "schedule_completed": [True, False],
                    "home_points": [10.0, None],
                    "away_points": [3.0, None],
                }
            )
        return pd.DataFrame({"path": [relative]})


@pytest.fixture
def run(monkeypatch):
    import cks_picks_cfb.data.data_first_possession_v1 as population

    monkeypatch.setattr(
        population, "build_population", lambda raw, scope: raw.assign(scope=scope)
    )
    return _Run()


def test_the_nine_cache_frames_come_from_the_named_published_objects(run):
    frames = ss.historical_frames(run)
    assert tuple(frames) == ss.HISTORICAL_FRAMES
    assert sorted(run.requested) == sorted(
        [
            "eligibility/population_raw.parquet",
            "ratings/observations.parquet",
            "ratings/terminal.parquet",
            "forecast/feature_frame.parquet",
            "ratings/snapshots.parquet",
            "ratings/priors.parquet",
            "ratings/rating_states.parquet",
        ]
    )
    assert frames["population"]["scope"].eq("historical").all()
    assert frames["v5_predictions"].empty


def test_outcomes_are_the_population_outcome_columns_with_completed_renamed(run):
    outcomes = ss.historical_frames(run)["outcomes"]
    assert list(outcomes.columns) == ss.OUTCOME_COLUMNS
    assert outcomes["completed"].tolist() == [True, False]


def test_the_cache_files_are_written_under_the_builders_names(run, tmp_path):
    rows = ss.write_historical_cache(run, tmp_path / "cache")
    assert set(rows) == set(ss.HISTORICAL_FRAMES)
    for name in ss.HISTORICAL_FRAMES:
        assert (tmp_path / "cache" / f"{name}.parquet").exists()


# ---------------------------------------------------------------------------
# Lock-driven access and the pinned-run opener
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402
import json  # noqa: E402

from cks_picks_cfb.data.data_first_phase2d import signed_payload  # noqa: E402
from cks_picks_cfb.rebuild.errors import GateError  # noqa: E402
from cks_picks_cfb.rebuild.published import open_pinned_run  # noqa: E402

LINEAGE = {
    "kind": "corrected_rebuild",
    "rebuild_run_id": "6a-x",
    "rebuild_root_raw_sha256": "a" * 64,
    "task4_run_id": "task4-x",
    "task4_receipt_raw_sha256": "b" * 64,
}


def test_only_a_lock_with_a_corrected_lineage_counts_as_corrected():
    assert ss.is_corrected({"corrected_lineage": LINEAGE})
    assert not ss.is_corrected({})
    with pytest.raises(GateError, match="not a corrected successor lock"):
        ss.lineage({})
    with pytest.raises(GateError):
        ss.lineage({"corrected_lineage": {"kind": "other"}})


def test_corrected_parents_name_the_rebuild_the_receipt_and_the_lock_hash():
    raw = b'{"lock": true}'
    parents = ss.corrected_parents({"corrected_lineage": LINEAGE}, raw)
    assert parents["corrected_rebuild"] == {
        "uri": "rebuild/6a/6a-x/root-manifest.json",
        "raw_sha256": "a" * 64,
    }
    assert parents["task4_receipt"]["uri"] == "rebuild/6a/task4-x/receipt/receipt.json"
    assert parents["source_lock"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()


class _Storage:
    def __init__(self, objects):
        self.objects = objects

    def read_bytes(self, key):
        return self.objects[key]


def _root(run_id="run-x"):
    payload = signed_payload(
        {
            "kind": "rebuild_root_v1",
            "run_id": run_id,
            "namespace": "rebuild/6a/",
            "objects": {
                f"rebuild/6a/{run_id}/a.json": hashlib.sha256(b"A").hexdigest()
            },
        }
    )
    return json.dumps(payload, sort_keys=True).encode()


def test_a_pinned_run_reads_only_what_its_root_hashed():
    raw = _root()
    storage = _Storage(
        {"rebuild/6a/run-x/root-manifest.json": raw, "rebuild/6a/run-x/a.json": b"A"}
    )
    run = open_pinned_run(storage, "run-x", hashlib.sha256(raw).hexdigest())
    assert run.read("rebuild/6a/run-x/a.json") == b"A"
    storage.objects["rebuild/6a/run-x/a.json"] = b"changed"
    with pytest.raises(GateError, match="changed"):
        run.read("rebuild/6a/run-x/a.json")
    with pytest.raises(GateError, match="not in the published root"):
        run.read("rebuild/6a/run-x/other.json")


def test_a_pinned_run_refuses_a_different_root_or_run_id():
    raw = _root()
    storage = _Storage({"rebuild/6a/run-x/root-manifest.json": raw})
    with pytest.raises(GateError, match="changed"):
        open_pinned_run(storage, "run-x", "0" * 64)
    other = _root("other")
    storage = _Storage({"rebuild/6a/run-x/root-manifest.json": other})
    with pytest.raises(GateError, match="not the published rebuild root"):
        open_pinned_run(storage, "run-x", hashlib.sha256(other).hexdigest())


def test_a_lock_without_a_live_week_returns_only_replay_features(monkeypatch):
    frames = pd.DataFrame({"week": [0, 1, 5], "game_id": [1, 2, 3]})

    class _Replay:
        def frame(self, relative):
            assert relative == "application_frames/frames.parquet"
            return frames

    monkeypatch.setattr(ss, "replay_run", lambda storage, lock: _Replay())
    monkeypatch.setattr(
        ss, "lock_schedule", lambda storage, lock: pd.DataFrame({"x": [1]})
    )
    lock = {"active_week": {"week": 6}, "corrected_lineage": LINEAGE}
    schedule, replay, live = ss.forecast_inputs(object(), lock)
    assert replay["game_id"].tolist() == [1, 2, 3] and live.empty and len(schedule) == 1


def test_a_live_week_needs_current_states_and_a_real_as_of(monkeypatch):
    class _Replay:
        def frame(self, relative):
            return pd.DataFrame({"week": [0, 5], "game_id": [1, 2]})

    monkeypatch.setattr(ss, "replay_run", lambda storage, lock: _Replay())
    monkeypatch.setattr(ss, "lock_schedule", lambda storage, lock: pd.DataFrame())
    lock = {
        "active_week": {"week": 6},
        "corrected_lineage": {**LINEAGE, "live_week": {"week": 6}},
    }
    with pytest.raises(GateError, match="live as_of"):
        ss.forecast_inputs(object(), lock)
    with pytest.raises(GateError, match="live as_of"):
        ss.forecast_inputs(object(), lock, current_teams=pd.DataFrame())
