#!/usr/bin/env zsh
# Run the web app locally (including the matchup pages) against real Neon data.
#
#   zsh scripts/ops/run_web_local.sh [preview|production]   (default: preview)
#
# The matchup pages are open in local development and closed in production by
# default, so nothing in Vercel needs to change. The database login is the
# restricted pipeline role from the macOS Keychain (never the owner URL in
# web/.env); the app only reads. Preview holds the same Week 5 data as
# production. Port: PORT (default 3000).
set -euo pipefail

target="${1:-preview}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
case "$target" in
  preview) wrapper="with_preview_env.sh"; url_var="PREVIEW_DATABASE_URL" ;;
  production) wrapper="with_production_pipeline_env.sh"; url_var="DATABASE_URL" ;;
  *) print -u2 "Usage: zsh scripts/ops/run_web_local.sh [preview|production]"; exit 64 ;;
esac

print "Web on http://127.0.0.1:${PORT:-3000}/matchup  (data: $target, read-only use of the pipeline login)"
exec zsh "$root/scripts/ops/$wrapper" zsh -c '
  export DATABASE_URL="${'"$url_var"'}"
  cd "'"$root"'/web"
  exec npm run dev -- --hostname 127.0.0.1 --port "${PORT:-3000}"
'
