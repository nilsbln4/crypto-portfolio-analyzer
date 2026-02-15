#!/usr/bin/env bash
# Render build script — runs on every deploy
set -o errexit

pip install -r requirements.txt

# Create tables and seed assets + portfolio templates (idempotent)
flask seed

# Fetch historical price data for charts (idempotent, skips cached)
flask seed-history

# Promote admin if ADMIN_EMAIL is set (idempotent)
if [ -n "$ADMIN_EMAIL" ]; then
    flask promote-admin "$ADMIN_EMAIL"
fi
