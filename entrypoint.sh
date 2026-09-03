#!/bin/bash
set -e

# Start admin console in the background
python -m admin &
ADMIN_PID=$!

# Start bot in the background
python main.py "$@" &
BOT_PID=$!

# Signal handling for clean container shutdown
shutdown() {
    echo "Stopping BookTower services..."
    kill -TERM "$ADMIN_PID" "$BOT_PID" 2>/dev/null || true
    wait "$ADMIN_PID" 2>/dev/null || true
    wait "$BOT_PID" 2>/dev/null || true
}

trap shutdown SIGINT SIGTERM SIGHUP

# Wait for either process to terminate
wait -n "$ADMIN_PID" "$BOT_PID" 2>/dev/null || wait "$BOT_PID" "$ADMIN_PID" 2>/dev/null || true
shutdown
