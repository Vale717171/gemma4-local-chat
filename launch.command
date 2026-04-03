#!/bin/bash
source "$HOME/mlx-env/bin/activate"
lsof -ti:5000 | xargs kill -9 2>/dev/null
python "$HOME/mlx-chat/server.py" &
SERVER_PID=$!
echo "Loading model, please wait..."
until curl -s http://localhost:5000 > /dev/null 2>&1; do
  sleep 1
done
open http://localhost:5000
wait $SERVER_PID
