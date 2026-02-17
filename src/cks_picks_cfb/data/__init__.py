"""Data ingestion modules for CFBD API data.

This package contains modules for ingesting data from the CollegeFootballData API
into local or cloud storage backends. All modules follow FBS-only filtering and
year-specific data ingestion patterns.
"""

from .base import BaseIngester
from .betting_lines import BettingLinesIngester
from .coaches import CoachesIngester
from .external_ratings import ExternalRatingsIngester
from .game_stats import GameStatsIngester
from .games import GamesIngester
from .plays import PlaysIngester
from .rankings import RankingsIngester
from .recruiting import RecruitingIngester
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
    "GameStatsIngester",
    "RankingsIngester",
    "RecruitingIngester",
    "ExternalRatingsIngester",
]
