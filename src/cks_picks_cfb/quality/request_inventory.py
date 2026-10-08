"""Expected provider requests from a reviewed inventory, never the attempt ledger."""

from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.quality.loaders import request_key


def expected_request_keys(manifest: Mapping[str, Any], year: int) -> set[str]:
    """Validate the independent request inventory and return exact request identities.

    Parameters use the same full identity as SourceRequest, including expected game
    ids and provider/canonical weeks. A request from a smaller slate cannot satisfy it.
    The schedule reference binds the inventory to an immutable schedule, rather than
    to the subset of games already present in the serving database.
    """
    if manifest.get("schema_version") != "cfbd_expected_requests_v1":
        raise ValueError("unknown expected-request inventory schema")
    if manifest.get("season") != year:
        raise ValueError("expected-request inventory season differs")
    ref = manifest.get("schedule_ref", {})
    if not ref.get("version_id") or not ref.get("content_sha"):
        raise ValueError("expected-request inventory needs a pinned schedule_ref")
    requests = manifest.get("requests")
    if not isinstance(requests, list) or not requests:
        raise ValueError("expected-request inventory must not be empty")
    keys = set()
    for item in requests:
        parameters = item.get("parameters")
        if (
            item.get("provider") != "cfbd"
            or not item.get("entity")
            or not isinstance(parameters, Mapping)
            or parameters.get("year") != year
        ):
            raise ValueError("invalid expected CFBD request")
        key = request_key(item["entity"], parameters)
        if key in keys:
            raise ValueError("duplicate expected request")
        keys.add(key)
    return keys
