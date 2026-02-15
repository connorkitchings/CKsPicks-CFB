# Basic import smoke tests for key modules
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib

import pytest

MODULES = [
    "cks_picks_cfb.features.byplay",
    "cks_picks_cfb.features.core",
    "cks_picks_cfb.features.pipeline",
    "cks_picks_cfb.features.persist",
    "cks_picks_cfb.models.v1_baseline",
    "cks_picks_cfb.utils.logging",
]


@pytest.mark.parametrize("mod", MODULES)
def test_import_module(mod: str):
    importlib.import_module(mod)
