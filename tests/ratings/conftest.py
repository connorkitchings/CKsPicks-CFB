"""Shared fixtures for the Phase 1 rating measurement tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from helpers import AS_OF, simple_league

from cks_picks_cfb.ratings.contracts import load_measurement_config

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture(scope="session")
def config():
    return load_measurement_config("conf/ratings/measurement_baseline_v1.yaml")


@pytest.fixture(scope="session")
def league():
    return simple_league()


@pytest.fixture(scope="session")
def as_of():
    return AS_OF
