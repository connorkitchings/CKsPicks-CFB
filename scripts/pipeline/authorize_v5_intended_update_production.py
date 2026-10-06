#!/usr/bin/env python3
"""Production-only entrypoint for packet-bound V5 authorization."""

import os

from scripts.pipeline.authorize_v5_intended_update_batch import main

if __name__ == "__main__":
    os.environ["CKS_V5_AUTHORIZER_FORCED_ENV"] = "production"
    main()
