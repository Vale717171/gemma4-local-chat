#!/bin/bash
source "$HOME/mlx-env/bin/activate"
lsof -ti:5000 | xargs kill -9 2>/dev/null
python "$HOME/mlx-chat/server.py" &
SERVER_PID=$!
echo "Loading model, please wait..."
until curl -s http://localhost:5000 > /dev/null 2>&1; do
  sleep 1
done
# Open in Chrome if available, otherwise default browser
if open -a "Google Chrome" http://127.0.0.1:5000 2>/dev/null; then
  :
else
  open http://127.0.0.1:5000
fi
wait $SERVER_PID
