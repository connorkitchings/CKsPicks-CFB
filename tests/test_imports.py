# Basic import smoke tests for key modules

import importlib

import pytest

MODULES = [
    "cfb_model.data.aggregations.byplay",
    "cfb_model.data.aggregations.core",
    "cfb_model.data.aggregations.pipeline",
    "cfb_model.data.aggregations.persist",
    "cfb_model.models.train_model",
    "cfb_model.utils.logging",
]


@pytest.mark.parametrize("mod", MODULES)
def test_import_module(mod: str):
    importlib.import_module(mod)
