"""Résumé projection from a real prepared season: period coverage, names, prepare checks."""

from __future__ import annotations

import copy
import dataclasses
import json

import pytest

from cks_picks_cfb.season import projection_football, projection_resume
from cks_picks_cfb.season import verification as v
from cks_picks_cfb.season.projection import build_projections
from cks_picks_cfb.season.projection_charts import CHART_KEYS
from cks_picks_cfb.season.projection_common import PROJECTION_ORDER
from cks_picks_cfb.season.projection_serving import SERVING_KEYS
from cks_picks_cfb.season.release import PROJECTION_KEYS
from tests.season_fixtures import build_season

#: Canonical names of the fixture's four FBS teams ("App State" is a provider name).
CANONICAL = {"Appalachian State", "Bravo", "Charlie", "Delta"}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """The season, its manifest context and the payload built from them."""
    output = tmp_path_factory.mktemp("resume")
    season = build_season(output)
    manifest = json.loads(next(output.rglob("run-manifest.json")).read_bytes())
    context = {"identity": manifest["identity"], "output_refs": manifest["output_refs"]}
    payload = build_projections(
        season["frames"], season["inputs"], season["revision"], context
    )
    return {**season, "context": context}, payload


def _served_periods(payload) -> set[str]:
    """Every served period id, derived from the served v5 rating snapshots."""
    periods = set()
    for snap in payload["v5_rating_snapshots"]:
        if snap["snapshot_class"] == "pregame" and snap["snapshot_id"].endswith(
            ":preseason"
        ):
            periods.add("preseason")
        elif snap["snapshot_class"] == "current":
            periods.add(
                projection_resume.source_qualified_period_id(
                    snap["source_manifest_sha256"], snap["cutoff_utc"]
                )
            )
    return periods


def test_payload_tables_are_exactly_the_registered_set(built):
    _, payload = built
    assert set(payload) == {"prediction_runs", *PROJECTION_ORDER}
    assert list(PROJECTION_KEYS) == list(PROJECTION_ORDER)


def test_every_builder_key_is_registered():
    built_keys = {
        *SERVING_KEYS,
        *projection_football.FOOTBALL_KEYS,
        *CHART_KEYS,
        "team_resume",
    }
    assert built_keys - {"prediction_runs"} == set(PROJECTION_ORDER)


def test_a_builder_returning_an_extra_table_fails_loudly(built, monkeypatch):
    season, _ = built
    real = projection_football.build_football

    def with_extra(**kwargs):
        return {**real(**kwargs), "unregistered": []}

    monkeypatch.setattr(projection_football, "build_football", with_extra)
    with pytest.raises(ValueError, match="returned tables"):
        build_projections(
            season["frames"], season["inputs"], season["revision"], season["context"]
        )


def test_every_served_period_has_resume_rows(built):
    _, payload = built
    served = _served_periods(payload)
    assert "preseason" in served, "the release serves a preseason period"
    assert len(served) == 3  # preseason plus post-weeks 0 and 1
    by_period: dict[str, set[str]] = {}
    for row in payload["team_resume"]:
        by_period.setdefault(row["period_id"], set()).add(row["team"])
    assert set(by_period) == served
    assert all(teams == CANONICAL for teams in by_period.values())


def test_period_ids_are_source_qualified_in_web_format(built):
    season, payload = built
    current = [row for row in payload["team_resume"] if row["period_id"] != "preseason"]
    assert current
    assert all(
        row["period_id"].startswith(f"{season['ratings_id']}@") for row in current
    )
    assert all(row["period_id"].endswith("Z") for row in current)


def test_period_id_format_matches_the_web_helper():
    sha = "a" * 64
    assert (
        projection_resume.source_qualified_period_id(
            sha, "2026-09-12T10:00:00.000000+00:00"
        )
        == f"{sha}@2026-09-12T10:00:00.000Z"
    )
    assert (
        projection_resume.source_qualified_period_id(
            sha, "2026-09-12T10:00:00.123456+00:00"
        )
        == f"{sha}@2026-09-12T10:00:00.123Z"
    )


def test_naive_cutoff_is_refused():
    with pytest.raises(ValueError):
        projection_resume.source_qualified_period_id("a" * 64, "2026-09-12T10:00:00")


def test_preseason_rows_have_no_post_week_or_sor(built):
    _, payload = built
    preseason = [
        row for row in payload["team_resume"] if row["period_id"] == "preseason"
    ]
    assert len(preseason) == 4
    assert all(row["post_week"] is None and row["sor"] is None for row in preseason)
    assert all(row["scheduled_games"] > 0 for row in preseason)


def test_prepare_checks_pass_on_the_built_payload(built):
    season, payload = built
    frames, inputs, ratings_id = (
        season["frames"],
        season["inputs"],
        season["ratings_id"],
    )
    assert v._resume_bridge_pinned(inputs)[0] == []
    assert v._resume_rated_teams(frames, inputs, ratings_id, payload)[0] == []
    assert v._resume_completed_parity(frames, inputs, ratings_id, payload)[0] == []
    assert v._resume_record_recount(frames, inputs, payload)[0] == []


def test_record_recount_fails_on_a_wrong_win_count(built):
    season, payload = built
    bad = copy.deepcopy(payload)
    row = next(
        r
        for r in bad["team_resume"]
        if r["period_id"] != "preseason"
        and r["team"] == "Bravo"
        and r["completed_games"] == 2
    )
    assert (row["wins"], row["losses"]) == (1, 1)
    row["wins"], row["losses"] = 2, 0
    problems, _ = v._resume_record_recount(season["frames"], season["inputs"], bad)
    assert len(problems) == 1 and "Bravo" in problems[0]


def test_rated_teams_fails_on_a_missing_row(built):
    season, payload = built
    bad = copy.deepcopy(payload)
    bad["team_resume"] = [
        r
        for r in bad["team_resume"]
        if not (r["period_id"] == "preseason" and r["team"] == "Bravo")
    ]
    problems, _ = v._resume_rated_teams(
        season["frames"], season["inputs"], season["ratings_id"], bad
    )
    assert problems == ["rated FBS team Bravo has no team_resume row in preseason"]


def test_completed_parity_fails_on_a_score_that_differs_from_finals(built):
    season, payload = built
    bad = copy.deepcopy(payload)
    bad["game_results"][0]["home_points"] += 1
    problems, _ = v._resume_completed_parity(
        season["frames"], season["inputs"], season["ratings_id"], bad
    )
    assert any("score differs from finals" in problem for problem in problems)


def test_completed_parity_fails_when_a_completed_game_is_missing(built):
    season, payload = built
    bad = copy.deepcopy(payload)
    bad["game_results"] = bad["game_results"][1:]
    problems, _ = v._resume_completed_parity(
        season["frames"], season["inputs"], season["ratings_id"], bad
    )
    assert any("completed games differ" in problem for problem in problems)


def test_bridge_check_fails_on_unpinned_bytes(built):
    season, _ = built
    wrong = dataclasses.replace(season["inputs"], bridge_sha256="0" * 64)
    problems, _ = v._resume_bridge_pinned(wrong)
    assert problems == ["bridge bytes differ from the pinned B2 bundle"]


def test_build_resume_refuses_unverified_bridge_bytes(built):
    season, _ = built
    unverified = dataclasses.replace(season["inputs"], bridge_sha256=None)
    with pytest.raises(ValueError, match="pinned B2 bundle"):
        projection_resume.build_resume(
            frames=season["frames"], inputs=unverified, ratings_id=season["ratings_id"]
        )
