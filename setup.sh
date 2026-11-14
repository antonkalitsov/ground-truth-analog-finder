#!/usr/bin/env sh
# One-command setup for Mac and Linux.
#   ./setup.sh            start the app with the data pack that ships in the repo
#   ./setup.sh rebuild    install Python packages, download all raw data (about 6 GB), rebuild the data pack, then start
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "Python 3.10 or newer is required: https://www.python.org/downloads/"; exit 1; }
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10 or newer is required (found $("$PY" --version))."; exit 1; }
if [ "$1" = "rebuild" ]; then
  [ -d .venv ] || "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r analog-finder/requirements.txt
  .venv/bin/python analog-finder/pipeline/rebuild.py
fi
exec sh analog-finder/start.sh
