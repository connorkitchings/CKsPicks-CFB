"""Exact identity and fail-closed evidence boundaries for the read-only audit."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from psycopg import IsolationLevel

from cks_picks_cfb.audit import adjusted_rows as audit
from cks_picks_cfb.data import matchup_data as md


def row(team="A", **changes):
    value = dict(
        season=2026,
        as_of_week=1,
        team=team,
        role="offense",
        measurement_id="epa_per_possession",
        raw_value=0.0,
        adjusted_value=0.0,
        opponent_adjustment=0.0,
        adjusted_rank=1,
        cohort_size=1,
        primary_exposure=10.0,
        games=1,
        adjustment_method=md.ADJUSTMENT_METHOD,
        as_of_cutoff="2026-09-01T00:00:00Z",
        rating_manifest_sha256="a" * 64,
        measurement_manifest_sha256="b" * 64,
    )
    return value | changes


def observation(**changes):
    return (
        dict(
            season=2026,
            week=0,
            game_id=1,
            kickoff_utc="2026-08-30T12:00:00Z",
            team="A",
            opponent="B",
            side="home",
            measurement_id="epa_per_possession",
            unit_role="offense",
            numerator=0.0,
            denominator=10.0,
            raw_value=0.0,
            usable_exposure=10.0,
            exposure_unit="possessions",
            coverage_status="observed",
            missing_reason=None,
            quality_flags="",
            timing_class="live",
        )
        | changes
    )


def prepared(**changes):
    return md.prepare_observations(
        pd.DataFrame([observation(**changes)]), {"A": "A", "B": "B"}
    )


def test_equal_counts_do_not_hide_different_keys():
    result = audit.compare(pd.DataFrame([row("A")]), pd.DataFrame([row("B")]))
    assert [r["team"] for r in result["only_left"]] == ["A"]
    assert [r["team"] for r in result["only_right"]] == ["B"]
    assert result["shared_keys"] == 0


@pytest.mark.parametrize("rows", [[row(), row()], [row(team=None)]])
def test_duplicate_or_null_keys_refused(rows):
    with pytest.raises(ValueError, match="canonical key"):
        audit.index_rows(pd.DataFrame(rows))


def test_alias_collision_and_ambiguous_mapping_refused():
    with pytest.raises(ValueError, match="collision"):
        audit.verified_names({"Alias", "A"}, {"A"}, {"A": "Alias"})
    with pytest.raises(md.MatchupDataError, match="ambiguous"):
        audit.verified_names({"Alias"}, {"A", "B"}, {"A": "Alias", "B": "Alias"})


def test_null_and_zero_differ_tolerance_is_relative_identifiers_exact():
    assert not audit.same("raw_value", None, 0.0)
    assert audit.same("raw_value", 100.0, 100.0 + 9e-8)
    assert not audit.same("raw_value", 100.0, 100.0 + 2e-7)
    assert not audit.same("games", 1, 1.0000000001)
    assert not audit.same("measurement_manifest_sha256", "01", "1")
    assert audit.same("raw_value", None, None)


def test_utc_timestamps_equal_offsets_naive_refused():
    assert audit.same(
        "as_of_cutoff", "2026-09-01T00:00:00Z", "2026-08-31T20:00:00-04:00"
    )
    with pytest.raises(ValueError, match="naive"):
        audit.same("as_of_cutoff", "2026-09-01", "2026-09-01T00:00:00Z")


def test_provenance_only_and_environment_value_drift_retained():
    result = audit.compare(
        pd.DataFrame([row()]),
        pd.DataFrame([row(rating_manifest_sha256="c" * 64, raw_value=1.0)]),
    )
    assert {(d["field"], d["kind"]) for d in result["differences"]} == {
        ("rating_manifest_sha256", "provenance"),
        ("raw_value", "value"),
    }
    assert (
        next(d for d in result["differences"] if d["field"] == "raw_value")["delta"]
        == 1.0
    )


def test_missing_ppa_omission_independently_reproduced():
    legacy = prepared()
    corrected = prepared(
        numerator=None,
        raw_value=None,
        coverage_status="missing",
        missing_reason="missing_ppa",
    )
    cutoff = {1: pd.Timestamp("2026-09-01T00:00:00Z")}

    def build(frame):
        return md.build_possession_adjusted(
            frame,
            season=2026,
            as_of_cutoffs=cutoff,
            fbs_names={"A", "B"},
            rating_manifest_sha256="a" * 64,
            measurement_manifest_sha256="b" * 64,
        )

    old = audit.index_rows(build(legacy))
    assert len(old) == 1 and build(corrected).empty
    explanation = audit.explain_extra(
        next(iter(old.values())), corrected, legacy, old, cutoff
    )
    assert explanation["classification"] == "supported_exclusion_recommendation"
    assert explanation["source_game_ids"] == [1]
    assert explanation["legacy_observations"][0]["raw_value"] == 0.0
    assert explanation["corrected_observations"][0]["raw_value"] is None
    unrelated = corrected.copy()
    unrelated["missing_reason"] = "unknown_provider_failure"
    assert (
        audit.explain_extra(next(iter(old.values())), unrelated, legacy, old, cutoff)[
            "classification"
        ]
        == "unresolved"
    )
    # Omission without independently reproduced stored values never authorizes recommendation.
    bad = row(raw_value=9.0)
    assert (
        audit.explain_extra(bad, corrected, legacy, old, cutoff)["classification"]
        == "unresolved"
    )


def test_week_and_availability_gates():
    p = prepared()
    availability = p.available_utc.iloc[0]
    assert len(audit.eligible(p, 1, availability)) == 1
    assert audit.eligible(p, 1, availability - pd.Timedelta(seconds=1)).empty
    assert audit.eligible(p, 0, availability).empty


def test_evidence_reservation_no_overwrite(tmp_path):
    target = tmp_path / "new"
    audit.fresh_output(target)
    (target / "proof").write_text("immutable")
    with pytest.raises(FileExistsError):
        audit.fresh_output(target)
    assert (target / "proof").read_text() == "immutable"


def test_refuse_root_data_output(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="root data"):
        audit.fresh_output(tmp_path / "data" / "output")
    assert not (tmp_path / "data").exists()


def test_readonly_repeatable_read_configuration():
    connection = SimpleNamespace()
    audit.configure_readonly(connection)
    assert connection.read_only is True
    assert connection.isolation_level == IsolationLevel.REPEATABLE_READ


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"schedule_completed": False}, "completed valid"),
        ({"outcome_valid": False}, "completed valid"),
        ({"week": 2}, "week/kickoff"),
        ({"kickoff_utc": "2026-08-31T12:00:00Z"}, "week/kickoff"),
    ],
)
def test_source_game_population_conflicts(changes, message):
    game = dict(
        season=2026,
        game_id=1,
        week=0,
        kickoff_utc="2026-08-30T12:00:00Z",
        home_team="A",
        away_team="B",
        schedule_completed=True,
        outcome_valid=True,
    )
    assert audit.validate_population(prepared(), pd.DataFrame([game]))
    with pytest.raises(ValueError, match=message):
        audit.validate_population(prepared(), pd.DataFrame([game | changes]))
