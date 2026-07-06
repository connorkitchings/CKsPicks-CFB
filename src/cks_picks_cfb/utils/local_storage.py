"""Local storage backend — compatibility shim.

Re-exports LocalStorage from cks_picks_cfb.data.storage. The old constructor
signature (data_root, file_format, data_type) is preserved for backward
compatibility with BaseIngester and existing call sites.

For new code, import LocalStorage directly from cks_picks_cfb.data.storage.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from cks_picks_cfb.data import storage as _storage_mod


class LocalStorage(_storage_mod.LocalStorage):
    """Backward-compatible LocalStorage.

    Accepts the old constructor args and translates them to the canonical
    data/storage.py:LocalStorage(root_path) form.
    """

    def __init__(
        self,
        data_root: str | Path | None = None,
        file_format: Literal["parquet", "csv"] = "parquet",
        data_type: Literal["raw", "interim", "processed"] = "raw",
    ) -> None:
        base_root = (
            Path(data_root)
            if data_root is not None
            else Path(os.getenv("CFB_MODEL_DATA_ROOT"))
            if os.getenv("CFB_MODEL_DATA_ROOT")
            else (Path.cwd() / "data")
        )
        # Old LocalStorage appended data_type to root (e.g., /data/raw, /data/processed).
        # Preserve this behavior for backward compat with existing callers.
        root_path = Path(base_root) / data_type
        if not root_path.exists():
            from cks_picks_cfb.data.storage import StorageError

            raise StorageError(
                f"Data root path is not a directory: {root_path}. "
                "Set CFB_MODEL_DATA_ROOT or pass data_root."
            )
        super().__init__(str(root_path))
        self.file_format = file_format
        self._data_type = data_type


__all__ = ["LocalStorage"]
