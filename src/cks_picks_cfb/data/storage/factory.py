"""Storage factory functions for instantiating configured backends."""

from __future__ import annotations

from cks_picks_cfb.data.storage.base import StorageBackend, StorageSettings
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.data.storage.r2 import R2Storage, ReadOnlyStorage, S3Storage


def get_source_storage() -> ReadOnlyStorage:
    """Return the separately configured historical source as read-only."""
    settings = StorageSettings.source_from_env()
    missing = [
        name
        for name, value in {
            "CFB_R2_SOURCE_BUCKET": settings.bucket,
            "CFB_R2_SOURCE_ACCOUNT_ID": settings.account_id,
            "CFB_R2_SOURCE_ACCESS_KEY": settings.access_key,
            "CFB_R2_SOURCE_SECRET_KEY": settings.secret_key,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Historical source storage requires: {', '.join(missing)}")
    backend = get_storage(settings)
    return ReadOnlyStorage(backend)


def get_storage(
    settings: StorageSettings | None = None, *, environment: str | None = None
) -> StorageBackend:
    """Get storage instance based on environment configuration.

    Returns:
        Configured storage backend instance

    Raises:
        ValueError: If storage backend is not configured or invalid
    """
    settings = settings or StorageSettings.from_env(environment=environment)
    backend = settings.backend.lower()

    if backend == "local":
        data_root = settings.data_root
        if not data_root:
            raise ValueError(
                "CFB_MODEL_DATA_ROOT must be set for local storage backend"
            )
        return LocalStorage(data_root)

    elif backend == "r2":
        selected = settings.environment
        prefix = (
            "CFB_R2_PREVIEW"
            if selected == "preview"
            else "CFB_R2_SOURCE"
            if selected == "source"
            else "CFB_R2"
        )
        bucket = settings.bucket
        account_id = settings.account_id
        access_key = settings.access_key
        secret_key = settings.secret_key
        endpoint = settings.endpoint

        if not all([bucket, account_id, access_key, secret_key]):
            raise ValueError(
                f"R2 {selected} storage requires: {prefix}_BUCKET, "
                f"{prefix}_ACCOUNT_ID, {prefix}_ACCESS_KEY, {prefix}_SECRET_KEY"
            )

        assert (
            bucket is not None
            and account_id is not None
            and access_key is not None
            and secret_key is not None
        )
        return R2Storage(bucket, account_id, access_key, secret_key, endpoint)

    elif backend == "s3":
        bucket = settings.bucket
        region = settings.region
        access_key = settings.access_key
        secret_key = settings.secret_key

        if not bucket:
            raise ValueError("S3 storage requires: CFB_S3_BUCKET")

        return S3Storage(bucket, region, access_key, secret_key)

    else:
        raise ValueError(
            f"Invalid storage backend: {backend}. Must be 'local', 'r2', or 's3'"
        )
