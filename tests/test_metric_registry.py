"""The metric registry preserves the existing team-stat contract and is self-consistent."""

from __future__ import annotations

from cks_picks_cfb.data import team_stats
from cks_picks_cfb.metrics import registry as reg


def test_registry_is_self_consistent_and_checksum_is_stable():
    assert reg.registry_problems() == []
    assert reg.registry_checksum() == reg.registry_checksum()
    assert len(reg.registry_checksum()) == 64


def test_rank_directions_equal_the_existing_website_contract():
    # ppa_per_play .. turnover_rate keep the (offense, defense) directions in team_stats.METRICS.
    for metric, directions in team_stats.METRICS.items():
        assert reg.BY_NAME[metric].rank_higher_is_better == directions, metric
    # Counts, totals and pace are not ranked.
    for metric in (
        "eligible_possessions",
        "plays_per_possession",
        "possessions_per_game",
        "points_scored",
    ):
        assert reg.BY_NAME[metric].rank_higher_is_better is None


def test_every_website_metric_is_in_the_registry_with_the_same_name():
    assert set(team_stats.METRICS) <= set(reg.BY_NAME)


def test_ppa_dependent_metrics_are_exactly_the_epa_family():
    ppa = {m.metric for m in reg.METRICS if m.requires_ppa}
    assert ppa == {
        "eligible_epa",
        "epa_per_possession",
        "ppa_per_play",
        "epa_per_play",
        "epa_pass",
        "epa_rush",
        "early_down_epa",
    }
    # Independent measurements (ppp, scoring) never depend on PPA.
    assert (
        not reg.BY_NAME["ppp"].requires_ppa
        and not reg.BY_NAME["non_offense_points"].requires_ppa
    )


def test_epa_per_play_is_an_alias_of_ppa_per_play():
    assert reg.BY_NAME["epa_per_play"].alias_of == "ppa_per_play"
    a, b = reg.BY_NAME["epa_per_play"], reg.BY_NAME["ppa_per_play"]
    assert (a.numerator, a.denominator, a.population_id) == (
        b.numerator,
        b.denominator,
        b.population_id,
    )


def test_changing_a_definition_changes_the_checksum(monkeypatch):
    before = reg.registry_checksum()
    altered = tuple(
        m
        if m.metric != "success_rate"
        else type(m)(**{**m.__dict__, "definition_version": "v2"})
        for m in reg.METRICS
    )
    monkeypatch.setattr(reg, "METRICS", altered)
    assert reg.registry_checksum() != before
