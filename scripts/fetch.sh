#!/bin/bash
# CTF Calendar data fetcher — invoked by cron
# Calls flask fetch for each enabled scraper.
set -euo pipefail

cd "$(dirname "$0")/.."
export FLASK_APP=app
export FLASK_ENV=production

# Log file — rotated by logrotate or manually
LOG_DIR="${HOME}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/ctf-fetch.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting fetch..." >> "$LOG_FILE"

# Ensure venv is active if one exists
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

flask fetch >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fetch complete." >> "$LOG_FILE"
