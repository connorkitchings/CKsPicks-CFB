"""Chronological preparation uses the real rating, offset, bridge and grading code."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
from cks_picks_cfb.season import inputs as season_inputs
from cks_picks_cfb.season import (
    projection_charts,
    projection_football,
    projection_serving,
)
from cks_picks_cfb.season import verification as v
from cks_picks_cfb.season.inputs import load_inputs
from cks_picks_cfb.season.manifest import canonical, sha
from cks_picks_cfb.season.runner import prepare, status
from tests.test_season_verification import synthetic_payload


def _fake_builder(keys, calls=None):
    """Stand-in for the real builders: a consistent payload for this run."""

    def build(*, frames, inputs, revision, identity, ratings_id, measurement_id):
        if calls is not None:
            calls.append(identity)
        payload = synthetic_payload(
            identity["release_id"],
            ratings_id,
            measurement_id,
            as_of=identity["as_of"],
            next_week_mode=identity["next_week_mode"],
        )
        return {key: payload[key] for key in keys}

    return build


@pytest.fixture(autouse=True)
def builder_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        projection_serving,
        "build_serving_core",
        _fake_builder(projection_serving.SERVING_KEYS, calls),
    )
    monkeypatch.setattr(
        projection_football,
        "build_football",
        _fake_builder(projection_football.FOOTBALL_KEYS),
    )
    monkeypatch.setattr(
        projection_charts,
        "build_charts",
        _fake_builder(projection_charts.CHART_KEYS),
    )
    # The chart_yardage_recomputed prepare check recomputes what the (fake)
    # chart builder produced.
    monkeypatch.setattr(
        projection_charts,
        "build_yardage_rows",
        lambda inputs, active_week: synthetic_payload()["team_game_yardage"],
    )
    return calls


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


def _mismatch_game_1(fixture, *, malformed=False):
    reader, _, revision = fixture
    events = pd.read_parquet(io.BytesIO(reader.objects["scoring_events"]))
    events.loc[0, "score_increment"] = 2
    if malformed:
        events.loc[0, "quality_reason"] = "impossible_score_increment"
    revision["inputs"]["scoring_events"] = reader.add("bad-events", events)


def _declare(fixture, tmp_path, monkeypatch, entries):
    """Pin ``entries`` as the revision's score exceptions file."""
    monkeypatch.setattr(season_inputs, "REPOSITORY", tmp_path)
    raw = json.dumps(entries).encode()
    (tmp_path / "exceptions.json").write_bytes(raw)
    fixture[2]["score_reconciliation_exceptions"] = {
        "uri": "exceptions.json",
        "sha256": sha(raw),
    }


@pytest.mark.parametrize("malformed", [False, True])
def test_unlisted_score_mismatch_is_rejected(fixture, tmp_path, malformed):
    _mismatch_game_1(fixture, malformed=malformed)
    with pytest.raises(
        ValueError, match="score reconciliation differs: game 1, team A"
    ):
        run(fixture, tmp_path / "out")


def test_listed_score_mismatch_passes(fixture, tmp_path, monkeypatch):
    _mismatch_game_1(fixture)
    entry = {"game_id": 1, "team": "A", "reason": "provider omits a field goal"}
    _declare(fixture, tmp_path, monkeypatch, [entry])
    manifest = run(fixture, tmp_path / "out")
    reader, model, revision = fixture
    assert load_inputs(reader, model, revision, 1).score_exceptions == {
        (1, "A"): entry["reason"]
    }
    assert manifest["revision_manifest_sha256"] == sha(canonical(revision))


def test_unused_score_exception_is_rejected(fixture, tmp_path, monkeypatch):
    _declare(
        fixture, tmp_path, monkeypatch, [{"game_id": 1, "team": "A", "reason": "x"}]
    )
    with pytest.raises(ValueError, match="unused score reconciliation exception"):
        run(fixture, tmp_path / "out")


def test_changed_score_exceptions_file_is_rejected(fixture, tmp_path, monkeypatch):
    _mismatch_game_1(fixture)
    _declare(
        fixture, tmp_path, monkeypatch, [{"game_id": 1, "team": "A", "reason": "x"}]
    )
    (tmp_path / "exceptions.json").write_bytes(b"[]")
    with pytest.raises(ValueError, match="checksum"):
        run(fixture, tmp_path / "out")


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


def _bytes(manifest):
    return {
        "manifest": Path(manifest["output_refs"]["model_manifest"]["uri"])
        .parent.joinpath("run-manifest.json")
        .read_bytes(),
        "verification": Path(manifest["verification_uri"]).read_bytes(),
        "payload": Path(
            manifest["output_refs"]["serving_projections"]["uri"]
        ).read_bytes(),
    }


def test_payload_is_written_and_bound_before_verification(
    fixture, tmp_path, builder_calls
):
    manifest = run(fixture, tmp_path)
    ref = manifest["output_refs"]["serving_projections"]
    raw = Path(ref["uri"]).read_bytes()
    payload = json.loads(raw)
    assert sha(raw) == ref["sha256"] and raw == canonical(payload)
    assert ref["logical_uri"] == (
        f"season-run:{manifest['release_id']}/serving-projections.json"
    )
    assert ref["rows"] == sum(map(len, payload.values()))
    assert builder_calls[0]["release_id"] == manifest["release_id"]
    report = json.loads(Path(manifest["verification_uri"]).read_bytes())
    assert report["schema_version"] == "season_verification_v2"
    assert report["output_refs"] == manifest["output_refs"]
    assert manifest["identities"] == v.lineage_identities(
        manifest["identity"], manifest["output_refs"]
    )
    assert set(report["checks"]["checksums_at_read"]["observed"]["outputs"]) == set(
        manifest["output_refs"]
    )
    v.validate_report(report, projections=payload, manifest=manifest)


def test_failed_projection_check_fails_closed_and_keeps_last_passed(
    fixture, tmp_path, monkeypatch
):
    first = run(fixture, tmp_path)
    passed = json.loads((tmp_path / "last-passed.json").read_bytes())

    def corrupt(**kwargs):
        tables = _fake_builder(projection_serving.SERVING_KEYS)(**kwargs)
        tables["system_stats"][0]["total_losses"] = 7
        return tables

    monkeypatch.setattr(projection_serving, "build_serving_core", corrupt)
    fixture[2]["revision_id"] = "r2"
    with pytest.raises(v.VerificationError, match="system_stats_match"):
        run(fixture, tmp_path)
    record = status(tmp_path)
    assert record["state"] == "failed"
    assert record["failed_checks"] == ["system_stats_match"]
    assert record["last_passed"] == passed
    assert passed["manifest_uri"].startswith(str(tmp_path / first["release_id"]))
    failed_dir = tmp_path / record["release_id"]
    assert not (failed_dir / "run-manifest.json").exists()
    assert not (failed_dir / "verification.json").exists()
    assert (failed_dir / "verification-failed.json").exists()


def test_failed_prepare_check_fails_closed(fixture, tmp_path, monkeypatch):
    monkeypatch.setattr("cks_picks_cfb.season.runner._reread", lambda refs: [])
    with pytest.raises(v.VerificationError, match="checksums_at_read"):
        run(fixture, tmp_path)
    assert status(tmp_path)["failed_checks"] == ["checksums_at_read"]
    assert not (tmp_path / "last-passed.json").exists()


def test_failed_input_read_keeps_last_passed_for_correction_report(fixture, tmp_path):
    first = run(fixture, tmp_path)
    reader, _, revision = fixture
    good = reader.objects["observations"]
    reader.objects["observations"] = good + b"changed"
    with pytest.raises(ValueError, match="checksum"):
        run(fixture, tmp_path)
    record = status(tmp_path)
    assert record["state"] == "failed"
    assert record["last_passed"]["manifest_uri"].endswith(
        f"{first['release_id']}/run-manifest.json"
    )
    reader.objects["observations"] = good
    revision["revision_id"] = "r2"
    second = run(fixture, tmp_path)
    report = json.loads(
        Path(second["output_refs"]["correction_report"]["uri"]).read_bytes()
    )
    assert report["previous_revision_sha256"] == first["revision_manifest_sha256"]
    assert status(tmp_path)["release_id"] == second["release_id"]


def test_preview_and_production_prepare_identical_bytes(fixture, tmp_path):
    import shutil

    reader, model, revision = fixture
    output = tmp_path / "prepared"
    outputs = {}
    for environment in ("preview", "production"):
        if output.exists():
            shutil.rmtree(output)
        manifest = prepare(
            model_raw=canonical(model),
            revision_raw=canonical(revision),
            reader=reader,
            through_week=1,
            next_week=2,
            as_of="2026-09-13T12:00:00Z",
            output=output,
            code_sha="a" * 40,
            environment=environment,
        )
        outputs[environment] = _bytes(manifest)
    assert outputs["preview"] == outputs["production"]
    for raw in outputs["preview"].values():
        content = raw.replace(str(output.resolve()).encode(), b"")
        assert b"preview" not in content and b"production" not in content
    with pytest.raises(ValueError, match="environment"):
        prepare(
            model_raw=canonical(model),
            revision_raw=canonical(revision),
            reader=reader,
            through_week=1,
            next_week=2,
            as_of="2026-09-13T12:00:00Z",
            output=output,
            code_sha="a" * 40,
            environment="staging",
        )


@pytest.fixture
def prepared(fixture, tmp_path):
    reader, model, revision = fixture
    manifest = run(fixture, tmp_path)
    frames = {
        name: pd.read_parquet(ref["uri"])
        for name, ref in manifest["output_refs"].items()
        if ref["uri"].endswith(".parquet")
    }
    return {
        "frames": frames,
        "inputs": load_inputs(reader, model, revision, 1),
        "model": model,
        "identity": manifest["identity"],
        "output_refs": manifest["output_refs"],
        "verified_outputs": sorted(manifest["output_refs"]),
        "revision": revision,
        "projections": json.loads(
            Path(manifest["output_refs"]["serving_projections"]["uri"]).read_bytes()
        ),
    }


def _failed_prepare(arguments):
    checks = v.derive_prepare_checks(arguments.pop("frames"), **arguments)
    assert set(checks) == v.REQUIRED_PREPARE_CHECKS
    return {name for name, entry in checks.items() if not entry["passed"]}


def _shift_evidence(arguments):
    frame = arguments["frames"]["rating_roles"].copy()
    row = frame.index[frame.target_week.eq(1)][0]
    explanation = json.loads(frame.at[row, "explanation"])
    explanation["evidence_contributions"][0]["source_week"] = 1
    frame.at[row, "explanation"] = json.dumps(explanation)
    arguments["frames"]["rating_roles"] = frame


def _assign(name, **columns):
    def mutate(arguments):
        frame = arguments["frames"][name]
        arguments["frames"][name] = frame.assign(
            **{k: f(frame) if callable(f) else f for k, f in columns.items()}
        )

    return mutate


def _tail(name):
    def mutate(arguments):
        arguments["frames"][name] = arguments["frames"][name].iloc[1:]

    return mutate


def _unverify(arguments):
    arguments["verified_outputs"] = arguments["verified_outputs"][1:]


def _miscount_explosive(arguments):
    """Both mirrored rows of game 1 carry the same wrong count, within bounds."""
    for row in arguments["projections"]["team_game_yardage"]:
        if row["game_id"] == 1:
            role = "off" if row["team"] == "A" else "def"
            row[f"{role}_explosive_n"] += 1


PREPARE_NEGATIVES = {
    "required_prior_week_data": _tail("measurements"),
    "score_reconciliation": _assign("scoring_events", score_increment=2.0),
    "earlier_week_only": _shift_evidence,
    "fixed_model_no_refit": _assign("predictions", model_ref="model:refit#margin"),
    "no_market_in_features": _assign("features", spread_line=-3.0),
    "ratings_equal_features": _assign(
        "features", home_offense=lambda f: f.home_offense + 1e-6
    ),
    "paired_predictions": _tail("predictions"),
    "checksums_at_read": _unverify,
    "chart_yardage_recomputed": _miscount_explosive,
}


def test_prepare_checks_pass_on_real_frames(prepared):
    assert _failed_prepare(prepared) == set()


@pytest.mark.parametrize("name", sorted(PREPARE_NEGATIVES))
def test_each_prepare_check_detects_its_violation(prepared, name):
    PREPARE_NEGATIVES[name](prepared)
    assert _failed_prepare(prepared) == {name}


def test_pinned_bridge_change_fails_fixed_model_check(prepared):
    prepared["model"] = {
        **prepared["model"],
        "inputs": {
            **prepared["model"]["inputs"],
            "bridge": {"uri": "bridge", "sha256": "0" * 64},
        },
    }
    assert _failed_prepare(prepared) == {"fixed_model_no_refit"}


@pytest.mark.parametrize(
    "mismatch, declared",
    [(True, False), (True, True), (False, True), (False, False)],
    ids=["unlisted", "listed", "unused", "exact"],
)
def test_prepare_and_verification_agree_on_score_reconciliation(
    fixture, prepared, tmp_path, monkeypatch, mismatch, declared
):
    if mismatch:
        _mismatch_game_1(fixture)
    if declared:
        entry = {"game_id": 1, "team": "A", "reason": "x"}
        _declare(fixture, tmp_path, monkeypatch, [entry])
    reader, model, revision = fixture
    try:
        load_inputs(reader, model, revision, 1)
        refused = []
    except ValueError as error:
        refused = str(error).split("; ")
    events = pd.read_parquet(
        io.BytesIO(reader.read_bytes(revision["inputs"]["scoring_events"]["uri"]))
    )
    prepared["frames"]["scoring_events"] = events
    prepared["inputs"].score_exceptions = season_inputs.score_exceptions(revision)
    check = v.derive_prepare_checks(prepared.pop("frames"), **prepared)
    assert check["score_reconciliation"]["passed"] is (not refused)
    assert check["score_reconciliation"]["observed"]["examples"] == refused
    assert bool(refused) is (mismatch != declared)
