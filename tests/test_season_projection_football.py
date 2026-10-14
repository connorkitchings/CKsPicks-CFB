"""Football-data tables of the season release payload, from a real prepared run."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from cks_picks_cfb.season import projection_common as pc
from cks_picks_cfb.season.projection_football import (
    FOOTBALL_KEYS,
    FootballProjectionError,
    build_football,
    football_report,
    run_id_of,
)
from cks_picks_cfb.season.verification import VerificationError
from tests.season_fixtures import build_season

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "contracts/migrations/0025_season_releases.sql"
)


def migration_columns(table: str) -> set[str]:
    text = MIGRATION.read_text()
    block = re.search(
        rf"CREATE TABLE IF NOT EXISTS season_release_{table} \((.*?)\n\);",
        text,
        re.S,
    ).group(1)
    names = set(re.findall(r"^\s+([a-z_0-9]+)\s+[A-Z]", block, re.M))
    return names - {"PRIMARY"} - pc.SERVER_COLUMNS


@pytest.fixture(scope="module")
def season(tmp_path_factory):
    return build_season(tmp_path_factory.mktemp("season"))


@pytest.fixture(scope="module")
def payload(season):
    return build_football(**season)


def test_returns_exactly_the_football_tables(payload):
    assert tuple(payload) == FOOTBALL_KEYS
    assert all(payload[key] for key in FOOTBALL_KEYS)


@pytest.mark.parametrize("table", FOOTBALL_KEYS)
def test_row_columns_equal_the_migration_minus_server_columns(payload, table):
    expected = migration_columns(table)
    assert expected and "environment" not in expected
    assert all(set(row) == expected for row in payload[table])


def test_payload_is_canonical_finite_and_has_no_environment(payload):
    pc.canonical_bytes(payload)  # allow_nan=False: no NaN/inf anywhere
    assert all("environment" not in row for rows in payload.values() for row in rows)


def test_rows_are_sorted_by_natural_key(payload):
    from cks_picks_cfb.season.release import PROJECTION_KEYS

    for table in FOOTBALL_KEYS:
        keys = [tuple(r[k] for k in PROJECTION_KEYS[table]) for r in payload[table]]
        assert keys == sorted(keys) and len(set(keys)) == len(keys)


def test_two_builds_from_fresh_preparations_are_identical(payload, tmp_path):
    again = build_football(**build_season(tmp_path))
    assert pc.canonical_bytes(again) == pc.canonical_bytes(payload)


def test_rating_and_measurement_lineage_is_one_identity(season, payload):
    ratings_id, measurement_id = season["ratings_id"], season["measurement_id"]
    (publication,) = payload["matchup_data_publications"]
    assert publication["rating_manifest_sha256"] == ratings_id
    assert publication["measurement_manifest_sha256"] == measurement_id
    assert {r["source_manifest_sha256"] for r in payload["v5_rating_snapshots"]} == {
        ratings_id
    }
    assert {r["source_manifest_sha256"] for r in payload["team_rating_components"]} == {
        ratings_id
    }
    for table in ("team_possession_stats", "team_possession_adjusted"):
        assert {r["rating_manifest_sha256"] for r in payload[table]} == {ratings_id}
        assert {r["measurement_manifest_sha256"] for r in payload[table]} == {
            measurement_id
        }
    assert {
        r["measurement_manifest_sha256"] for r in payload["team_game_measurements"]
    } == {measurement_id}


def test_bare_prepare_identity_derives_the_run_id(season):
    identity = dict(season["identity"])
    run_id = identity.pop("run_id")
    assert run_id_of(identity) == run_id


def test_publication_receipt(season, payload):
    run_id = season["identity"]["run_id"]
    (publication,) = payload["matchup_data_publications"]
    assert publication["rating_manifest_uri"] == f"season-run:{run_id}#ratings"
    assert (
        publication["measurement_manifest_uri"] == f"season-run:{run_id}#measurements"
    )
    assert publication["row_counts"] == {
        table: len(payload[table])
        for table in (
            "team_game_measurements",
            "team_possession_stats",
            "team_possession_adjusted",
            "team_rating_components",
        )
    }
    assert publication["code_sha"] == season["identity"]["code_sha"]
    assert publication["as_of_weeks"] == [0, 1, 2]
    assert set(publication["rating_scale"]) == {"offense", "defense"}
    assert publication["publication_id"].startswith(
        f"2026:intended_update:{season['ratings_id'][:12]}:"
    )
    assert publication["published_at"] == "2026-09-13T12:00:00.000000+00:00"


def test_snapshot_ids_counts_and_null_game_ids(season, payload):
    run = season["identity"]["run_id"]
    assert set(season["frames"]["ratings"].game_id) == {0}  # prepared sentinel
    snapshots = {r["snapshot_id"]: r for r in payload["v5_rating_snapshots"]}
    teams = ("Appalachian State", "Bravo", "Charlie", "Delta")
    expected = (
        {f"{run}:pregame:{t}:preseason" for t in teams}
        | {f"{run}:pregame:{t}:week-{w}" for t in teams for w in (1, 2)}
        | {f"{run}:current:post-week-{n}:{t}" for t in teams for n in (0, 1)}
    )
    assert set(snapshots) == expected
    assert all(r["game_id"] is None for r in snapshots.values())
    assert all(r["source_run_id"] == run for r in snapshots.values())
    preseason = snapshots[f"{run}:pregame:Delta:preseason"]
    assert preseason["week"] == 0 and preseason["snapshot_class"] == "pregame"
    assert preseason["cutoff_utc"] == "2026-09-05T10:00:00.000000+00:00"
    assert preseason["fallback_reason"] == "no_prior_season"
    week = snapshots[f"{run}:pregame:Bravo:week-2"]
    assert week["week"] == 2 and week["fallback_reason"] is None
    current = snapshots[f"{run}:current:post-week-1:Bravo"]
    assert current["week"] == 1 and current["snapshot_class"] == "current"


def test_every_component_reconciles_to_its_snapshot(payload):
    snapshots = {r["snapshot_id"]: r for r in payload["v5_rating_snapshots"]}
    components = payload["team_rating_components"]
    assert len(components) == 2 * len(snapshots)
    for c in components:
        snap = snapshots[c["v5_snapshot_id"]]
        role = c["unit_role"]
        assert c["rating_team"] == snap["team"]
        assert c["rating_mean"] == pytest.approx(snap[f"{role}_rating"], abs=1e-12)
        assert c["rating_variance"] == pytest.approx(
            snap[f"{role}_variance"], abs=1e-12
        )
        assert c["cutoff_utc"] == snap["cutoff_utc"]
    renamed = {c["team"] for c in components if c["rating_team"] == "Appalachian State"}
    assert renamed == {"App State"}


def stat(rows, **match):
    (row,) = [r for r in rows if all(r[k] == v for k, v in match.items())]
    return row


def test_possession_stats_hand_computed(payload):
    # App State offense, games 1 and 3: 10 points on 2 possessions each; eligible
    # EPA 4.0 (game 1) and 5.0 (game 3) from the fixture plays.
    rows = payload["team_possession_stats"]
    ppp = stat(rows, as_of_week=2, team="App State", role="offense", metric="ppp")
    assert (ppp["numerator"], ppp["denominator"], ppp["value"]) == (20.0, 4.0, 5.0)
    assert ppp["games"] == 2 and ppp["games_excluded"] == 0
    assert ppp["as_of_cutoff"] == "2026-09-13T12:00:00.000000+00:00"
    epa = stat(
        rows,
        as_of_week=2,
        team="App State",
        role="offense",
        metric="epa_per_possession",
    )
    assert epa["value"] == pytest.approx(9.0 / 4.0)
    week1 = stat(rows, as_of_week=1, team="Bravo", role="defense", metric="ppp")
    assert (week1["value"], week1["games"]) == (5.0, 1)


def test_team_season_stats_hand_computed(payload):
    # Week 0, App State offense in game 1: five eligible scrimmage plays (the
    # field goal is special teams) with success 1,1,1,0,1, yards 6,26,11,4,13
    # and PPA 0.3,1.2,1.6,0.0,0.9.
    rows = payload["team_season_stats"]
    match = {"as_of_week": 1, "team": "App State", "role": "offense"}
    success = stat(rows, metric="success_rate", **match)
    assert (success["value"], success["n"], success["games"]) == (0.8, 5, 1)
    assert stat(rows, metric="ppa_per_play", **match)["value"] == pytest.approx(0.8)
    assert stat(rows, metric="explosive_rate", **match)["value"] == pytest.approx(0.2)
    assert stat(rows, metric="scoring_opp_rate", **match)["value"] == 1.0
    assert {r["as_of_week"] for r in rows} == {1, 2}
    assert {r["team"] for r in rows} == {"App State", "Bravo", "Charlie", "Delta"}
    versions = rows[0]["source_versions"]
    assert set(versions) == {"byplay", "drives", "games", "game_outcomes", "teams"}


def test_game_venues_cover_the_full_schedule(payload):
    venues = payload["game_venues"]
    assert [r["game_id"] for r in venues] == list(range(1, 9))
    assert all(r["source"] == "cfbd" and r["city"] for r in venues)
    assert venues[5]["neutral_site"] is True


def drop_city(game_id):
    def edit(tables):
        venues = tables["venues"]
        venues.loc[venues.id.eq(100 + game_id), "city"] = None

    return edit


def with_inputs(season, **changes):
    """The prepared season with edited builder inputs (preparation unchanged)."""
    return {**season, "inputs": dataclasses.replace(season["inputs"], **changes)}


def test_active_week_game_without_city_blocks(season, tmp_path):
    venues = season["inputs"].venues.copy()
    venues.loc[venues.id.eq(105), "city"] = None
    with pytest.raises(ValueError, match=r"venue city missing.*\[5\]"):
        build_football(**with_inputs(season, venues=venues))
    # The real preparation runs the builder and refuses the run.
    with pytest.raises(ValueError, match=r"venue city missing.*\[5\]"):
        build_season(tmp_path, drop_city(5))


def test_later_week_game_without_city_is_reported_not_blocking(tmp_path):
    season = build_season(tmp_path, drop_city(7))
    venues = {r["game_id"]: r for r in build_football(**season)["game_venues"]}
    assert venues[7]["city"] is None and venues[8]["city"] == "City 8"
    report = football_report(**season)["game_venues"]
    assert report["later_missing_city_game_ids"] == [7]
    assert report["required_games"] == 6


def test_absent_venue_inputs_yield_no_venue_rows(season, tmp_path):
    edited = with_inputs(season, venue_games=None, venues=None)
    payload = build_football(**edited)
    assert payload["game_venues"] == []
    assert payload["v5_rating_snapshots"]
    assert football_report(**edited)["game_venues"]["state"] == "missing_inputs"

    def edit(tables):
        del tables["venue_games"], tables["venues"]

    # A release must cover every game through the active week with a venue.
    with pytest.raises(VerificationError, match="venues_cover"):
        build_season(tmp_path, edit)


def test_missing_teams_input_is_a_clear_error(season, tmp_path):
    with pytest.raises(FootballProjectionError, match="pinned 'teams' input"):
        build_football(**with_inputs(season, teams=None))

    def edit(tables):
        del tables["teams"]

    with pytest.raises(FootballProjectionError, match="pinned 'teams' input"):
        build_season(tmp_path, edit)
