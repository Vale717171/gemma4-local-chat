#!/bin/bash
set -e

PROJECT_DIR="${GEMMA_CHAT_DIR:-}"
if [ -z "$PROJECT_DIR" ] && [ -f "$(dirname "$0")/server.py" ]; then
  PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

if [ -z "$PROJECT_DIR" ] || [ ! -f "$PROJECT_DIR/server.py" ]; then
  echo "Errore: cartella progetto non trovata."
  echo "Esegui di nuovo setup.sh dalla cartella del progetto."
  exit 1
fi

source "$HOME/mlx-env/bin/activate"

PIDS=$(lsof -ti tcp:5001 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  kill $PIDS 2>/dev/null || true
fi

python "$PROJECT_DIR/server.py" &
SERVER_PID=$!
echo "Loading model, please wait..."
until curl -s http://127.0.0.1:5001 > /dev/null 2>&1; do
  sleep 1
done
# Open in Chrome if available, otherwise default browser
if open -a "Google Chrome" http://127.0.0.1:5001 2>/dev/null; then
  :
else
  open http://127.0.0.1:5001
fi
wait $SERVER_PID
