#!/bin/bash
# Double-click this file on a Mac to run the full hoopsim app.
#
# It installs what it needs the first time (into a private folder next to this
# script, so it cannot disturb anything else on your machine), starts the local
# server, and opens your browser. Close the Terminal window to stop it.
#
# If you only want to look around, open dist/hoopsim.html instead -- that needs
# nothing at all.

set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n%s\n' "$*"; }

PYTHON=""
for candidate in python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  say "hoopsim needs Python 3.10 or newer, and I could not find it."
  say "The easiest fix is to install it from https://www.python.org/downloads/"
  say "Then double-click this file again."
  say "In the meantime, open  dist/hoopsim.html  -- it needs nothing installed."
  read -r -p "Press return to close this window. "
  exit 1
fi

VENV=".hoopsim-venv"
if [ ! -d "$VENV" ]; then
  say "First run: setting up. This takes a minute or two, only once."
  "$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

if ! python -c 'import hoopsim' >/dev/null 2>&1; then
  say "Installing hoopsim and the libraries it needs ..."
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -e .
fi

PORT=8000
while lsof -i :"$PORT" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done

say "Starting hoopsim on http://127.0.0.1:$PORT"
say "Your browser should open by itself. Close this window to stop."
( sleep 4; open "http://127.0.0.1:$PORT/" 2>/dev/null || true ) &

exec hoopsim serve --port "$PORT"
