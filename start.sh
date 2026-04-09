#!/bin/bash
# ECTHR Translator - Start Script
# Usage: ./start.sh

set -e

echo "🚀 Starting ECTHR Translator..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "📝 Copy .env.example to .env and add your ANTHROPIC_API_KEY"
    exit 1
fi

# Source .env
export $(cat .env | grep -v '^#' | xargs)

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY not set in .env"
    exit 1
fi

# Create data directories
mkdir -p data/tm data/uploads data/outputs

echo "📦 Installing backend dependencies..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "🔧 Starting backend server on port 8000..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ../data/backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

cd ../frontend

echo "📦 Installing frontend dependencies..."
if [ ! -d "node_modules" ]; then
    npm install -q
fi

echo "🎨 Starting frontend server on port 3000..."
npm run dev > ../data/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"

cd ..

# Save PIDs for cleanup
echo $BACKEND_PID > data/backend.pid
echo $FRONTEND_PID > data/frontend.pid

echo ""
echo "${GREEN}✅ ECTHR Translator is running!${NC}"
echo ""
echo "${BLUE}📍 Frontend:${NC} http://localhost:3000"
echo "${BLUE}📍 Backend:${NC}  http://localhost:8000"
echo "${BLUE}📍 API Docs:${NC} http://localhost:8000/docs"
echo ""
echo "📋 Logs:"
echo "   Backend:  tail -f data/backend.log"
echo "   Frontend: tail -f data/frontend.log"
echo ""
echo "🛑 To stop: ./stop.sh"
echo ""

# Wait a bit and check if processes are still running
sleep 3
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend failed to start. Check data/backend.log"
    exit 1
fi
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend failed to start. Check data/frontend.log"
    exit 1
fi

echo "✅ All services running successfully!"
