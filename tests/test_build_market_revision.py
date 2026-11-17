"""Market-only revision builder: what it may change, what it must refuse.

Fakes stand in for storage, the database and the quote builder; no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.pipeline import build_market_revision as builder

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "conf/season/2026/revision_manifest_w8_v2.json"
)
CUTOFF = "2026-10-20T14:39:00Z"
QUOTES_SOURCE_URI = json.loads(SOURCE.read_text())["inputs"]["market_quotes"]["uri"]
LAST_CAPTURE = datetime(2026, 10, 20, 14, 33, 30, tzinfo=timezone.utc)
QUOTES = {
    "uri": "lake/silver/dataset=market_quotes/version=new/data.parquet",
    "sha256": "b" * 64,
}


def source_manifest() -> dict:
    return json.loads(SOURCE.read_text())


def derive(old: dict) -> dict:
    return builder.derive_manifest(
        old,
        revision_id="season-2026-w8-preview-r3",
        quotes_input=QUOTES,
        captured_at="2026-10-20T14:33:30Z",
        target_week="8",
        cutoff=CUTOFF,
    )


def changed_paths(old: dict, new: dict, prefix: str = "") -> set[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        return {
            path
            for key in old.keys() | new.keys()
            for path in changed_paths(old.get(key), new.get(key), f"{prefix}/{key}")
        }
    return set() if old == new else {prefix}


def test_derive_changes_only_quotes_cutoff_and_revision_identity():
    old = source_manifest()
    new = derive(old)

    assert changed_paths(old, new) == {
        "/revision_id",
        "/captured_at",
        "/inputs/market_quotes/uri",
        "/inputs/market_quotes/sha256",
        "/pre_week_cutoffs/8",
    }
    assert new["inputs"]["market_quotes"] == QUOTES
    assert new["pre_week_cutoffs"]["8"] == CUTOFF
    # The source is untouched, so a failed build can never corrupt the certified manifest.
    assert old == source_manifest()


def test_derive_keeps_every_football_input_and_completed_week_cutoff():
    old = source_manifest()
    new = derive(old)

    football = lambda m: {k: v for k, v in m["inputs"].items() if k != "market_quotes"}  # noqa: E731
    assert football(new) == football(old)
    assert new["post_week_cutoffs"] == old["post_week_cutoffs"]
    assert (
        new["score_reconciliation_exceptions"] == old["score_reconciliation_exceptions"]
    )
    assert {k: v for k, v in new["pre_week_cutoffs"].items() if k != "8"} == {
        k: v for k, v in old["pre_week_cutoffs"].items() if k != "8"
    }


@pytest.fixture
def registered(monkeypatch) -> list:
    """Quotes versions the builder registered in the (fake) catalog."""
    calls: list = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr(builder, "get_storage", lambda environment: object())
    monkeypatch.setattr(builder, "season_market_capture_ids", lambda *a: ["c1"])
    monkeypatch.setattr(
        builder,
        "build_market_quotes",
        lambda *a, **k: (
            SimpleNamespace(uri=QUOTES["uri"], content_sha=QUOTES["sha256"]),
            {"manifest": True},
        ),
    )
    monkeypatch.setattr(
        builder, "register_dataset_version", lambda *args: calls.append(args)
    )
    return calls


def run_main(
    monkeypatch,
    target,
    *,
    captured_at=LAST_CAPTURE,
    week_games=56,
    source=SOURCE,
    target_week=8,
    cutoff=CUTOFF,
) -> int:
    schedule = pd.DataFrame(
        {"game_id": range(week_games), "season": 2026, "week": target_week}
    )
    monkeypatch.setattr(builder, "frame", lambda store, ref: schedule)
    monkeypatch.setattr(
        builder,
        "market_captures",
        lambda *a: [SimpleNamespace(captured_at=captured_at)],
    )
    return builder.main(
        [
            "--from-manifest", str(source),
            "--to-manifest", str(target),
            "--revision-id", "season-2026-w8-preview-r3",
            "--cutoff", cutoff,
            "--target-week", str(target_week),
        ]
    )  # fmt: skip


def test_main_writes_the_new_manifest_and_registers_the_quotes_version(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"

    assert run_main(monkeypatch, target) == 0

    assert len(registered) == 1
    written = json.loads(target.read_text())
    assert written["revision_id"] == "season-2026-w8-preview-r3"
    assert written["captured_at"] == "2026-10-20T14:33:30Z"
    assert written["inputs"]["market_quotes"] == QUOTES


def test_main_refuses_to_overwrite_an_existing_manifest(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"
    target.write_text("certified\n")

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        run_main(monkeypatch, target)

    assert target.read_text() == "certified\n"
    assert registered == []


def test_main_refuses_a_capture_later_than_the_cutoff(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"
    late = datetime(2026, 10, 20, 14, 40, tzinfo=timezone.utc)

    with pytest.raises(SystemExit, match="later than --cutoff"):
        run_main(monkeypatch, target, captured_at=late)

    assert not target.exists()
    assert registered == []


def test_main_refuses_a_target_week_with_no_scheduled_games(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"

    with pytest.raises(SystemExit, match="Week 8 has no games"):
        run_main(monkeypatch, target, week_games=0)

    assert not target.exists()
    assert registered == []


def test_main_registers_nothing_when_the_manifest_is_invalid(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"

    def reject(_manifest):
        raise ValueError("invalid revision")

    monkeypatch.setattr(builder, "validate_revision", reject)

    with pytest.raises(ValueError, match="invalid revision"):
        run_main(monkeypatch, target)

    assert not target.exists()
    assert registered == []


def manifest_through(week: int) -> dict:
    """Synthetic manifest whose upcoming (highest) pre-week cutoff is ``week``."""
    old = source_manifest()
    old["pre_week_cutoffs"] = {
        str(w): f"2026-09-{w + 1:02d}T12:00:00Z" for w in range(week + 1)
    }
    return old


def refresh(old: dict, week: int, cutoff: str = "2026-10-25T20:52:00Z") -> dict:
    return builder.derive_manifest(
        old,
        revision_id=f"season-2026-w{week}-preview-r2",
        quotes_input=QUOTES,
        captured_at="2026-10-25T20:47:00Z",
        target_week=str(week),
        cutoff=cutoff,
    )


def test_week_nine_refresh_moves_only_week_nine_and_market_identity():
    old = manifest_through(9)
    new = refresh(old, 9)

    assert changed_paths(old, new) == {
        "/revision_id",
        "/captured_at",
        "/inputs/market_quotes/uri",
        "/inputs/market_quotes/sha256",
        "/pre_week_cutoffs/9",
    }
    assert new["pre_week_cutoffs"]["8"] == old["pre_week_cutoffs"]["8"]


@pytest.mark.parametrize("week", [8, 9])
def test_each_target_week_touches_only_its_own_cutoff(week):
    old = manifest_through(week)
    new = refresh(old, week)

    moved = {
        k
        for k in old["pre_week_cutoffs"]
        if old["pre_week_cutoffs"][k] != new["pre_week_cutoffs"][k]
    }
    assert moved == {str(week)}


def test_target_week_that_is_not_the_highest_is_refused():
    with pytest.raises(ValueError, match="8.*upcoming week 9"):
        refresh(manifest_through(9), 8)


def test_target_week_missing_from_the_source_is_refused():
    with pytest.raises(ValueError, match="Week 10 is not in"):
        refresh(manifest_through(9), 10)


def test_cutoff_earlier_than_the_source_cutoff_is_refused():
    old = manifest_through(9)
    old["pre_week_cutoffs"]["9"] = "2026-10-25T21:00:00Z"
    with pytest.raises(ValueError, match="earlier than the source"):
        refresh(old, 9)


def test_main_requires_target_week(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        builder.main(
            ["--from-manifest", str(SOURCE), "--to-manifest", str(tmp_path / "x.json"),
             "--revision-id", "r", "--cutoff", CUTOFF]
        )  # fmt: skip
    assert exit_info.value.code == 2


def test_main_names_both_weeks_when_target_is_not_upcoming(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "out.json"

    with pytest.raises(SystemExit, match="upcoming week 8"):
        run_main(monkeypatch, target, target_week=7)

    assert not target.exists()
    assert registered == []


# --- Monday kickoff-time refresh --------------------------------------------

SCHEDULE = {
    "uri": "lake/silver/dataset=games/version=fresh/data.parquet",
    "sha256": "c" * 64,
}


def derive_with_schedule(old: dict, schedule: dict | None = SCHEDULE) -> dict:
    return builder.derive_manifest(
        old,
        revision_id="season-2026-w8-preview-r3",
        quotes_input=QUOTES,
        captured_at="2026-10-20T14:33:30Z",
        target_week="8",
        cutoff=CUTOFF,
        schedule_input=schedule,
    )


def test_schedule_refresh_changes_only_the_schedule_and_venue_games_pair():
    old = source_manifest()

    new = derive_with_schedule(old)

    assert changed_paths(old, new) == {
        "/revision_id",
        "/captured_at",
        "/inputs/market_quotes/uri",
        "/inputs/market_quotes/sha256",
        "/pre_week_cutoffs/8",
        "/inputs/schedule/uri",
        "/inputs/schedule/sha256",
        "/inputs/venue_games/uri",
        "/inputs/venue_games/sha256",
    }
    assert new["inputs"]["schedule"] == new["inputs"]["venue_games"] == SCHEDULE


def test_schedule_refresh_is_refused_when_the_source_pins_differ():
    old = source_manifest()
    old["inputs"]["venue_games"] = dict(QUOTES)

    with pytest.raises(ValueError, match="schedule and venue_games pins differ"):
        derive_with_schedule(old)


def test_without_a_schedule_input_the_schedule_pins_stay_forbidden_to_change():
    old = source_manifest()

    new = derive_with_schedule(old, schedule=None)

    assert new["inputs"]["schedule"] == old["inputs"]["schedule"]
    assert new["inputs"]["venue_games"] == old["inputs"]["venue_games"]


def schedule_frame(**overrides) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "game_id": [1, 2, 3],
            "week": [7, 8, 8],
            "home_team": ["A", "C", "E"],
            "away_team": ["B", "D", "F"],
            "kickoff_utc": pd.to_datetime(
                ["2026-10-17T16:00Z", "2026-10-24T05:00Z", "2026-10-24T05:00Z"]
            ),
        }
    )
    return frame.assign(**overrides)


def test_new_kickoff_times_for_the_target_week_are_accepted():
    old = schedule_frame()
    new = schedule_frame(
        kickoff_utc=pd.to_datetime(
            ["2026-10-17T16:00Z", "2026-10-24T19:30Z", "2026-10-24T23:00Z"]
        )
    )

    builder.check_game_set_unchanged(old, new, target_week=8)


def test_an_added_cancelled_or_moved_game_fails_closed_with_the_game_list():
    old = schedule_frame()
    added = pd.concat(
        [old, schedule_frame().iloc[[0]].assign(game_id=9)], ignore_index=True
    )
    cancelled = old[old.game_id != 2]
    moved_week = old.assign(week=[7, 9, 8])
    moved_team = old.assign(home_team=["A", "C", "Z"])

    with pytest.raises(ValueError, match=r"added games \[9\]"):
        builder.check_game_set_unchanged(old, added, target_week=8)
    with pytest.raises(ValueError, match=r"cancelled games \[2\]"):
        builder.check_game_set_unchanged(old, cancelled, target_week=8)
    with pytest.raises(ValueError, match=r"moved games.*\[2\]"):
        builder.check_game_set_unchanged(old, moved_week, target_week=8)
    with pytest.raises(ValueError, match=r"moved games.*\[3\]"):
        builder.check_game_set_unchanged(old, moved_team, target_week=8)


def test_a_neutral_site_change_fails_closed_with_the_game_list():
    old = schedule_frame(neutral_site=[False, False, True])
    new = old.assign(neutral_site=[False, True, True])

    with pytest.raises(ValueError, match=r"moved games.*neutral_site.*\[2\]"):
        builder.check_game_set_unchanged(old, new, target_week=8)


def test_display_column_changes_are_accepted_in_every_week():
    old = schedule_frame(
        venue=["Old Field", "B", "C"],
        venue_id=[1, 2, 3],
        attendance=[None, None, None],
        neutral_site=[False, False, True],
    )
    new = old.assign(
        venue=["New Field", "B2", "C2"],
        venue_id=[9, 2, 3],
        attendance=[50000, None, 1],
    )

    assert builder.check_game_set_unchanged(old, new, target_week=8) == []


def test_a_completed_week_kickoff_correction_is_reported_not_refused():
    old = schedule_frame()
    new = schedule_frame(
        kickoff_utc=pd.to_datetime(
            ["2026-10-17T17:00Z", "2026-10-24T05:00Z", "2026-10-24T05:00Z"]
        )
    )

    assert builder.check_game_set_unchanged(old, new, target_week=8) == [1]


CUTOFFS = {"7": "2026-10-13T18:00:00Z", "8": "2026-10-19T14:10:00Z"}


def outcome_moves(old, new, quote_times, cutoffs=CUTOFFS):
    quotes = pd.DataFrame(
        {
            "game_id": [g for g, _ in quote_times],
            "captured_at": pd.to_datetime([t for _, t in quote_times], utc=True),
        }
    )
    return builder.kickoff_outcome_moves(
        old, new, quotes=quotes, cutoffs=cutoffs, target_week=8
    )


def test_completed_week_kickoff_correction_with_unchanged_outcomes_is_accepted():
    old = schedule_frame()
    new = schedule_frame(
        kickoff_utc=pd.to_datetime(
            ["2026-10-17T17:00Z", "2026-10-24T19:30Z", "2026-10-24T23:00Z"]
        )
    )

    # The quote predates both the old and the corrected kickoff.
    assert outcome_moves(old, new, [(1, "2026-10-16T12:00Z")]) == []


def test_kickoff_correction_that_flips_quote_eligibility_names_the_game():
    old = schedule_frame()
    new = schedule_frame(
        kickoff_utc=pd.to_datetime(
            ["2026-10-17T15:00Z", "2026-10-24T05:00Z", "2026-10-24T05:00Z"]
        )
    )

    # Captured 15:30: before the old 16:00 kickoff, after the corrected 15:00.
    assert outcome_moves(old, new, [(1, "2026-10-17T15:30Z")]) == [1]


def test_kickoff_correction_that_breaks_the_pre_week_cutoff_names_the_games():
    old = schedule_frame()
    # Game 1 moves to after the week 8 cutoff minus six hours: unsettled at cutoff.
    late = schedule_frame(
        kickoff_utc=pd.to_datetime(
            ["2026-10-19T10:00Z", "2026-10-24T05:00Z", "2026-10-24T05:00Z"]
        )
    )
    # A week 8 game moves to before the week 8 cutoff.
    early = schedule_frame(
        kickoff_utc=pd.to_datetime(
            ["2026-10-17T16:00Z", "2026-10-19T12:00Z", "2026-10-24T05:00Z"]
        )
    )

    assert outcome_moves(old, late, []) == [1]
    assert outcome_moves(old, early, []) == [2]


def test_main_refuses_a_kickoff_correction_that_moves_eligibility_without_writing(
    tmp_path, monkeypatch, registered
):
    store = SimpleNamespace(
        read_bytes=lambda key: json.dumps(
            {"uri": SCHEDULE["uri"], "content_sha": SCHEDULE["sha256"]}
        ).encode()
    )
    monkeypatch.setattr(builder, "get_storage", lambda environment: store)
    old = pd.DataFrame(
        {
            "game_id": [1, 2],
            "season": 2026,
            "week": [7, 8],
            "home_team": ["A", "C"],
            "away_team": ["B", "D"],
            "kickoff_utc": pd.to_datetime(["2026-10-17T16:00Z", "2026-10-24T19:00Z"]),
        }
    )
    fresh = old.assign(
        kickoff_utc=pd.to_datetime(["2026-10-17T15:00Z", "2026-10-24T19:00Z"])
    )
    quotes = pd.DataFrame(
        {"game_id": [1], "captured_at": pd.to_datetime(["2026-10-17T15:30Z"])}
    )
    pins = {SCHEDULE["uri"]: fresh, QUOTES_SOURCE_URI: quotes}
    monkeypatch.setattr(
        builder,
        "frame",
        lambda s, pin: pins.get(pin["uri"], old),
    )
    target = tmp_path / "out.json"

    with pytest.raises(SystemExit, match=r"outcome for games \[1\]"):
        builder.main(
            ["--from-manifest", str(SOURCE), "--to-manifest", str(target),
             "--revision-id", "r", "--cutoff", CUTOFF, "--target-week", "8",
             "--schedule-ref", "artifacts/preview/pipeline-runs/r/games_ref.json"]
        )  # fmt: skip

    assert not target.exists()
    assert registered == []


def test_main_stops_before_writing_when_the_refreshed_game_set_changed(
    tmp_path, monkeypatch, registered
):
    ref = "artifacts/preview/pipeline-runs/r/games_ref.json"
    store = SimpleNamespace(
        read_bytes=lambda key: json.dumps(
            {"uri": SCHEDULE["uri"], "content_sha": SCHEDULE["sha256"]}
        ).encode()
    )
    monkeypatch.setattr(builder, "get_storage", lambda environment: store)
    old = pd.DataFrame(
        {
            "game_id": [1],
            "season": 2026,
            "week": 8,
            "home_team": "A",
            "away_team": "B",
            "kickoff_utc": pd.to_datetime(["2026-10-24T05:00Z"]),
        }
    )
    fresh = old.assign(game_id=2)
    monkeypatch.setattr(
        builder,
        "frame",
        lambda s, pin: fresh if pin == SCHEDULE else old,
    )
    target = tmp_path / "out.json"

    with pytest.raises(SystemExit, match="added games"):
        builder.main(
            ["--from-manifest", str(SOURCE), "--to-manifest", str(target),
             "--revision-id", "r", "--cutoff", CUTOFF, "--target-week", "8",
             "--schedule-ref", ref]
        )  # fmt: skip

    assert not target.exists()
    assert registered == []
