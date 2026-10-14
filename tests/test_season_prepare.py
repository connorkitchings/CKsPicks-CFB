"""Chronological preparation uses the real rating, offset, bridge and grading code."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
from cks_picks_cfb.season.manifest import canonical, sha
from cks_picks_cfb.season.runner import prepare, status


class MemoryReader:
    def __init__(self):
        self.objects = {}

    def add(self, name, value):
        if isinstance(value, pd.DataFrame):
            output = io.BytesIO()
            value.to_parquet(output, index=False)
            raw = output.getvalue()
        else:
            raw = canonical(value)
        self.objects[name] = raw
        return {"uri": name, "sha256": sha(raw)}

    def read_bytes(self, path):
        return self.objects[path]


@pytest.fixture
def fixture():
    reader = MemoryReader()
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": w,
                "game_id": w + 1,
                "kickoff_utc": f"2026-09-{5 + 7 * w:02}T12:00:00Z",
                "home_team": "A",
                "away_team": "B",
            }
            for w in range(3)
        ]
    )
    finals = pd.DataFrame(
        [
            {"season": 2026, "game_id": i, "home_points": 3, "away_points": 0}
            for i in (1, 2)
        ]
    )
    plays = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": i - 1,
                "game_id": i,
                "drive_number": 1,
                "play_number": 1,
                "offense": "A",
                "defense": "B",
                "quarter": 1,
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "play_type": "Field Goal Good",
                "garbage": 0,
                "ppa": None,
                "offense_score": 3,
                "defense_score": 0,
            }
            for i in (1, 2)
        ]
    )
    drives = pd.DataFrame(
        [{"season": 2026, "game_id": i, "drive_number": 1} for i in (1, 2)]
    )
    observations = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": g.week,
                "game_id": g.game_id,
                "kickoff_utc": g.kickoff_utc,
                "team": team,
                "opponent": opponent,
                "measurement_id": "ppp",
                "unit_role": role,
                "raw_value": 1.2 if team == "A" else 0.8,
                "numerator": 9.6 if team == "A" else 6.4,
                "denominator": 8.0,
                "coverage_status": "observed",
            }
            for g in schedule.iloc[:2].itertuples()
            for team, opponent in (("A", "B"), ("B", "A"))
            for role in ("offense", "defense")
        ]
    )
    events = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": i,
                "team": "A",
                "period_class": "regulation",
                "scoring_category": "regulation_offense",
                "score_increment": 3.0,
                "source_event_id": str(i),
                "quality_reason": None,
            }
            for i in (1, 2)
        ]
    )
    historical = pd.DataFrame(
        [
            {
                "season": s,
                "week": 0,
                "game_id": s,
                "kickoff_utc": f"{s}-09-01T12:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "forecast_eligible": True,
                "schedule_completed": True,
                "outcome_valid": True,
                "measurement_usable": True,
            }
            for s in DEVELOPMENT_SEASONS
        ]
    )
    old_events = pd.DataFrame(
        [
            {
                "season": s,
                "game_id": s,
                "team": "A",
                "period_class": "regulation",
                "scoring_category": "regulation_offense",
                "score_increment": 0.0,
            }
            for s in DEVELOPMENT_SEASONS
        ]
    )
    priors = pd.DataFrame(
        [
            {
                "season": 2026,
                "team": t,
                "unit_role": r,
                "prior_mean": 0.0,
                "prior_variance": 1.0,
            }
            for t in "AB"
            for r in ("offense", "defense")
        ]
    )
    terminal = pd.DataFrame(
        [
            {
                "season": 2025,
                "team": t,
                "unit_role": r,
                "measurement_id": "ppp",
                "adjusted_value": 0.8 + i * 0.4,
                "primary_exposure": 8.0,
            }
            for i, t in enumerate("AB")
            for r in ("offense", "defense")
        ]
    )
    bundle = json.loads(
        (
            Path(__file__).resolve().parents[1] / "conf/rebuild/bundle_b2_w5_v1.json"
        ).read_bytes()
    )
    model = {
        "schema_version": "season_model_v1",
        "model_id": "v5-intended-update-2026-v1",
        "design": "ppp__rho_0_60__exposure",
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "inputs": {
            name: reader.add(name, value)
            for name, value in {
                "bridge": bundle,
                "priors": priors,
                "terminal": terminal,
                "historical_population": historical,
                "historical_events": old_events,
            }.items()
        },
    }
    revision = {
        "schema_version": "season_revision_v1",
        "season": 2026,
        "revision_id": "r1",
        "captured_at": "2026-09-13T12:00:00Z",
        "pre_week_cutoffs": {"0": "2026-09-05T10:00:00Z", "1": "2026-09-12T10:00:00Z"},
        "inputs": {
            name: reader.add(name, value)
            for name, value in {
                "schedule": schedule,
                "finals": finals,
                "byplay": plays,
                "drives": drives,
                "reconciliation": pd.DataFrame(
                    {"game_id": [1, 2], "blocking": [False, False]}
                ),
                "observations": observations,
                "scoring_events": events,
            }.items()
        },
    }
    return reader, model, revision


def run(fixture, output):
    reader, model, revision = fixture
    return prepare(
        model_raw=canonical(model),
        revision_raw=canonical(revision),
        reader=reader,
        through_week=1,
        next_week=2,
        as_of="2026-09-13T12:00:00Z",
        output=output,
        code_sha="a" * 40,
    )


def test_real_replay_live_and_warm_retry(fixture, tmp_path):
    manifest = run(fixture, tmp_path)
    predictions = pd.read_parquet(manifest["output_refs"]["predictions"]["uri"])
    assert len(predictions) == 6
    assert set(predictions.timing_class) == {"replay", "live"}
    assert manifest == run(fixture, tmp_path)
    assert status(tmp_path)["resumed"] is True
    assert (
        pd.read_parquet(manifest["output_refs"]["ratings"]["uri"]).target_week.max()
        == 2
    )


@pytest.mark.parametrize("name", ["drives", "finals", "byplay"])
def test_missing_required_game_blocks_advancement(fixture, tmp_path, name):
    reader, model, revision = fixture
    table = pd.read_parquet(io.BytesIO(reader.objects[name]))
    revision["inputs"][name] = reader.add(name, table[table.game_id.ne(2)])
    with pytest.raises(ValueError, match="missing|required|final scores"):
        run(fixture, tmp_path)


def test_checksum_changed_on_warm_retry_is_rejected(fixture, tmp_path):
    run(fixture, tmp_path)
    fixture[0].objects["observations"] += b"changed"
    with pytest.raises(ValueError, match="checksum"):
        run(fixture, tmp_path)


def test_changed_output_is_not_cached_success(fixture, tmp_path):
    manifest = run(fixture, tmp_path)
    Path(manifest["output_refs"]["grades"]["uri"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        status(tmp_path)


def test_provider_correction_rebuilds_later_history_only(fixture, tmp_path):
    before = run(fixture, tmp_path)
    reader, model, revision = fixture
    observations = pd.read_parquet(io.BytesIO(reader.objects["observations"]))
    selected = observations.game_id.eq(1) & observations.team.eq("A")
    observations.loc[selected, "raw_value"] += 1
    observations.loc[selected, "numerator"] += 8
    revision["revision_id"] = "r2"
    revision["inputs"]["observations"] = reader.add("observations-r2", observations)
    after = run(fixture, tmp_path)
    left = pd.read_parquet(before["output_refs"]["predictions"]["uri"])
    right = pd.read_parquet(after["output_refs"]["predictions"]["uri"])
    assert before["release_id"] != after["release_id"]
    assert (
        left[left.week.eq(0)]["mean"].tolist()
        == right[right.week.eq(0)]["mean"].tolist()
    )
    assert (
        left[left.week.eq(1)]["mean"].tolist()
        != right[right.week.eq(1)]["mean"].tolist()
    )


def test_prior_week_availability_cannot_be_waived(fixture, tmp_path):
    fixture[2]["pre_week_cutoffs"]["1"] = "2026-09-05T13:00:00Z"
    with pytest.raises(ValueError, match="unavailable"):
        run(fixture, tmp_path)


def test_score_reconciliation_mismatch_is_rejected(fixture, tmp_path):
    reader, _, revision = fixture
    events = pd.read_parquet(io.BytesIO(reader.objects["scoring_events"]))
    events.loc[0, "score_increment"] = 2
    revision["inputs"]["scoring_events"] = reader.add("bad-events", events)
    with pytest.raises(ValueError, match="score reconciliation"):
        run(fixture, tmp_path)


def test_nullable_measurement_is_retained_without_fake_value(fixture, tmp_path):
    reader, _, revision = fixture
    obs = pd.read_parquet(io.BytesIO(reader.objects["observations"]))
    obs.loc[0, ["raw_value", "numerator"]] = None
    obs.loc[0, "coverage_status"] = "excluded"
    revision["inputs"]["observations"] = reader.add("nullable", obs)
    run(fixture, tmp_path)


def test_prekickoff_target_precedence_and_retrospective_timestamp(fixture, tmp_path):
    reader, _, revision = fixture
    rows = [
        {
            "game_id": 1,
            "target": "spread",
            "point": -3.0,
            "canonical_line": -2.0,
            "provider": "book",
            "captured_at": "2026-09-05T11:00:00Z",
            "quote_id": "pre",
            "snapshot_id": "s1",
        }
    ]
    fallback = [
        {
            "game_id": 1,
            "target": t,
            "point": point,
            "canonical_line": point,
            "provider": "CFBD",
            "captured_at": "2026-09-13T12:00:00Z",
            "quote_id": "cfbd-" + t,
            "snapshot_id": "historical",
        }
        for t, point in (("spread", -20.0), ("total", 40.0))
    ]
    revision["inputs"]["market_quotes"] = reader.add("quotes", pd.DataFrame(rows))
    revision["inputs"]["historical_lines"] = reader.add(
        "fallback", pd.DataFrame(fallback)
    )
    manifest = run(fixture, tmp_path)
    grades = pd.read_parquet(manifest["output_refs"]["grades"]["uri"])
    spread = grades[grades.game_id.eq(1) & grades.target.eq("spread")].iloc[0]
    total = grades[grades.game_id.eq(1) & grades.target.eq("total")].iloc[0]
    assert spread.quote_id == "pre"
    assert spread.benchmark_type == "retained_prekickoff"
    assert total.benchmark_type == "cfbd_retrospective"
    assert total.captured_at == "2026-09-13T12:00:00+00:00"
    assert grades[grades.game_id.eq(2)].result.isna().all()


def test_measurements_are_derived_from_real_normalized_plays(fixture, tmp_path):
    _, _, revision = fixture
    revision["inputs"].pop("observations")
    revision["inputs"].pop("scoring_events")
    manifest = run(fixture, tmp_path)
    measurements = pd.read_parquet(manifest["output_refs"]["measurements"]["uri"])
    assert set(measurements.game_id) == {1, 2}
    assert len(measurements) == 64


def test_wide_lake_quotes_use_consensus_before_best_quote(fixture, tmp_path):
    reader, _, revision = fixture
    quotes = pd.DataFrame(
        [
            {
                "game_id": 1,
                "quote_id": "consensus",
                "provider": "Consensus",
                "captured_at": "2026-09-05T11:00:00Z",
                "spread": -2.0,
                "total": 40.0,
            },
            {
                "game_id": 1,
                "quote_id": "book",
                "provider": "book",
                "captured_at": "2026-09-05T11:00:00Z",
                "spread": 2.0,
                "total": 42.0,
            },
        ]
    )
    revision["inputs"]["market_quotes"] = reader.add("wide-quotes", quotes)
    manifest = run(fixture, tmp_path)
    grades = pd.read_parquet(manifest["output_refs"]["grades"]["uri"])
    assert set(grades[grades.game_id.eq(1)].benchmark_type) == {"retained_prekickoff"}


def test_drive_linkage_is_required(fixture, tmp_path):
    reader, _, revision = fixture
    drives = pd.read_parquet(io.BytesIO(reader.objects["drives"]))
    drives["drive_number"] = 2
    revision["inputs"]["drives"] = reader.add("bad-drives", drives)
    with pytest.raises(ValueError, match="absent drive"):
        run(fixture, tmp_path)


def test_incomplete_nonblocking_reconciliation_is_not_accepted(fixture, tmp_path):
    reader, _, revision = fixture
    table = pd.DataFrame(
        {
            "game_id": [1, 2],
            "blocking": [False, False],
            "classification": ["exact_match", "incomplete_source"],
        }
    )
    revision["inputs"]["reconciliation"] = reader.add("incomplete", table)
    with pytest.raises(ValueError, match="incomplete"):
        run(fixture, tmp_path)


def test_reconstruct_next_week_keeps_started_games_without_freeze(fixture, tmp_path):
    reader, model, revision = fixture
    revision["pre_week_cutoffs"]["2"] = "2026-09-19T10:00:00Z"
    revision["captured_at"] = "2026-09-19T13:00:00Z"
    manifest = prepare(
        model_raw=canonical(model),
        revision_raw=canonical(revision),
        reader=reader,
        through_week=1,
        next_week=2,
        as_of="2026-09-19T13:00:00Z",
        output=tmp_path,
        code_sha="a" * 40,
        reconstruct_next_week=True,
    )
    predictions = pd.read_parquet(manifest["output_refs"]["predictions"]["uri"])
    assert set(predictions.game_id) == {1, 2, 3}
    assert set(predictions.timing_class) == {"replay"}
    assert manifest["captured_at"] == "2026-09-19T13:00:00Z"
    assert manifest["next_week_mode"] == "reconstructed"
    assert "freeze_receipt" not in manifest


def test_real_measurement_warm_retry_reuses_checked_cache(
    fixture, tmp_path, monkeypatch
):
    _, _, revision = fixture
    revision["inputs"].pop("observations")
    revision["inputs"].pop("scoring_events")
    before = run(fixture, tmp_path)

    def unexpected(**kwargs):
        raise AssertionError("unchanged measurements must be cached")

    monkeypatch.setattr("cks_picks_cfb.season.inputs.build_measurements", unexpected)
    assert run(fixture, tmp_path) == before


def test_post_week_state_contains_exact_completed_evidence(fixture, tmp_path):
    manifest = run(fixture, tmp_path)
    roles = pd.read_parquet(manifest["output_refs"]["current_rating_roles"]["uri"])
    a = roles[
        roles.post_week.eq(1) & roles.team.eq("A") & roles.unit_role.eq("offense")
    ].iloc[0]
    assert json.loads(a.source_game_ids) == [1, 2]
    assert a.usable_exposure == 16.0


def test_fixed_bundle_refit_is_not_accepted(fixture, tmp_path):
    reader, model, _ = fixture
    bundle = json.loads(reader.objects["bridge"])
    bundle["targets"]["margin"]["intercept"] += 1
    model["inputs"]["bridge"] = reader.add("refitted", bundle)
    with pytest.raises(ValueError, match="B2"):
        run(fixture, tmp_path)


def test_correction_report_counts_later_changed_forecasts(fixture, tmp_path):
    run(fixture, tmp_path)
    reader, _, revision = fixture
    observations = pd.read_parquet(io.BytesIO(reader.objects["observations"]))
    selected = observations.game_id.eq(1) & observations.team.eq("A")
    observations.loc[selected, "raw_value"] += 1
    observations.loc[selected, "numerator"] += 8
    revision["inputs"]["observations"] = reader.add(
        "updated-observations", observations
    )
    manifest = run(fixture, tmp_path)
    report = json.loads(
        Path(manifest["output_refs"]["correction_report"]["uri"]).read_bytes()
    )
    assert report["source_revision_changed"] is True
    assert report["output_changes"]["predictions"]["changed"] > 0
    assert report["output_changes"]["predictions"]["added"] == 0
