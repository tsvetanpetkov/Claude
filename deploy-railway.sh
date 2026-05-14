#!/usr/bin/env bash
# Deploys the data_explorer Streamlit app to Railway.
# Prerequisites: Node.js installed, ANTHROPIC_API_KEY set.
set -euo pipefail

command -v railway &>/dev/null || {
    echo "Railway CLI not found. Install it with:"
    echo "  npm install -g @railway/cli"
    exit 1
}

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY env var must be set}"

echo "==> Logging in to Railway..."
railway login

echo "==> Initialising project (skip if already linked)..."
railway init --name data-explorer 2>/dev/null || true

echo "==> Setting ANTHROPIC_API_KEY..."
railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"

echo "==> Deploying..."
railway up --detach

echo ""
echo "Deployment started."
echo "  Status : railway status"
echo "  Logs   : railway logs"
echo "  Open   : railway open"
