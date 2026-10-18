"""Chart tables of the season release payload, built from a real prepared run."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from cks_picks_cfb.charts.reconciliation import chart_problems
from cks_picks_cfb.season import projection_charts
from cks_picks_cfb.season import projection_common as pc
from cks_picks_cfb.season.projection_charts import (
    CHART_KEYS,
    ChartProjectionError,
    build_charts,
)
from cks_picks_cfb.season.projection_football import build_football
from tests.isolation_digests import EXCLUDED_PROVENANCE, digests
from tests.season_fixtures import build_season

MIGRATIONS = Path(__file__).resolve().parents[1] / "contracts/migrations"
#: The migration that created each chart table's release copy.
MIGRATION = {
    **dict.fromkeys(pc.CHART_TABLES, MIGRATIONS / "0026_team_chart_tables.sql"),
    "team_game_yardage": MIGRATIONS / "0027_team_game_yardage.sql",
}
GOLDEN = Path(__file__).with_name("isolation_golden.json")
# matchup_data_publications embeds np.polyfit floating-point residual which has a 1-bit
# platform difference between macOS ARM64 and Linux x86_64.
MACOS_ARM64_MATCHUP_DIGEST = (
    "db328e2241e270b7558aea808fb41d82efc3ff5c746ef9d7f02e40de3fda4638"
)


def migration_columns(table: str) -> set[str]:
    text = MIGRATION[table].read_text()
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
def charts(season):
    return build_charts(**season)


def test_returns_exactly_the_chart_tables(charts):
    assert tuple(charts) == CHART_KEYS
    assert charts["team_season_roster"] and charts["team_game_stats"]
    assert charts["team_game_yardage"]
    # Active week 2 is before the first adjusted window (Through Week 2).
    assert charts["team_adjusted_epa"] == []


@pytest.mark.parametrize("table", CHART_KEYS)
def test_row_columns_equal_the_migration_minus_server_columns(charts, table):
    expected = migration_columns(table)
    assert expected and all(set(row) == expected for row in charts[table])


def test_payload_is_canonical_and_sorted_by_natural_key(charts):
    from cks_picks_cfb.season.release import PROJECTION_KEYS

    pc.canonical_bytes(charts)
    for table in CHART_KEYS:
        keys = [tuple(r[k] for k in PROJECTION_KEYS[table]) for r in charts[table]]
        assert keys == sorted(keys) and len(set(keys)) == len(keys)


def test_roster_is_the_published_fbs_list_with_conferences(charts):
    teams = {row["team"]: row["conference"] for row in charts["team_season_roster"]}
    assert teams == dict.fromkeys(("App State", "Bravo", "Charlie", "Delta"), "Fixture")


def test_team_game_rows_cover_completed_games_with_mirrored_sites(charts):
    rows = charts["team_game_stats"]
    assert {r["game_id"] for r in rows} == {1, 2, 3, 4}  # weeks 0-1 only
    assert {r["week"] for r in rows} == {0, 1}
    by_game = {}
    for row in rows:
        by_game.setdefault(row["game_id"], []).append(row)
    assert all(len(pair) == 2 for pair in by_game.values())
    assert {r["site"] for r in rows} <= {"home", "away"}  # game 6 (neutral) is live


def test_tables_reconcile_with_the_real_team_season_stats(season, charts):
    stats = build_football(**season)["team_season_stats"]
    problems, observed = chart_problems(
        roster=charts["team_season_roster"],
        game_rows=charts["team_game_stats"],
        adjusted_rows=charts["team_adjusted_epa"],
        stats_rows=stats,
        season=2026,
        active_week=season["identity"]["active_week"],
    )
    assert problems == []
    assert observed["games"] == 4
    assert any(r["metric"] == "success_rate" for r in stats)


def test_two_builds_from_fresh_preparations_are_identical(charts, tmp_path):
    again = build_charts(**build_season(tmp_path))
    assert pc.canonical_bytes(again) == pc.canonical_bytes(charts)


def test_a_missing_teams_input_is_refused(season):
    absent = {**season, "inputs": dataclasses.replace(season["inputs"], teams=None)}
    with pytest.raises(ChartProjectionError, match="teams"):
        build_charts(**absent)
    bare = season["inputs"].teams.drop(columns="conference")
    with pytest.raises(ChartProjectionError, match="conference"):
        build_charts(
            **{**season, "inputs": dataclasses.replace(season["inputs"], teams=bare)}
        )


def test_neutral_site_games_are_marked_neutral(tmp_path):
    def edit(tables):
        tables["venue_games"]["neutral_site"] = tables["venue_games"].id.eq(3)

    charts = build_charts(**build_season(tmp_path, edit=edit))
    sites = {r["site"] for r in charts["team_game_stats"] if r["game_id"] == 3}
    assert sites == {"neutral"}


# --------------------------------------------------------------- isolation


def test_models_and_core_projections_are_unchanged_by_the_chart_module(
    tmp_path, monkeypatch
):
    """Ratings/forecast numbers and core_v1 payload bytes equal the pre-change golden.

    The golden was computed on the baseline commit (before any chart code) with the
    fixture's fixed identity. Identity/provenance columns are excluded from the
    model-frame digests: ``EXCLUDED_PROVENANCE``.
    """

    # The baseline inputs (teams without a conference column) must still prepare:
    # the chart builder is given conferences without touching the pinned revision.
    # The chart_yardage_recomputed prepare check rebuilds yardage from the same
    # inputs, so it is given the same conferences.
    real = projection_charts.build_charts
    real_yardage = projection_charts.build_yardage_rows

    def conferenced(inputs):
        teams = inputs.teams.assign(conference="Fixture")
        return dataclasses.replace(inputs, teams=teams)

    def with_conference(**arguments):
        return real(**{**arguments, "inputs": conferenced(arguments["inputs"])})

    monkeypatch.setattr(projection_charts, "build_charts", with_conference)
    monkeypatch.setattr(
        projection_charts,
        "build_yardage_rows",
        lambda inputs, active_week: real_yardage(conferenced(inputs), active_week),
    )

    def without_conference(tables):
        # The baseline fixture predates the conference column; removing it
        # reproduces the baseline pinned input (and so the baseline identity).
        tables["teams"] = tables["teams"].drop(columns="conference")

    season = build_season(tmp_path, edit=without_conference)
    computed = digests(season)
    golden = json.loads(GOLDEN.read_text())
    if computed.get("core_v1:matchup_data_publications") in (
        MACOS_ARM64_MATCHUP_DIGEST,
        golden.get("core_v1:matchup_data_publications"),
    ):
        computed["core_v1:matchup_data_publications"] = golden[
            "core_v1:matchup_data_publications"
        ]
    assert computed == golden
    assert {"run_id", "candidate_id"} <= EXCLUDED_PROVENANCE
