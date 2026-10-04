"""Gold dataset contracts: schema registration, null semantics, mirrors, ledger rules."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cks_picks_cfb.data.schema_contracts import (
    DatasetSchemaError,
    schema_for,
    validate_frame,
)
from cks_picks_cfb.metrics import contracts as gc
from cks_picks_cfb.metrics import registry as reg

T0 = pd.Timestamp("2026-09-05T19:00:00Z")
VERSIONS = json.dumps({"byplay": "v1"}, sort_keys=True)


def _metric_row(
    metric="ppp",
    team="A",
    opponent="B",
    role="offense",
    num=14.0,
    den=7.0,
    value=2.0,
    status="observed",
    reason=None,
    eligible=7,
    observed=7,
    flags="[]",
):
    d = reg.BY_NAME[metric]
    return {
        "season": 2026,
        "week": 1,
        "game_id": 1,
        "team": team,
        "opponent": opponent,
        "season_type": "regular",
        "role": role,
        "side": "home" if team == "A" else "away",
        "opponent_fbs": True,
        "kickoff_utc": T0,
        "metric": metric,
        "definition_version": d.definition_version,
        "population_id": d.population_id,
        "numerator": num,
        "denominator": den,
        "value": value,
        "eligible_count": eligible,
        "observed_count": observed,
        "coverage_unit": d.coverage_unit,
        "coverage_status": status,
        "missing_reason": reason,
        "quality_flags": flags,
        "timing_class": "live",
        "source_versions": VERSIONS,
    }


def _frame(*rows):
    return pd.DataFrame(list(rows))


def test_all_four_datasets_are_registered_with_their_keys():
    keys = {
        ("team_game_metrics", "team_game_metrics_v1"): (
            "season",
            "game_id",
            "team",
            "role",
            "metric",
        ),
        ("football_possessions", "football_possessions_v1"): (
            "season",
            "game_id",
            "drive_number",
            "offense",
        ),
        ("football_scoring_ledger", "football_scoring_ledger_v1"): (
            "season",
            "game_id",
            "source_event_id",
            "team",
        ),
        ("scoring_attribution_evidence", "scoring_attribution_evidence_v1"): (
            "evidence_id",
        ),
    }
    for (dataset, version), key in keys.items():
        assert schema_for(dataset, version).keys == key
    with pytest.raises(DatasetSchemaError):
        schema_for("team_game_metrics", "team_game_metrics_v9")


def test_a_valid_metric_frame_passes_schema_and_semantics():
    frame = _frame(_metric_row(), _metric_row(role="defense", team="B", opponent="A"))
    validate_frame(frame, schema_for("team_game_metrics", "team_game_metrics_v1"))
    assert gc.team_game_metrics_problems(frame) == []
    assert gc.defense_mirror_problems(frame) == []


def test_duplicate_metric_keys_fail_the_schema():
    frame = _frame(_metric_row(), _metric_row())
    with pytest.raises(DatasetSchemaError, match="duplicate keys"):
        validate_frame(frame, schema_for("team_game_metrics", "team_game_metrics_v1"))


def test_missing_requires_a_reason_and_a_null_value_never_a_zero():
    zero_filled = _frame(
        _metric_row(
            "eligible_epa", num=None, den=1.0, value=0.0, status="missing", reason=None
        )
    )
    problems = gc.team_game_metrics_problems(zero_filled)
    assert any("needs a missing_reason" in p for p in problems) and any(
        "null value" in p for p in problems
    )
    good = _frame(
        _metric_row(
            "eligible_epa",
            num=None,
            den=1.0,
            value=None,
            status="missing",
            reason="ppa_incomplete",
            eligible=40,
            observed=39,
        )
    )
    assert gc.team_game_metrics_problems(good) == []


def test_a_known_denominator_is_preserved_when_the_numerator_is_missing():
    row = _metric_row(
        "epa_pass",
        num=None,
        den=22.0,
        value=None,
        status="missing",
        reason="ppa_incomplete",
        eligible=22,
        observed=21,
    )
    assert gc.team_game_metrics_problems(_frame(row)) == []


def test_zero_denominator_ratio_is_undefined_null_not_zero():
    undefined = _metric_row(
        "epa_pass", num=0.0, den=0.0, value=None, eligible=0, observed=0
    )
    assert gc.team_game_metrics_problems(_frame(undefined)) == []
    zero = _metric_row("epa_pass", num=0.0, den=0.0, value=0.0, eligible=0, observed=0)
    assert any(
        "undefined ratio" in p for p in gc.team_game_metrics_problems(_frame(zero))
    )


def test_count_metrics_use_denominator_one_and_value_equals_numerator():
    ok = _metric_row(
        "eligible_possessions", num=12.0, den=1.0, value=12.0, eligible=12, observed=12
    )
    assert gc.team_game_metrics_problems(_frame(ok)) == []
    bad = _metric_row("eligible_possessions", num=12.0, den=2.0, value=6.0)
    assert any("denominator 1" in p for p in gc.team_game_metrics_problems(_frame(bad)))


def test_counts_must_be_nonnegative_integers_and_observed_cannot_exceed_eligible():
    bad = _metric_row(eligible=5, observed=6)
    assert any(
        "exceeds eligible_count" in p
        for p in gc.team_game_metrics_problems(_frame(bad))
    )
    assert any(
        "nonnegative integer" in p
        for p in gc.team_game_metrics_problems(
            _frame(_metric_row(eligible=-1, observed=0))
        )
    )


def test_value_must_equal_numerator_over_denominator_and_be_finite():
    assert any(
        "differs from numerator" in p
        for p in gc.team_game_metrics_problems(_frame(_metric_row(value=3.0)))
    )
    assert any(
        "not finite" in p
        for p in gc.team_game_metrics_problems(_frame(_metric_row(value=float("inf"))))
    )


def test_registry_membership_and_definition_are_enforced():
    unknown = _metric_row()
    unknown["metric"] = "made_up"
    assert any(
        "not in the registry" in p
        for p in gc.team_game_metrics_problems(_frame(unknown))
    )
    drift = _metric_row()
    drift["population_id"] = "Q"
    assert any(
        "differs from the registry" in p
        for p in gc.team_game_metrics_problems(_frame(drift))
    )


def test_flags_and_versions_must_be_canonical_json():
    assert any(
        "sorted JSON list" in p
        for p in gc.team_game_metrics_problems(_frame(_metric_row(flags='["b","a"]')))
    )
    bad = _metric_row()
    bad["source_versions"] = "not json"
    assert any("JSON map" in p for p in gc.team_game_metrics_problems(_frame(bad)))


def test_defense_rows_must_mirror_the_opponents_offense():
    off = _metric_row()
    drifted = _metric_row(
        role="defense", team="B", opponent="A", num=14.0, den=7.0, value=2.0, observed=6
    )
    assert any(
        "observed_count differs" in p
        for p in gc.defense_mirror_problems(_frame(off, drifted))
    )
    orphan = _metric_row(role="defense", team="C", opponent="Z")
    assert any(
        "no opponent offense row" in p
        for p in gc.defense_mirror_problems(_frame(off, orphan))
    )


def _possession(drive=1, offense="A", **over):
    row = {
        "season": 2026,
        "week": 1,
        "game_id": 1,
        "drive_number": drive,
        "possession_id": gc.possession_id_for(2026, 1, drive, offense),
        "offense": offense,
        "defense": "B",
        "period_class": "regulation",
        "eligible_play_count": 6,
        "ineligible_play_count": 0,
        "mixed_eligibility": False,
        "possession_eligible": True,
        "scoring_opportunity": True,
        "start_yards_to_goal": 75.0,
        "source_play_ids": "[]",
        "quality_reason": None,
        "timing_class": "live",
        "source_versions": VERSIONS,
    }
    return {**row, **over}


def test_possessions_schema_and_deterministic_ids():
    frame = _frame(_possession(1), _possession(2, "B"))
    validate_frame(frame, schema_for("football_possessions", "football_possessions_v1"))
    assert gc.possessions_problems(frame) == []
    assert gc.possession_id_for(2026, 1, 1, "A") == gc.possession_id_for(
        2026, 1, 1, "A"
    )
    assert gc.possession_id_for(2026, 1, 1, "A") != gc.possession_id_for(
        2026, 1, 2, "A"
    )
    tampered = _frame(_possession(1, possession_id="x"))
    assert any("deterministic" in p for p in gc.possessions_problems(tampered))
    ineligible_regulation = _frame(_possession(1, period_class="overtime"))
    assert any(
        "must be regulation" in p
        for p in gc.possessions_problems(ineligible_regulation)
    )


def _event(
    event_id="e1",
    team="A",
    increment=7.0,
    category="eligible_regulation_offense",
    **over,
):
    row = {
        "season": 2026,
        "game_id": 1,
        "source_event_id": event_id,
        "team": team,
        "drive_number": 1,
        "quarter": 1,
        "play_number": 3,
        "period_class": "regulation",
        "score_increment": increment,
        "scoring_category": category,
        "unit_category": "offense",
        "associated_possession_id": gc.possession_id_for(2026, 1, 1, team),
        "conversion_for_event_id": None,
        "raw_score_before": 0.0,
        "raw_score_after": 7.0,
        "envelope_before": 0.0,
        "envelope_after": 7.0,
        "certified_final": 7.0,
        "quality_reason": None,
        "rule_version": "baseline_v1",
        "allocation_group_id": "g1",
        "admission": "baseline_unchanged",
        "evidence_ids": "[]",
        "timing_class": "live",
        "source_versions": VERSIONS,
    }
    return {**row, **over}


def test_ledger_unresolved_markers_have_null_increments_not_zero():
    marker = _event(
        "m1",
        increment=None,
        category="unresolved",
        associated_possession_id=None,
        unit_category="unknown",
    )
    assert gc.scoring_ledger_problems(_frame(marker)) == []
    zero_marker = _event(
        "m1",
        increment=0.0,
        category="unresolved",
        associated_possession_id=None,
        unit_category="unknown",
    )
    assert any(
        "null score_increment" in p
        for p in gc.scoring_ledger_problems(_frame(zero_marker))
    )
    resolved_null = _event("e2", increment=None)
    assert any(
        "nonnegative integer" in p
        for p in gc.scoring_ledger_problems(_frame(resolved_null))
    )


def test_ledger_resolved_increments_are_integral_and_within_the_limit():
    assert any(
        "eight-point limit" in p
        for p in gc.scoring_ledger_problems(_frame(_event(increment=9.0)))
    )
    assert any(
        "nonnegative integer" in p
        for p in gc.scoring_ledger_problems(_frame(_event(increment=2.5)))
    )
    assert any(
        "nonnegative integer" in p
        for p in gc.scoring_ledger_problems(_frame(_event(increment=-1.0)))
    )


def test_ledger_references_resolve_within_the_game_and_team():
    td, pat = (
        _event("td", increment=6.0),
        _event("pat", increment=1.0, conversion_for_event_id="td"),
    )
    poss = _frame(_possession(1, "A"))
    assert gc.scoring_ledger_problems(_frame(td, pat), poss) == []
    dangling = _event("pat", increment=1.0, conversion_for_event_id="missing")
    assert any(
        "conversion_for_event_id" in p
        for p in gc.scoring_ledger_problems(_frame(dangling))
    )
    other_team = _event("pat", increment=1.0, team="B", conversion_for_event_id="td")
    assert any(
        "conversion_for_event_id" in p
        for p in gc.scoring_ledger_problems(_frame(td, other_team))
    )
    no_possession = _event("e9", associated_possession_id="nope")
    assert any(
        "resolve to a possession" in p
        for p in gc.scoring_ledger_problems(_frame(no_possession), poss)
    )


def test_ledger_admission_needs_evidence_and_envelope_stays_under_the_final():
    assert any(
        "needs evidence_ids" in p
        for p in gc.scoring_ledger_problems(_frame(_event(admission="corroborated")))
    )
    ok = _event(admission="corroborated", evidence_ids='["ev1"]')
    assert gc.scoring_ledger_problems(_frame(ok)) == []
    assert any(
        "exceeds the certified final" in p
        for p in gc.scoring_ledger_problems(_frame(_event(envelope_after=9.0)))
    )
    assert any(
        "not a sorted" in p or "sorted JSON list" in p
        for p in gc.scoring_ledger_problems(_frame(_event(evidence_ids='["b","a"]')))
    )


def test_ledger_and_evidence_schemas_validate_frames():
    frame = _frame(_event("a"), _event("b", team="B"))
    validate_frame(
        frame, schema_for("football_scoring_ledger", "football_scoring_ledger_v1")
    )
    evidence = _frame(
        {
            "evidence_id": "ev1",
            "allocation_group_id": "g1",
            "season": 2026,
            "game_id": 1,
            "team": "A",
            "quarter": 1,
            "points": 7,
            "source_event_id": "e1",
            "possession_id": None,
            "conversion_for_event_id": None,
            "unit_category": "offense",
            "source_kind": "cfbd_drives",
            "source_uri": "raw/cfbd/drives/x.json",
            "source_sha256": "a" * 64,
            "source_locator": "drive 3",
            "terms_uri": "https://example.test/terms",
            "rights_basis": "api key terms",
            "verdict": "supports",
            "reason": "drive points equal",
            "verifier_version": "v1",
            "captured_at": T0,
        }
    )
    validate_frame(
        evidence,
        schema_for("scoring_attribution_evidence", "scoring_attribution_evidence_v1"),
    )
    assert gc.evidence_problems(evidence) == []
    bad = evidence.assign(source_sha256="xyz", source_locator="")
    problems = gc.evidence_problems(bad)
    assert any("SHA-256" in p for p in problems) and any(
        "locator" in p for p in problems
    )


def test_require_raises_with_a_summary():
    with pytest.raises(gc.GoldContractError, match="2 problem"):
        gc.require(["a", "b"], "label")
    gc.require([], "label")
