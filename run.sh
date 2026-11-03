#!/bin/bash
set -e
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if curl -sf --max-time 2 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "App is already running. Open: http://127.0.0.1:8000"
  exit 0
fi

echo "Starting FAQ app at http://127.0.0.1:8000"
exec .venv/bin/uvicorn src.app.main:app --host 127.0.0.1 --port 8000
