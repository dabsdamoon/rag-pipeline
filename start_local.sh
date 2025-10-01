#!/bin/bash
set -euo pipefail

# Usage: ./start_local.sh [backend_port] [frontend_port]
# Default ports: backend=8001, frontend=3001

BACKEND_PORT=${1:-8001}
FRONTEND_PORT=${2:-3001}

# Load .env file if it exists
if [ -f .env ]; then
  echo "📋 Loading environment variables from .env..."
  set -a  # automatically export all variables
  source .env
  set +a
fi

export TEST_WITH_CHROMADB=${TEST_WITH_CHROMADB:-false}
echo "🔧 Using ChromaDB: $TEST_WITH_CHROMADB"

ensure_npm() {
  if command -v npm >/dev/null 2>&1; then
    return 0
  fi

  local nvm_dir="${NVM_DIR:-$HOME/.nvm}"
  if [ -s "$nvm_dir/nvm.sh" ]; then
    # shellcheck source=/dev/null
    . "$nvm_dir/nvm.sh"
  elif [ -s "/usr/local/opt/nvm/nvm.sh" ]; then
    # shellcheck source=/dev/null
    . "/usr/local/opt/nvm/nvm.sh"
  fi

  command -v npm >/dev/null 2>&1
}

fail() {
  echo "❌ $1" >&2
  exit 1
}

cleanup() {
  echo "🛑 Shutting down servers..."
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if ! ensure_npm; then
  fail "npm is not available. Run 'nvm use' or install Node.js before starting."
fi

# Activate conda environment if available
if [ -n "${CONDA_DEFAULT_ENV:-}" ] && [ "$CONDA_DEFAULT_ENV" != "houmy" ]; then
  echo "⚠️  Currently in conda env '$CONDA_DEFAULT_ENV'. Switching to 'houmy'..."
  # shellcheck source=/dev/null
  source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
  conda activate houmy || fail "Failed to activate conda environment 'houmy'"
elif [ -z "${CONDA_DEFAULT_ENV:-}" ]; then
  echo "🐍 Activating conda environment 'houmy'..."
  # shellcheck source=/dev/null
  source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
  conda activate houmy || fail "Failed to activate conda environment 'houmy'. Please run 'conda activate houmy' first."
fi

# Determine python executable (prefer current env)
if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/python" ]; then
  PYTHON_BIN="$CONDA_PREFIX/bin/python"
else
  fail "Python not found. Please ensure python is installed and the 'houmy' conda environment is available."
fi

echo "🚀 Starting Houmy RAG Chatbot (local mode)"
echo "📡 Backend port:  $BACKEND_PORT"
echo "🎨 Frontend port: $FRONTEND_PORT"

echo "📡 Starting FastAPI backend on port $BACKEND_PORT..."
"$PYTHON_BIN" main.py --port "$BACKEND_PORT" &
BACKEND_PID=$!

# Wait for backend to start and verify it's running
echo "⏳ Waiting for backend to start..."
sleep 3

# Check if backend process is still alive
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "❌ Backend process died immediately after starting!"
  echo "Check for Python errors above."
  exit 1
fi

# Wait a bit more for the server to bind to the port
sleep 2

# Check if backend is responding
MAX_RETRIES=10
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -s "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
    echo "✅ Backend is responding on port $BACKEND_PORT"
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
    echo "⏳ Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
  fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "❌ Backend failed to start on port $BACKEND_PORT!"
  echo "Backend PID: $BACKEND_PID"
  echo ""
  echo "Troubleshooting steps:"
  echo "1. Check if port $BACKEND_PORT is already in use: lsof -i :$BACKEND_PORT"
  echo "2. Try starting manually: $PYTHON_BIN main.py --port $BACKEND_PORT"
  echo "3. Check Python environment and dependencies"
  echo ""
  echo "Cleaning up..."
  kill "$BACKEND_PID" 2>/dev/null || true
  exit 1
fi

cd frontend || fail "frontend directory not found"

if [ ! -d "node_modules" ] || ! npx --yes react-scripts -v >/dev/null 2>&1; then
  echo "📦 Installing frontend dependencies..."
  npm install --no-fund --no-audit
fi

export REACT_APP_LOCAL_API_URL="http://localhost:$BACKEND_PORT"
export REACT_APP_DEFAULT_API_TARGET="local"
unset REACT_APP_CLOUDRUN_API_URL || true

echo "🎨 Starting React frontend on port $FRONTEND_PORT..."
HOST=0.0.0.0 PORT=$FRONTEND_PORT npm start &
FRONTEND_PID=$!

echo "✅ Both servers running!"
echo "📡 Backend:  http://localhost:$BACKEND_PORT"
echo "🎨 Frontend: http://localhost:$FRONTEND_PORT"
echo "📖 API Docs: http://localhost:$BACKEND_PORT/docs"
echo "Press Ctrl+C to stop both servers"

wait "$BACKEND_PID" "$FRONTEND_PID"
