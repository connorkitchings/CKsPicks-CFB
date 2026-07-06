"""Global pytest configuration.

Ensures tests default to local storage backend so they don't accidentally
hit R2/cloud storage during unit testing. Tests that explicitly need cloud
storage should set CFB_STORAGE_BACKEND in their own fixture.
"""

import os

# Default to local storage for all tests. Individual tests that need cloud
# (e.g., test_storage_entity_api cloud integration) can override this.
os.environ.setdefault("CFB_STORAGE_BACKEND", "local")
