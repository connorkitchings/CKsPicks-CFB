#!/usr/bin/env zsh
# Run an owner-only production command (season release rollback) with the
# Production owner/migrator branch URL from the local macOS Keychain. No
# database URL is written to the repository, Vercel, shell history, or logs.
#
# The Keychain item is owner-provisioned (see docs/ops/weekly_runbook.md,
# "Owner credential"). Override the item with CFB_OWNER_KEYCHAIN_SERVICE and
# CFB_OWNER_KEYCHAIN_ACCOUNT. Restricted pipeline/web logins are refused, the
# same as run_season.py rollback (season/release.py).

set -euo pipefail

if (( $# == 0 )); then
  print -u2 "Usage: zsh scripts/ops/with_production_owner_env.sh <command> [args...]"
  exit 64
fi

service="${CFB_OWNER_KEYCHAIN_SERVICE:-ckspicks-cfb/production/owner-url}"
account="${CFB_OWNER_KEYCHAIN_ACCOUNT:-cks_prod_owner}"

owner_url="$(
  security find-generic-password -s "$service" -a "$account" -w 2>/dev/null
)" || {
  print -u2 "Missing Keychain item '$service' (account $account)."
  print -u2 "The owner must create it first; see docs/ops/weekly_runbook.md (Owner credential)."
  exit 66
}

# Login role = URL user (scheme://user[:password]@host/...). Parsed, never printed.
authority="${owner_url#*://}"
authority="${authority%%/*}"
if [[ "$authority" != *@* ]]; then
  print -u2 "Keychain item '$service' does not contain a URL with a login role."
  exit 65
fi
role="${${authority%@*}%%:*}"
if [[ -z "$role" || "$role" == *_pipeline || "$role" == *_web ]]; then
  print -u2 "Keychain item '$service' resolves to a restricted pipeline/web role; rollback requires the owner/migrator login."
  exit 65
fi

export DATABASE_URL="$owner_url"
export CFB_ARTIFACT_ENV="production"
unset owner_url authority role

exec "$@"
