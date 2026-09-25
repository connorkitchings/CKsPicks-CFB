#!/usr/bin/env zsh
# Run a production V5 command as the restricted cks_prod_pipeline role with
# branch-scoped credentials from the local macOS Keychain. No database URL is
# written to the repository, Vercel, shell history, or logs. The owner URL
# remains an admin/migration credential and must not be used here.

set -euo pipefail

if (( $# == 0 )); then
  print -u2 "Usage: zsh scripts/ops/with_production_pipeline_env.sh <command> [args...]"
  exit 64
fi

pipeline_url="$(
  security find-generic-password \
    -s 'ckspicks-cfb/production/pipeline-url' \
    -a cks_prod_pipeline \
    -w 2>/dev/null
)" || {
  print -u2 "Missing Keychain item 'ckspicks-cfb/production/pipeline-url' (account cks_prod_pipeline)."
  print -u2 "Provision the restricted production pipeline role before running V5 commands."
  exit 66
}

export DATABASE_URL="$pipeline_url"
export CFB_ARTIFACT_ENV="production"
unset pipeline_url

exec "$@"
