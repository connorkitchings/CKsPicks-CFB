"""Near-kickoff capture: separate entity and slot decisions (no network, fake clock).

The near-kickoff board is analysis-only evidence. It must never be selected by the
revision builders, and the slot logic must capture once per slot across a primary
and a backup run, never in weeks outside 12 to 15 and never on Sunday or Monday.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.lake import SourceCapture
from cks_picks_cfb.data.the_odds_api import (
    MARKET_QUOTES_ENTITY,
    NEAR_KICKOFF_ENTITY,
    TheOddsAPIAdapter,
)
from scripts.ops import near_kickoff_slot as slots
from scripts.pipeline import build_season_revision as builder
from scripts.pipeline import build_week_market_snapshot as snapshot
from tests.pg_harness import PgCluster, find_pg_bin

ROOT = Path(__file__).resolve().parents[1]


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# Eastern is UTC-5 from November 1, so 09:00 ET Saturday is 14:00Z.
SCHEDULE = pd.DataFrame(
    {
        "week": [11, 12, 12, 12, 12, 13],
        "start_date": [
            "2026-11-14T17:00:00Z",  # Week 11 Saturday noon ET
            "2026-11-20T01:00:00Z",  # Week 12 Thursday 8pm ET (Nov 19)
            "2026-11-21T17:00:00Z",  # Week 12 Saturday noon ET
            "2026-11-21T23:30:00Z",  # Week 12 Saturday evening
            "2026-11-23T01:00:00Z",  # Week 12 Sunday 8pm ET (Nov 22)
            "2026-11-28T17:00:00Z",  # Week 13 Saturday noon ET
        ],
    }
)
SAT_SLOT = "2026-w12-20261121"


def test_saturday_before_first_kickoff_captures():
    decision = slots.decide_slot(utc(2026, 11, 21, 14), SCHEDULE, set())
    assert (decision.action, decision.slot_id, decision.week) == (
        "capture",
        SAT_SLOT,
        12,
    )


def test_failed_primary_is_followed_by_successful_backup():
    succeeded_run_ids: list[str] = []

    def run_slot(now: datetime, *, succeeds: bool, label: str) -> str:
        decision = slots.decide_slot(
            now, SCHEDULE, slots.completed_slot_ids(succeeded_run_ids)
        )
        if decision.action == "capture" and succeeds:
            succeeded_run_ids.append(f"near-kickoff-{decision.slot_id}-{label}")
        return decision.action

    assert run_slot(utc(2026, 11, 21, 14), succeeds=False, label="1-1") == "capture"
    assert run_slot(utc(2026, 11, 21, 15, 15), succeeds=True, label="2-1") == "capture"
    assert run_slot(utc(2026, 11, 21, 15, 45), succeeds=True, label="3-1") == "skip"


def test_backup_skips_after_primary_success():
    completed = slots.completed_slot_ids([f"near-kickoff-{SAT_SLOT}-9-1"])
    decision = slots.decide_slot(utc(2026, 11, 21, 15, 15), SCHEDULE, completed)
    assert (decision.action, decision.reason) == ("skip", "slot already captured")


def test_outside_weeks_12_to_15_skips():
    # Week 11 Saturday has games but is outside the window.
    decision = slots.decide_slot(utc(2026, 11, 14, 14), SCHEDULE, set())
    assert decision.action == "skip"
    assert "outside weeks 12 to 15" in decision.reason
    late = pd.DataFrame({"week": [16], "start_date": ["2026-12-19T17:00:00Z"]})
    assert slots.decide_slot(utc(2026, 12, 19, 14), late, set()).action == "skip"


def test_day_without_kickoff_skips():
    decision = slots.decide_slot(utc(2026, 11, 24, 17), SCHEDULE, set())  # Tuesday
    assert (decision.action, decision.reason) == (
        "skip",
        "no kickoff on this Eastern day",
    )


def test_sunday_and_monday_never_get_a_slot_even_with_games():
    sunday_evening = slots.decide_slot(utc(2026, 11, 22, 18), SCHEDULE, set())
    monday = slots.decide_slot(utc(2026, 11, 23, 17), SCHEDULE, set())
    assert sunday_evening.action == monday.action == "skip"
    assert "weekly update" in sunday_evening.reason


def test_capture_after_earliest_kickoff_is_not_near_kickoff():
    decision = slots.decide_slot(utc(2026, 11, 21, 17, 5), SCHEDULE, set())
    assert decision.action == "skip"
    assert "not near-kickoff" in decision.reason


def test_midweek_captures_then_caps_per_week():
    schedule = pd.DataFrame(
        {
            "week": [13, 13, 13],
            "start_date": [
                "2026-11-25T01:00:00Z",  # Tuesday Nov 24 8pm ET
                "2026-11-26T01:00:00Z",  # Wednesday Nov 25
                "2026-11-27T01:00:00Z",  # Thursday Nov 26
            ],
        }
    )
    assert slots.decide_slot(utc(2026, 11, 24, 17), schedule, set()).action == "capture"
    done = {"2026-w13-20261124", "2026-w13-20261125"}
    capped = slots.decide_slot(utc(2026, 11, 26, 17), schedule, done)
    assert (capped.action, capped.reason) == ("skip", "midweek slot cap reached")


def test_naive_clock_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        slots.decide_slot(datetime(2026, 11, 21, 14), SCHEDULE, set())


def test_workflow_schedule_avoids_weekly_update_days_and_uses_own_concurrency():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/near-kickoff-capture.yml").read_text()
    )
    weekly = yaml.safe_load(
        (ROOT / ".github/workflows/weekly-season-update.yml").read_text()
    )
    triggers = workflow.get("on") or workflow[True]
    crons = [item["cron"] for item in triggers["schedule"]]
    assert len(crons) == 4  # a primary and a backup for each of two day groups
    for cron in crons:
        _, hour, _, _, days = cron.split()
        assert days in {"6", "2-5"}  # never Sunday (0) or Monday (1)
        assert 13 <= int(hour) <= 18  # before evening kickoffs, Eastern UTC-5
    assert workflow["concurrency"]["group"] != weekly["concurrency"]["group"]
    assert "CFB_NEAR_KICKOFF_CAPTURE_ENABLED" in workflow["jobs"]["capture"]["if"]


def test_adapter_accepts_near_kickoff_entity_and_keeps_weekly_default():
    board = [
        {
            "id": "e1",
            "home_team": "H",
            "away_team": "A",
            "commence_time": "2026-11-21T17:00:00Z",
            "bookmakers": [
                {
                    "key": "b",
                    "markets": [
                        {
                            "key": "totals",
                            "outcomes": [{"name": "Over", "point": 50, "price": -110}],
                        }
                    ],
                }
            ],
        }
    ]
    adapter = TheOddsAPIAdapter(
        api_key="test-key", http_get=lambda _: board, now=lambda: utc(2026, 11, 21, 14)
    )
    assert adapter.fetch_live(NEAR_KICKOFF_ENTITY, {}).entity == NEAR_KICKOFF_ENTITY
    assert adapter.fetch_live(MARKET_QUOTES_ENTITY, {}).entity == MARKET_QUOTES_ENTITY
    assert NEAR_KICKOFF_ENTITY != MARKET_QUOTES_ENTITY


def test_snapshot_market_captures_refuses_near_kickoff_capture(monkeypatch):
    capture = SourceCapture(
        capture_id="nk",
        provider="the_odds_api",
        entity=NEAR_KICKOFF_ENTITY,
        captured_at=utc(2026, 11, 21, 14),
        effective_at=None,
        request={},
        content_sha="a" * 64,
        object_sha="a" * 64,
        uri="lake/bronze/x/data.parquet",
        row_count=0,
        state="registered",
    )
    monkeypatch.setattr(snapshot, "source_capture_by_id", lambda *_: capture)
    with pytest.raises(ValueError, match="not a registered market capture"):
        snapshot.market_captures("conn", ["nk"])


PG_BIN = find_pg_bin()


@pytest.mark.skipif(PG_BIN is None, reason="PostgreSQL server binaries not found")
def test_revision_capture_selection_excludes_near_kickoff_capture(tmp_path):
    cluster = PgCluster(PG_BIN, tmp_path)
    try:
        cluster.start()
        with cluster.connect(autocommit=True) as conn:
            conn.execute("CREATE SCHEMA catalog")
            conn.execute(
                "CREATE TABLE catalog.source_captures (capture_id text PRIMARY KEY, "
                "provider text, entity text, captured_at timestamptz, "
                "request jsonb, state text)"
            )
            for capture_id, entity in (
                ("weekly", MARKET_QUOTES_ENTITY),
                ("near", NEAR_KICKOFF_ENTITY),
            ):
                conn.execute(
                    "INSERT INTO catalog.source_captures VALUES "
                    "(%s, 'the_odds_api', %s, %s, %s, 'registered')",
                    (capture_id, entity, "2026-11-21T14:00:00Z", json.dumps({})),
                )
        selected = builder.season_market_capture_ids(
            cluster.conninfo(), 2026, utc(2026, 12, 1)
        )
    finally:
        cluster.stop()
    assert selected == ["weekly"]


# --- matched-games check and unmatched summary (fake data, no network) ---

from scripts.data import fetch_odds_api_market_quotes as fetch  # noqa: E402

NOW = utc(2026, 11, 21, 14)  # Saturday 09:00 ET
DAY_SCHEDULE = pd.DataFrame(
    {
        "game_id": [1, 2, 3, 4, 5, 6],
        "home_team": [f"Home{i}" for i in range(6)],
        "away_team": [f"Away{i}" for i in range(6)],
        "start_date": [
            "2026-11-21T17:00:00Z",  # today, upcoming
            "2026-11-21T20:00:00Z",  # today, upcoming
            "2026-11-21T23:30:00Z",  # today, upcoming
            "2026-11-21T13:00:00Z",  # today, already started
            "2026-11-22T17:00:00Z",  # tomorrow
            "2026-11-28T17:00:00Z",  # next week
        ],
    }
)


def test_expected_slot_games_are_todays_unstarted_games():
    assert slots.expected_slot_game_ids(NOW, DAY_SCHEDULE) == {"1", "2", "3"}


def test_expected_slot_games_reject_naive_clock():
    with pytest.raises(ValueError):
        slots.expected_slot_game_ids(datetime(2026, 11, 21, 14), DAY_SCHEDULE)


@pytest.mark.parametrize(
    ("matched", "fails"),
    [
        ({"g1", "g2", "g3", "g4", "g5"}, False),
        ({"g1", "g2"}, True),  # 2/3 = 0.67 < 0.80
        (set(), True),
    ],
)
def test_match_ratio_failure_below_threshold(matched, fails):
    message = fetch.match_ratio_failure({"g1", "g2", "g3"}, matched, 0.8)
    assert (message is not None) is fails
    if fails:
        assert "of 3" in message and "0.80" in message


def test_match_ratio_exactly_at_threshold_passes():
    expected = {f"g{i}" for i in range(5)}
    assert fetch.match_ratio_failure(expected, {"g0", "g1", "g2", "g3"}, 0.8) is None


def test_match_ratio_with_no_expected_games_never_fails():
    assert fetch.match_ratio_failure(set(), set(), 0.8) is None


def test_match_ratio_override_zero_disables_check():
    assert fetch.match_ratio_failure({"g1", "g2"}, set(), 0) is None


def test_near_kickoff_unmatched_output_is_count_plus_five_samples():
    unmatched = [f"Away{i} @ Home{i}" for i in range(559)]
    text = fetch.unmatched_summary(unmatched, near_kickoff=True)
    assert "559 board events" in text
    assert text.count(" @ ") == 5
    assert len(text) < 400


def test_default_weekly_unmatched_output_is_unchanged():
    unmatched = ["B @ A", "D @ C", "B @ A"]
    assert fetch.unmatched_summary(unmatched, near_kickoff=False) == (
        "WARNING: 3 board events did not match the week schedule and were "
        "skipped: ['B @ A', 'D @ C']"
    )


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def _run_main(monkeypatch, argv, quoted_game_count):
    """Run main() with fakes; return (calls, exit message)."""
    from types import SimpleNamespace

    calls = {"finish": [], "registered": 0}
    records = [
        {
            "source_event_id": f"e{i}",
            "home_team": f"Home{i}",
            "away_team": f"Away{i}",
            "kickoff_utc": DAY_SCHEDULE.loc[i, "start_date"],
        }
        for i in range(quoted_game_count)
    ]
    response = SimpleNamespace(
        records=tuple(records),
        request={},
        captured_at=NOW,
        effective_at=NOW,
        provider_api_version=None,
        response_metadata={},
    )

    class FakeAdapter:
        def fetch_live(self, entity, params):
            calls["entity"] = entity
            return response

    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr(fetch, "load_dotenv", lambda: None)
    monkeypatch.setattr(fetch, "datetime", _FrozenDatetime)
    monkeypatch.setattr(fetch, "_week_schedule", lambda *a: DAY_SCHEDULE)
    monkeypatch.setattr(fetch, "TheOddsAPIAdapter", FakeAdapter)
    monkeypatch.setattr(fetch, "get_storage", lambda: object())
    monkeypatch.setattr(fetch, "begin_ingestion_run", lambda *a, **k: None)
    monkeypatch.setattr(
        fetch,
        "capture_provider_records",
        lambda *a, **k: SimpleNamespace(capture_id="cap1"),
    )
    monkeypatch.setattr(
        fetch,
        "register_source_capture",
        lambda *a, **k: calls.__setitem__("registered", calls["registered"] + 1),
    )
    monkeypatch.setattr(
        fetch, "finish_ingestion_run", lambda *a, **k: calls["finish"].append(k)
    )
    monkeypatch.setattr("sys.argv", ["fetch", "--year", "2026", "--week", "12", *argv])
    try:
        fetch.main()
    except SystemExit as exc:
        return calls, str(exc)
    return calls, None


def test_main_below_threshold_registers_capture_then_fails_run(monkeypatch):
    # Only g1 of the three expected games (g1..g3) is quoted: 0.33 < 0.80.
    calls, message = _run_main(monkeypatch, ["--near-kickoff", "--confirm"], 1)
    assert "Matched-games check failed: 1 of 3" in message
    assert calls["entity"] == NEAR_KICKOFF_ENTITY
    assert calls["registered"] == 1
    assert calls["finish"][0]["succeeded"] is False
    assert calls["finish"][0]["error_category"] == "MatchRatioBelowThreshold"


def test_main_at_or_above_threshold_succeeds(monkeypatch):
    # g1..g4 quoted covers all three expected games.
    calls, message = _run_main(monkeypatch, ["--near-kickoff", "--confirm"], 4)
    assert message is None
    assert calls["finish"][0]["succeeded"] is True


def test_main_override_zero_allows_thin_board(monkeypatch):
    calls, message = _run_main(
        monkeypatch, ["--near-kickoff", "--confirm", "--min-match-ratio", "0"], 1
    )
    assert message is None
    assert calls["finish"][0]["succeeded"] is True


def test_main_weekly_mode_never_applies_the_check(monkeypatch):
    calls, message = _run_main(monkeypatch, ["--confirm"], 1)
    assert message is None
    assert calls["entity"] == MARKET_QUOTES_ENTITY
    assert calls["finish"][0]["succeeded"] is True
