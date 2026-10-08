"""Persisted selection regression; TEST_DATABASE_URL must be disposable."""

import json
import os
from pathlib import Path

import pandas as pd
import psycopg
import pytest

from cks_picks_cfb.db.migrations import apply_migrations
from scripts.pipeline import publish_to_db


def test_null_lean_with_quotes_persists_no_selection(monkeypatch, tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable TEST_DATABASE_URL")
    with psycopg.connect(url, autocommit=True) as conn:
        for schema in ("ops", "catalog", "public"):
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conn.execute("CREATE SCHEMA public")
    apply_migrations(url, Path(__file__).resolve().parents[1] / "contracts/migrations")
    monkeypatch.chdir(tmp_path)
    rows, quotes = [], []
    for game, label in enumerate((None, "No Bet", "Home"), start=1):
        quote = f"q{game}"
        rows.append(
            {
                "game_id": game,
                "home_team": "A",
                "away_team": "B",
                "Spread Prediction": -7.0,
                "Total Prediction": 55.0,
                "home_team_spread_line": -3.0,
                "total_line": 50.0,
                "Spread Bet": label,
                "Total Bet": "Over" if label == "Home" else label,
                "market_snapshot_id": f"snap{game}",
                "source_quote_ids": json.dumps([quote]),
                "market_captured_at": "2026-08-28T18:00:00Z",
                "spread_market_quote_id": quote,
                "total_market_quote_id": quote,
            }
        )
        quotes.append(
            {
                "quote_id": quote,
                "game_id": game,
                "provider": "draftkings",
                "captured_at": "2026-08-28T17:50:00Z",
                "spread": -3.0,
                "total": 50.0,
            }
        )
    with psycopg.connect(url) as conn:
        for row in rows:
            conn.execute(
                "INSERT INTO games(game_id,season,week,home_team,away_team,start_date) VALUES (%s,2026,1,'A','B','2026-08-29T18:00:00Z')",
                (row["game_id"],),
            )
    assert (
        publish_to_db.publish_week(
            publish_to_db.prepare_predictions(pd.DataFrame(rows)),
            url,
            season=2026,
            week=1,
            high_conf_threshold=3.0,
            source_config="test",
            system_name="test",
            model_id="legacy-test",
            update_current=False,
            state="preview",
            market_quotes=pd.DataFrame(quotes),
        )
        == 3
    )
    with psycopg.connect(url) as conn:
        selections = conn.execute(
            "SELECT game_id, target, side FROM prediction_market_selections ORDER BY game_id,target"
        ).fetchall()
        assert selections == [(3, "spread", "home"), (3, "total", "over")]
        assert conn.execute("SELECT count(*) FROM predictions").fetchone()[0] == 3
