# Basic import smoke tests for key modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib

import pytest

MODULES = [
    "features.byplay",
    "features.core",
    "features.pipeline",
    "features.persist",
    "models.train_model",
    "utils.logging",
]


@pytest.mark.parametrize("mod", MODULES)
def test_import_module(mod: str):
    importlib.import_module(mod)