#!/usr/bin/env sh
# Serve the app at http://localhost:8000 (Ctrl+C to stop).
cd "$(dirname "$0")/web" || exit 1
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "Python 3 is not installed. Get it from https://www.python.org/downloads/"; exit 1; }
echo "Terra Twin is running at http://localhost:8000  (press Ctrl+C to stop)"
( sleep 1; (command -v open >/dev/null && open http://localhost:8000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8000) ) >/dev/null 2>&1 &
exec "$PY" -m http.server 8000
