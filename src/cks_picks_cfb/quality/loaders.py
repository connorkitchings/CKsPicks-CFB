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


def request_key(entity: str, parameters: Mapping[str, Any]) -> str:
    """Stable identity of one provider request: entity plus canonical parameters."""
    return f"{entity}:{json.dumps(dict(parameters), sort_keys=True, default=str)}"


def capture_requests(cur: Any, year: int) -> tuple[set[str], set[str]]:
    """(requested, completed) CFBD request keys for ``year`` from the ingestion runs.

    Every request ever begun is expected; a request is completed when some run that
    carried it succeeded. A request that failed and was never retried is the gap.
    """
    cur.execute(
        "SELECT state, request FROM catalog.ingestion_runs "
        "WHERE provider = 'cfbd' "
        "AND request->'requests'->0->'parameters'->>'year' = %s",
        (str(year),),
    )
    expected: set[str] = set()
    completed: set[str] = set()
    for state, request in cur.fetchall():
        for item in (request or {}).get("requests", []):
            key = request_key(str(item.get("entity", "")), item.get("parameters") or {})
            expected.add(key)
            if state == "succeeded":
                completed.add(key)
    return expected, completed


def latest_odds_capture(cur: Any, year: int) -> dict[str, Any] | None:
    """The newest Odds API quote capture of ``year`` and its unmatched-event count."""
    cur.execute(
        "SELECT capture_id, response_metadata FROM catalog.source_captures "
        "WHERE provider = 'the_odds_api' AND entity = 'market_quotes' "
        "AND captured_at >= %s ORDER BY captured_at DESC LIMIT 1",
        (f"{year}-01-01T00:00:00Z",),
    )
    row = cur.fetchone()
    if row is None:
        return None
    metadata = row[1] or {}
    return {
        "capture_id": row[0],
        "unmatched_events": int(metadata.get("unmatched_events", 0)),
        "matched_events": int(metadata.get("matched_events", 0)),
    }


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
    from cks_picks_cfb.data.schema_contracts import DatasetSchemaError, schema_for

    context: dict[str, Any] = {
        "catalog_versions": catalog_versions(cur),
        "pins": pins,
        "inputs": {},
        "schemas": {},
        "schema_errors": {},
    }
    for name, dataset in SEASON_DATASETS.items():
        row = _ref_row(cur, dataset, year, pins.get(dataset))
        if row is None:
            continue
        context[name] = read(row)
        context["inputs"][name] = {"version_id": row[1], "content_sha": row[3]}
        try:
            context["schemas"][name] = (context[name], schema_for(dataset, str(row[2])))
        except DatasetSchemaError as exc:
            # A catalog version with no active contract is a finding, not a crash.
            context["schema_errors"][name] = str(exc)
    expected, completed = capture_requests(cur, year)
    if expected:
        context["expected_requests"] = expected
        context["completed_requests"] = completed
    odds = latest_odds_capture(cur, year)
    if odds is not None:
        context["odds_capture"] = odds
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


SILVER_DATASETS = (
    "byplay",
    "drives",
    "games",
    "source_reconciliation",
    "reconciled_team_game",
)


def _previous_ref_row(
    cur: Any, dataset: str, season: int, current_version: str
) -> tuple | None:
    """The newest validated version of ``dataset`` for ``season`` other than the current."""
    cur.execute(
        "SELECT dataset, version_id, schema_version, content_sha, uri "
        "FROM catalog.dataset_versions "
        "WHERE dataset = %s AND tier = 'silver' AND state = 'validated' "
        "AND partitions @> %s::jsonb AND version_id <> %s "
        "ORDER BY as_of DESC, created_at DESC LIMIT 1",
        [dataset, json.dumps({"seasons": [season]}), current_version],
    )
    return cur.fetchone()


def build_silver_context(
    cur: Any,
    read: Callable[[tuple], pd.DataFrame],
    *,
    year: int,
    pins: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the silver-stage context for ``year`` (read-only)."""
    pins = dict(pins or {})
    context: dict[str, Any] = {"pins": pins, "inputs": {}}
    for dataset in SILVER_DATASETS:
        row = _ref_row(cur, dataset, year, pins.get(dataset))
        if row is None:
            continue
        context["team_game" if dataset == "reconciled_team_game" else dataset] = read(
            row
        )
        context["inputs"][dataset] = {"version_id": row[1], "content_sha": row[3]}
        if dataset == "games":
            previous = _previous_ref_row(cur, "games", year, row[1])
            if previous is not None:
                context["games_previous"] = read(previous)
                context["inputs"]["games_previous"] = {
                    "version_id": previous[1],
                    "content_sha": previous[3],
                }
    cur.execute(
        "SELECT capture_id, content_sha, object_sha, uri, captured_at "
        "FROM catalog.source_captures WHERE entity = 'games'"
    )
    context["capture_index"] = pd.DataFrame(
        cur.fetchall(),
        columns=["capture_id", "content_sha", "object_sha", "uri", "captured_at"],
    )
    return context


def load_silver_context(
    environment: str, year: int, *, pins: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Open the environment's catalog read-only and build the silver context."""
    return _with_connection(
        environment,
        lambda cur, read: build_silver_context(cur, read, year=year, pins=pins),
    )


def _with_connection(environment: str, fn: Callable[[Any, Callable], Any]) -> Any:
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
            return fn(cur, read)


def load_ingest_context(
    environment: str, year: int, *, pins: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Open the environment's catalog read-only and build the ingest context."""
    return _with_connection(
        environment,
        lambda cur, read: build_ingest_context(cur, read, year=year, pins=pins),
    )
