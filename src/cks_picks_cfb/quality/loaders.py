"""Build quality-run contexts from the catalog and Silver. Read-only.

``build_ingest_context`` takes an open cursor and a ``read`` callable so tests can
inject fakes. A dataset that is not in the catalog for the season is simply left out
of the context, which makes the checks that need it report ``skipped``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping

import pandas as pd

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}
# Silver datasets read for the ingest stage, keyed by context name.
SEASON_DATASETS = {
    "games": "games",
    "plays": "plays",
    "drives": "drives",
}


def _ref_row(
    cur: Any, dataset: str, season: int | None, pin: str | None
) -> tuple | None:
    query = (
        "SELECT dataset, version_id, schema_version, content_sha, uri "
        "FROM catalog.dataset_versions "
        "WHERE dataset = %s AND tier = 'silver' AND state = 'validated' "
    )
    params: list[Any] = [dataset]
    if pin is not None:
        query += "AND version_id = %s "
        params.append(pin)
    elif season is not None:
        query += "AND partitions @> %s::jsonb "
        params.append(json.dumps({"seasons": [season]}))
    query += "ORDER BY as_of DESC, created_at DESC LIMIT 1"
    cur.execute(query, params)
    return cur.fetchone()


def catalog_versions(cur: Any) -> pd.DataFrame:
    cur.execute(
        "SELECT dataset, version_id, as_of, partitions FROM catalog.dataset_versions "
        "WHERE tier = 'silver' AND state = 'validated'"
    )
    frame = pd.DataFrame(
        cur.fetchall(), columns=["dataset", "version_id", "as_of", "partitions"]
    )
    frame["seasons"] = frame["partitions"].map(
        lambda p: list((p or {}).get("seasons", []))
    )
    return frame.drop(columns="partitions")


def parse_pins(values: list[str] | None) -> dict[str, str]:
    pins: dict[str, str] = {}
    for item in values or []:
        dataset, sep, version = item.partition("=")
        if not sep or not dataset or not version:
            raise ValueError(f"--pin must look like dataset=version_id, got {item!r}")
        pins[dataset] = version
    return pins


def build_ingest_context(
    cur: Any,
    read: Callable[[tuple], pd.DataFrame],
    *,
    year: int,
    pins: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the ingest-stage context for ``year``.

    ``read`` receives the catalog row ``(dataset, version_id, schema_version,
    content_sha, uri)`` and returns the Silver frame. The schedule is the games
    the site publishes (Neon ``games``), so Silver ingestion is compared against
    what users see.
    """
    pins = dict(pins or {})
    context: dict[str, Any] = {
        "catalog_versions": catalog_versions(cur),
        "pins": pins,
        "inputs": {},
    }
    for name, dataset in SEASON_DATASETS.items():
        row = _ref_row(cur, dataset, year, pins.get(dataset))
        if row is None:
            continue
        context[name] = read(row)
        context["inputs"][name] = {"version_id": row[1], "content_sha": row[3]}
    cur.execute("SELECT season, week, game_id FROM games WHERE season = %s", (year,))
    context["schedule"] = pd.DataFrame(
        cur.fetchall(), columns=["season", "week", "game_id"]
    )
    # Prices live on the Neon quotes (Odds API); Silver quotes carry no price columns.
    cur.execute(
        "SELECT q.quote_id, q.home_spread_price, q.away_spread_price, q.over_price, "
        "q.under_price FROM market_quotes q JOIN games g ON g.game_id = q.game_id "
        "WHERE g.season = %s",
        (year,),
    )
    context["market_quotes"] = pd.DataFrame(
        cur.fetchall(),
        columns=[
            "quote_id",
            "home_spread_price",
            "away_spread_price",
            "over_price",
            "under_price",
        ],
    )
    return context


def load_ingest_context(
    environment: str, year: int, *, pins: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Open the environment's catalog read-only and build the ingest context."""
    import psycopg
    from dotenv import load_dotenv

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage

    load_dotenv()
    url = os.environ.get(URL_ENV[environment])
    if not url:
        raise RuntimeError(
            f"Set {URL_ENV[environment]} to load the {environment} context"
        )
    storage = get_storage(environment=environment)

    def read(row: tuple) -> pd.DataFrame:
        return read_dataset(storage, DatasetRef(*[str(x) for x in row]))

    with psycopg.connect(url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            return build_ingest_context(cur, read, year=year, pins=pins)
