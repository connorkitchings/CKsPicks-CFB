#!/usr/bin/env zsh
# Run a Preview-only command with branch-scoped credentials from the local
# macOS Keychain. No database URL is written to the repository or Vercel.

set -euo pipefail

if (( $# == 0 )); then
  print -u2 "Usage: zsh scripts/ops/with_preview_env.sh <command> [args...]"
  exit 64
fi

export PREVIEW_DATABASE_URL="$(
  security find-generic-password \
    -s 'ckspicks-cfb/preview-2026/pipeline-url' \
    -a cks_preview_pipeline \
    -w
)"
export DATABASE_URL="$(
  security find-generic-password \
    -s 'ckspicks-cfb/preview-2026/migrator-url' \
    -a cks_preview_migrator \
    -w
)"
export CFB_ARTIFACT_ENV="preview"

exec "$@"
