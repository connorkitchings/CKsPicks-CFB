"""Data ingestion modules for CFBD API data.

This package contains modules for ingesting data from the CollegeFootballData API
into a local CSV storage backend. All modules follow FBS-only filtering and year-specific
data ingestion patterns.
"""

from .base import BaseIngester
from .betting_lines import BettingLinesIngester
from .coaches import CoachesIngester
from .games import GamesIngester
from .plays import PlaysIngester
from .rosters import RostersIngester
from .teams import TeamsIngester
from .venues import VenuesIngester

__all__ = [
    "BaseIngester",
    "TeamsIngester",
    "VenuesIngester",
    "GamesIngester",
    "BettingLinesIngester",
    "RostersIngester",
    "CoachesIngester",
    "PlaysIngester",
]
