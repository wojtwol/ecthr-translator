#!/bin/bash
# ECTHR Translator - Stop Script

echo "🛑 Stopping ECTHR Translator..."

# Kill by PID files
if [ -f data/backend.pid ]; then
    BACKEND_PID=$(cat data/backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        echo "✅ Backend stopped (PID: $BACKEND_PID)"
    fi
    rm data/backend.pid
fi

if [ -f data/frontend.pid ]; then
    FRONTEND_PID=$(cat data/frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID
        echo "✅ Frontend stopped (PID: $FRONTEND_PID)"
    fi
    rm data/frontend.pid
fi

# Fallback: kill by port
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

echo "✅ All services stopped"
