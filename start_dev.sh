#!/bin/bash
set -euo pipefail

# Usage: ./start_dev.sh [frontend_port]
# Default frontend port: 3001

FRONTEND_PORT=${1:-3001}

# Cloud Run API URL can be provided via CLOUD_RUN_API_URL or pre-set REACT_APP_CLOUDRUN_API_URL
# DEFAULT_CLOUD_RUN_URL="https://houmy-api-932784017415.us-central1.run.app" # for relays-cloud
DEFAULT_CLOUD_RUN_URL="https://houmy-api-369068805659.us-central1.run.app" # for project-houmy
CLOUD_RUN_URL=${CLOUD_RUN_API_URL:-${REACT_APP_CLOUDRUN_API_URL:-$DEFAULT_CLOUD_RUN_URL}}
LOCAL_API_URL=${LOCAL_API_URL:-${REACT_APP_LOCAL_API_URL:-"http://localhost:8001"}}

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

if ! ensure_npm; then
  echo "❌ npm is not available. Install Node.js or run 'nvm use' first." >&2
  exit 1
fi

cleanup() {
  echo "🛑 Shutting down frontend..."
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

cd frontend || { echo "❌ frontend directory not found" >&2; exit 1; }

if [ ! -d "node_modules" ] || ! npx --yes react-scripts -v >/dev/null 2>&1; then
  echo "📦 Installing frontend dependencies..."
  npm install --no-fund --no-audit
fi

export REACT_APP_CLOUDRUN_API_URL="$CLOUD_RUN_URL"
export REACT_APP_LOCAL_API_URL="$LOCAL_API_URL"
export REACT_APP_DEFAULT_API_TARGET="cloud"

echo "🚀 Launching Houmy demo frontend (Cloud Run mode)"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend:    http://localhost:$FRONTEND_PORT"
echo "   Backend API: $REACT_APP_CLOUDRUN_API_URL"
echo ""
echo "🎭 Features Available:"
echo "   ✨ Create Character - AI-powered character generation"
echo "   🎭 Roleplay Chat    - Chat with your custom characters"
echo "   📚 RAG Assistant    - Document Q&A with knowledge base"
echo ""
echo "⚠️  Note: Cloud Run API must be deployed with roleplay endpoints"

echo "🎨 Starting React frontend on port $FRONTEND_PORT..."
HOST=0.0.0.0 PORT=$FRONTEND_PORT npm start &
FRONTEND_PID=$!

wait "$FRONTEND_PID"
