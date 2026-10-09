"""Provider-keyed (v2) possession ledger contracts (contract 2026-10-09/01, Task 4).

v2 keeps every v1 column and meaning and changes identity only:

* a possession is a provider drive by one offense, keyed ``(season, game_id, drive_id, offense)``;
  ``drive_number`` stays as an attribute (the smallest number the drive carries);
* a scoring event is the provider play that moved the score, with the three-segment id
  ``season:game_id:source_play_id``. The id is game-qualified because synthetic negative
  provider ids repeat across games, and it can never equal a pinned four-segment v1 id
  (``season:game:drive:play``), so a mixed lookup fails loudly instead of mis-joining.

This module is separate from ``data_first_possession_v1`` so v1 contracts, hashes and pins are
never edited. Population, snapshots, history, terminal and coverage datasets keep their v1
versions; the forecast materializer therefore refuses v2 possession references by design.
"""

from __future__ import annotations

import re
from typing import Any

from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_COLUMNS,
    POSSESSION_DATASETS,
    SCORING_EVENT_COLUMNS,
)

POSSESSION_SCHEMA_V2 = "data_first_possession_possession_v2"
SCORING_EVENT_SCHEMA_V2 = "data_first_possession_scoring_event_v2"
OBSERVATION_SCHEMA_V2 = "data_first_possession_observation_v2"

POSSESSION_COLUMNS_V2 = (
    *POSSESSION_COLUMNS[: POSSESSION_COLUMNS.index("drive_number") + 1],
    "drive_id",
    *POSSESSION_COLUMNS[POSSESSION_COLUMNS.index("drive_number") + 1 :],
)
SCORING_EVENT_COLUMNS_V2 = (
    *SCORING_EVENT_COLUMNS[: SCORING_EVENT_COLUMNS.index("source_event_id") + 1],
    "source_play_id",
    *SCORING_EVENT_COLUMNS[SCORING_EVENT_COLUMNS.index("source_event_id") + 1 :],
    "drive_id",
)

POSSESSION_DATASETS_V2 = {
    **POSSESSION_DATASETS,
    "possessions": ("possession_ledger", POSSESSION_SCHEMA_V2),
    "scoring_events": ("possession_scoring_event", SCORING_EVENT_SCHEMA_V2),
    "observations": ("possession_observation", OBSERVATION_SCHEMA_V2),
}

#: ``season:game_id:source_play_id`` (provider ids may be negative).
EVENT_ID_V2 = re.compile(r"\d+:\d+:-?\d+")


def source_event_id_v2(season: Any, game_id: Any, source_play_id: Any) -> str:
    """The v2 scoring-event id for a provider play."""
    return f"{int(season)}:{int(game_id)}:{source_play_id}"


def is_event_id_v2(value: Any) -> bool:
    return isinstance(value, str) and EVENT_ID_V2.fullmatch(value) is not None
