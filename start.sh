#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8787}"
exec "$DIR/.venv/bin/uvicorn" server:app --app-dir "$DIR" --host 0.0.0.0 --port "$PORT"
