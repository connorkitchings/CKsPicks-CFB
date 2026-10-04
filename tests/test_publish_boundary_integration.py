"""publish_week with a recording fake connection: blocked payloads write nothing."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "pipeline"))

import publish_to_db  # noqa: E402

from cks_picks_cfb.quality.publish import PublishQualityError  # noqa: E402


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self._rows: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.db.executed.append(flat)
        if flat.startswith("INSERT INTO predictions"):
            self.db.written.append(int(params["game_id"]))
        if "SELECT state FROM prediction_runs" in sql:
            self._rows = []
        elif "FROM games WHERE season" in sql:
            self._rows = [(g,) for g in self.db.schedule]
        elif "SELECT game_id FROM predictions" in sql:
            self._rows = [(g,) for g in self.db.stored_predictions()]
        elif "FROM prediction_market_selections" in sql:
            self._rows = []
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.db.commits += 1


class FakeDb:
    def __init__(self, schedule, drop_stored=()):
        self.schedule = schedule
        self.drop_stored = set(drop_stored)
        self.executed: list[str] = []
        self.commits = 0
        self.written: list[int] = []

    def stored_predictions(self):
        return [g for g in self.written if g not in self.drop_stored]

    def writes(self, prefix):
        return [s for s in self.executed if s.startswith(prefix)]


def _df(ids=(1, 2)):
    return pd.DataFrame(
        {
            "game_id": list(ids),
            "home_team": ["A"] * len(ids),
            "away_team": ["B"] * len(ids),
            "Spread Prediction": [-3.0] * len(ids),
            "Total Prediction": [50.0] * len(ids),
            "home_team_spread_line": [None] * len(ids),
            "total_line": [None] * len(ids),
            "Spread Bet": ["No Bet"] * len(ids),
            "Total Bet": ["No Bet"] * len(ids),
        }
    )


@pytest.fixture
def harness(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # receipts land under tmp_path/artifacts
    monkeypatch.setattr(publish_to_db, "assert_active_pipeline_lease", lambda cur: None)

    def install(db):
        monkeypatch.setattr(publish_to_db.psycopg, "connect", lambda url: FakeConn(db))

    return install


def _publish(df, **kw):
    return publish_to_db.publish_week(
        df,
        "postgres://fake",
        season=2026,
        week=1,
        high_conf_threshold=3.0,
        source_config="conf/test.yaml",
        system_name="test",
        model_id="legacy-test",
        update_current=False,
        state="preview",
        **kw,
    )


def test_happy_path_commits_and_writes_both_receipts(harness, tmp_path):
    db = FakeDb(schedule=[1, 2])
    harness(db)
    assert _publish(_df()) == 2
    assert db.commits == 1 and db.written == [1, 2]
    receipts = sorted((tmp_path / "artifacts/quality/receipts/publish").glob("*.json"))
    assert len(receipts) == 2


def test_missing_scheduled_game_blocks_before_any_write(harness):
    db = FakeDb(schedule=[1, 2, 3])
    harness(db)
    with pytest.raises(PublishQualityError, match="schedule_coverage"):
        _publish(_df())
    assert (
        db.commits == 0
        and db.writes("INSERT INTO prediction_runs") == []
        and db.written == []
    )


def test_partial_slate_override_is_allowed_and_recorded(harness, tmp_path):
    db = FakeDb(schedule=[1, 2, 3])
    harness(db)
    assert _publish(_df(), allow_partial_slate=True) == 2
    assert db.commits == 1
    assert any(
        "allowed by operator" in p.read_text()
        for p in (tmp_path / "artifacts/quality/receipts/publish").glob("*.json")
    )


def test_a_null_required_field_blocks_before_any_write(harness):
    df = _df()
    df.loc[0, "Spread Prediction"] = None
    db = FakeDb(schedule=[1, 2])
    harness(db)
    with pytest.raises(PublishQualityError, match="required_fields"):
        _publish(df)
    assert db.commits == 0 and db.written == []


def test_readback_mismatch_raises_before_commit(harness):
    db = FakeDb(schedule=[1, 2], drop_stored=[2])  # the database "loses" game 2
    harness(db)
    with pytest.raises(PublishQualityError, match="predictions_readback"):
        _publish(_df())
    assert db.commits == 0


# --- scoring -----------------------------------------------------------------

import score_to_db  # noqa: E402


class ScoreCursor:
    def __init__(self, db):
        self.db = db
        self._row = None
        self._rows: list = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        if "to_regclass" in flat:
            self._row = (True,)
        elif "SELECT state, evidence_class FROM prediction_runs" in flat:
            self._row = ("frozen", "live")
        elif (
            "FROM prediction_market_selections" in flat
            and "prediction_grades" not in flat
        ):
            target = params[2]
            point = -3.5 if target == "spread" else 50.5
            side = "away" if target == "spread" else "under"
            self._row = (
                "snap",
                f"q-{target}",
                side,
                point,
                -110.0,
                "model_side_best_quote_v2",
            )
        elif flat.startswith("INSERT INTO prediction_grades"):
            self.db.grades.append(params)
        elif "FROM prediction_grades pg" in flat:
            self._rows = [
                (
                    g["game_id"],
                    g["target"],
                    g["side"],
                    -3.5 if g["target"] == "spread" else 50.5,
                    self.db.stored_result(g),
                    24,
                    21,
                )
                for g in self.db.grades
            ]
        else:
            self._row, self._rows = None, []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class ScoreConn(FakeConn):
    def cursor(self):
        return ScoreCursor(self.db)


class ScoreDb:
    def __init__(self, corrupt=False):
        self.grades: list[dict] = []
        self.commits = 0
        self.corrupt = corrupt

    def stored_result(self, grade):
        return "push" if self.corrupt else grade["result"]


def test_scoring_commits_when_grades_recompute_and_rolls_back_when_they_do_not(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(score_to_db, "assert_active_pipeline_lease", lambda cur: None)
    monkeypatch.setattr(score_to_db, "_recompute_stats", lambda cur, season: None)
    scored = pd.DataFrame(
        {
            "game_id": [7],
            "home_points": [24],
            "away_points": [21],
            "spread_lean": ["home"],
            "spread_result_norm": ["win"],
            "total_lean": ["over"],
            "total_result_norm": ["win"],
        }
    )

    ok = ScoreDb()
    monkeypatch.setattr(score_to_db.psycopg, "connect", lambda url: ScoreConn(ok))
    count, _stats = score_to_db.publish_scored_run(
        scored, "postgres://fake", run_id="r1", season=2026
    )
    assert count == 1 and ok.commits == 1
    assert {g["result"] for g in ok.grades} == {
        "win"
    }  # away -3.5 and under 50.5 both win 24-21

    bad = ScoreDb(corrupt=True)
    monkeypatch.setattr(score_to_db.psycopg, "connect", lambda url: ScoreConn(bad))
    with pytest.raises(PublishQualityError, match="grades_recomputed"):
        score_to_db.publish_scored_run(
            scored, "postgres://fake", run_id="r1", season=2026
        )
    assert bad.commits == 0
