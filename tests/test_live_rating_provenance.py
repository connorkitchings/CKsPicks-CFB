"""Live forecast rows keep the post-week current team states and say so in their refs.

Replay weeks are rated from the pregame states (``#pregame:<game_id>`` refs, output
unchanged); the live week keeps the current-team states the live features were built
from (``#current:<current_teams_raw_sha256>/<team>`` refs) and the verifier re-derives both.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.artifacts import dataframe_csv_bytes
from cks_picks_cfb.data.data_first_live_forecast_v1 import LIVE_FORECAST_COLUMNS
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.forecast.intended_update_bundle import replace_2026_ratings
from cks_picks_cfb.forecast.live import (
    DEVELOPMENT_SEASONS,
    FEATURES,
    apply_exported_bridge,
)
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_forecasts import (
    build,
    check_live_provenance,
)

LIVE_WEEK = 6
CUTOFF = "2026-10-04T08:00:00+00:00"
# game_id -> (week, home, away); game 31 kicked off before as_of and is omitted.
GAMES = {
    11: (5, "Alpha", "Beta"),
    12: (5, "Gamma", "Delta"),
    21: (6, "Beta", "Gamma"),
    22: (6, "Delta", "Alpha"),
    31: (6, "Epsilon", "Zeta"),
}
TEAMS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
BUNDLE = {
    "schema_version": "v5_inference_bundle_v1",
    "feature_order": list(FEATURES),
    "development_seasons": list(DEVELOPMENT_SEASONS),
    "targets": {
        target: {
            "feature_names": ["home_offense", "home_defense", "away_offense"],
            "coefficients": [1.0, -0.5, 0.25],
            "center": {"home_offense": 0.0, "home_defense": 0.0, "away_offense": 0.0},
            "scale": {"home_offense": 1.0, "home_defense": 1.0, "away_offense": 1.0},
            "intercept": 3.0 if target == "margin" else 50.0,
            "calibration_variance": 4.0,
            "head": "reference",
            "alpha": 10.0,
        }
        for target in ("margin", "total")
    },
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _schedule() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"season": 2026, "week": w, "game_id": g, "home_team": h, "away_team": a}
            for g, (w, h, a) in GAMES.items()
        ]
    )


def _pregame() -> pd.DataFrame:
    rows = []
    for game_id, (_, home, away) in GAMES.items():
        for index, team in enumerate((home, away)):
            rows.append(
                {
                    "season": 2026,
                    "game_id": game_id,
                    "team": team,
                    "offense_rating": game_id / 10 + index,
                    "defense_rating": -game_id / 20 - index,
                }
            )
    return pd.DataFrame(rows)


def _current() -> pd.DataFrame:
    # Two generations: post-Week-4 (week 5) and post-Week-5 (week 6, the live one).
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": 0,
                "cutoff_utc": cutoff,
                "team": team,
                "offense_rating": 30.0 + week + index,
                "defense_rating": 20.0 - week - index / 4,
            }
            for week, cutoff in ((5, "2026-09-27T08:00:00Z"), (6, CUTOFF))
            for index, team in enumerate(TEAMS)
        ]
    )


def _features(game_ids, ratings) -> pd.DataFrame:
    schedule = _schedule().set_index("game_id")
    rows = []
    for game_id in game_ids:
        rows.append(
            {
                "season": 2026,
                "week": int(schedule.loc[game_id, "week"]),
                "game_id": game_id,
                **ratings(game_id),
                "home_host": 1.0,
                "venue_unknown": 0.0,
                "offset_margin": 0.5,
                "offset_total": -1.0,
            }
        )
    return pd.DataFrame(rows)


def _live_ratings(game_id: int) -> dict[str, float]:
    states = _current()
    states = states[states.week.eq(LIVE_WEEK)].set_index("team")
    _, home, away = GAMES[game_id]
    return {
        "home_offense": float(states.loc[home, "offense_rating"]),
        "home_defense": float(states.loc[home, "defense_rating"]),
        "away_offense": float(states.loc[away, "offense_rating"]),
        "away_defense": float(states.loc[away, "defense_rating"]),
    }


def _stale_ratings(game_id: int) -> dict[str, float]:
    return {
        name: 99.0
        for name in ("home_offense", "home_defense", "away_offense", "away_defense")
    }


def _fixture(tmp_path: Path, *, live_ratings=_live_ratings, current_sha=None):
    """A local-cache build: Week 5 replay plus a display-only live Week 6."""
    lock = {
        "games": {
            "columns": ["game_id", "week"],
            "rows": [[g, w] for g, (w, _, _) in GAMES.items()],
        },
        "active_week": {"week": LIVE_WEEK},
        "research_2026_measurement_sha256": "m" * 64,
    }
    lock_path = tmp_path / "lock.json"
    lock_path.write_bytes(canonical_json(lock))

    bridge = tmp_path / "bridge"
    bridge.mkdir()
    bundle_raw = canonical_json(BUNDLE)
    (bridge / "bundle.json").write_bytes(bundle_raw)
    bridge_manifest = signed_payload(
        {
            "schema_version": "v5_intended_update_bridge_manifest_v1",
            "state": "frozen",
            "output_refs": {"inference_bundle": {"raw_sha256": _sha(bundle_raw)}},
        }
    )
    (bridge / "bridge-manifest.json").write_bytes(canonical_json(bridge_manifest))

    ratings = tmp_path / "ratings"
    ratings.mkdir()
    pregame_raw, current_raw = _parquet(_pregame()), _parquet(_current())
    (ratings / "pregame_teams.parquet").write_bytes(pregame_raw)
    (ratings / "current_teams.parquet").write_bytes(current_raw)
    prefix = "artifacts/ratings/run"
    rating_manifest = signed_payload(
        {
            "schema_version": "v5_intended_update_2026_rating_manifest_v1",
            "state": "frozen",
            "output_refs": {
                "pregame_teams": {
                    "uri": f"{prefix}/pregame_teams.parquet",
                    "raw_sha256": _sha(pregame_raw),
                },
                "current_teams": {
                    "uri": f"{prefix}/current_teams.parquet",
                    "raw_sha256": _sha(current_raw),
                },
            },
            "generation_hashes": {
                "current_post_w4": "a" * 64,
                "current_post_w5": "b" * 64,
            },
            "post_week_cutoffs": {"4": "2026-09-27T08:00:00Z", "5": CUTOFF},
        }
    )
    (ratings / "rating-manifest.json").write_bytes(canonical_json(rating_manifest))

    cache = tmp_path / "cache"
    cache.mkdir()
    _schedule().to_parquet(cache / "schedule.parquet")
    _features([11, 12], _stale_ratings).to_parquet(cache / "replay_features.parquet")
    live = _features([21, 22], live_ratings)
    live.attrs = {
        "omitted_kicked_off_game_ids": [31],
        "as_of": CUTOFF,
        "state_refs": {
            g: f"team_states/0#{GAMES[g][1]}|team_states/0#{GAMES[g][2]}"
            for g in (21, 22)
        },
        "current_teams_raw_sha256": current_sha or _sha(current_raw),
    }
    live.to_parquet(cache / "live_features.parquet")
    return {
        "lock": lock_path,
        "bridge": bridge,
        "ratings": ratings,
        "cache": cache,
        "rating_sha": _sha(canonical_json(rating_manifest)),
        "current_sha": _sha(current_raw),
        "rating_manifest": rating_manifest,
    }


def _build(tmp_path: Path, fixture) -> dict:
    return build(
        release_tag="fixture",
        code_sha="c" * 40,
        source_lock=fixture["lock"],
        output=tmp_path / "out",
        bridge=fixture["bridge"],
        ratings=fixture["ratings"],
        cache=fixture["cache"],
        display_only=True,
    )


def _predictions(tmp_path: Path, week: int) -> pd.DataFrame:
    return pd.read_csv(tmp_path / "out" / f"week={week}" / "predictions.csv")


def test_replay_week_output_is_unchanged_pregame_application(tmp_path):
    fixture = _fixture(tmp_path)
    manifests = _build(tmp_path, fixture)
    rating_sha = fixture["rating_sha"]
    replay = replace_2026_ratings(
        _features([11, 12], _stale_ratings), _schedule(), _pregame()
    )
    expected = apply_exported_bridge(
        BUNDLE,
        replay,
        run_id="2026w5-v5repair-fixture",
        model_ref=f"bridge:{_sha((fixture['bridge'] / 'bridge-manifest.json').read_bytes())}",
        state_refs={g: f"rating:{rating_sha}#pregame:{g}" for g in (11, 12)},
        source_ref=f"ratings:{rating_sha}|measurement:{'m' * 64}",
        timing_class="replay",
    ).predictions
    actual = (tmp_path / "out" / "week=5" / "predictions.csv").read_bytes()
    assert actual == dataframe_csv_bytes(expected.loc[:, list(LIVE_FORECAST_COLUMNS)])
    assert "current_teams" not in manifests["5"]


def test_mixed_run_labels_replay_rows_pregame_and_live_rows_current(tmp_path):
    fixture = _fixture(tmp_path)
    manifests = _build(tmp_path, fixture)
    rating_sha, current_sha = fixture["rating_sha"], fixture["current_sha"]
    replay = _predictions(tmp_path, 5)
    assert set(replay.state_ref) == {
        f"rating:{rating_sha}#pregame:{g}" for g in (11, 12)
    }
    live = _predictions(tmp_path, LIVE_WEEK)
    assert set(live.state_ref) == {
        f"rating:{rating_sha}#current:{current_sha}/Beta"
        f"|rating:{rating_sha}#current:{current_sha}/Gamma",
        f"rating:{rating_sha}#current:{current_sha}/Delta"
        f"|rating:{rating_sha}#current:{current_sha}/Alpha",
    }
    record = manifests[str(LIVE_WEEK)]["current_teams"]
    assert record["raw_sha256"] == current_sha
    assert record["uri"] == "artifacts/ratings/run/current_teams.parquet"
    assert record["generation"] == {
        "name": "current_post_w5",
        "post_week": 5,
        "cutoff_utc": CUTOFF,
        "generation_sha256": "b" * 64,
    }
    assert [row["game_id"] for row in record["ratings"]] == [21, 22]
    assert record["ratings"][0]["home_offense"] == _live_ratings(21)["home_offense"]


def test_live_ratings_that_differ_from_the_current_states_fail(tmp_path):
    def off_by_one(game_id):
        return {**_live_ratings(game_id), "away_defense": 0.0}

    with pytest.raises(ValueError, match="current-team states"):
        _build(tmp_path, _fixture(tmp_path, live_ratings=off_by_one))


def test_live_features_built_from_other_current_states_fail(tmp_path):
    with pytest.raises(ValueError, match="other current-team states"):
        _build(tmp_path, _fixture(tmp_path, current_sha="f" * 64))


def _verify(tmp_path: Path, mutate=None) -> None:
    fixture = _fixture(tmp_path)
    manifests = _build(tmp_path, fixture)
    rows = _predictions(tmp_path, LIVE_WEEK)
    if mutate:
        rows = mutate(rows, fixture)
    check_live_provenance(
        rows,
        manifests[str(LIVE_WEEK)]["current_teams"],
        _current(),
        fixture["rating_manifest"],
        _schedule(),
        rating_sha=fixture["rating_sha"],
        week=LIVE_WEEK,
    )


def test_verifier_accepts_live_rows_bound_to_the_current_states(tmp_path):
    _verify(tmp_path)


def test_verifier_rejects_a_live_ref_with_another_current_sha(tmp_path):
    def wrong_sha(rows, fixture):
        return rows.assign(
            state_ref=rows.state_ref.str.replace(fixture["current_sha"], "e" * 64)
        )

    with pytest.raises(ValueError, match="state refs"):
        _verify(tmp_path, wrong_sha)


def test_verifier_rejects_a_live_row_labeled_pregame(tmp_path):
    def pregame(rows, fixture):
        refs = rows.game_id.map(lambda g: f"rating:{fixture['rating_sha']}#pregame:{g}")
        return rows.assign(state_ref=refs)

    with pytest.raises(ValueError, match="state refs"):
        _verify(tmp_path, pregame)


def test_verifier_rejects_recorded_ratings_that_the_states_do_not_reproduce(tmp_path):
    fixture = _fixture(tmp_path)
    manifests = _build(tmp_path, fixture)
    record = json.loads(json.dumps(manifests[str(LIVE_WEEK)]["current_teams"]))
    record["ratings"][1]["home_defense"] += 0.5
    with pytest.raises(ValueError, match="ratings"):
        check_live_provenance(
            _predictions(tmp_path, LIVE_WEEK),
            record,
            _current(),
            fixture["rating_manifest"],
            _schedule(),
            rating_sha=fixture["rating_sha"],
            week=LIVE_WEEK,
        )
