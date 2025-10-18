# Smoke test for presence of module-level docstrings in priority packages

import ast
import os

PRIORITY_DIRS = [
    os.path.join("src", "data"),
    os.path.join("src", "models"),
    os.path.join("src", "utils"),
]


def iter_py_files(root_dirs):
    for root_dir in root_dirs:
        for r, _, files in os.walk(root_dir):
            for f in files:
                if f.endswith(".py"):
                    yield os.path.join(r, f)


def test_priority_modules_have_docstrings():
    missing = []
    for path in iter_py_files(PRIORITY_DIRS):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except Exception:
            continue
        if ast.get_docstring(tree) is None:
            # Allow __init__.py in non-public subpackages to be empty
            if os.path.basename(path) == "__init__.py":
                continue
            missing.append(path)
    assert not missing, f"Missing module docstrings: {missing}"
