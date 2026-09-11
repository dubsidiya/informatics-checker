#!/bin/sh
set -e
cd "$(dirname "$0")"

if ! curl -sf --max-time 2 http://127.0.0.1:8765/health >/dev/null; then
  echo "Starting local checker on 127.0.0.1:8765"
  HOST=127.0.0.1 python3 app.py &
  sleep 1
fi

echo "Public link will appear below. Keep this window open."
exec npx --yes localtunnel --port 8765
