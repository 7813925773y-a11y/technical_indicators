#!/usr/bin/env bash
# Launch the TV Indicator Analyzer web UI
# Prereq: TradingView Desktop running with CDP on :9222
#   bash ../tradingview-mcp/scripts/launch_tv_debug_mac.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/../../mcp-crew-ai/.venv"

if [[ ! -f "$VENV/bin/python" ]]; then
  echo "ERROR: venv not found at $VENV"
  echo "  Run: cd ../../mcp-crew-ai && uv sync"
  exit 1
fi

cd "$SCRIPT_DIR"

export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo ""
echo "  TV Indicator Analyzer  →  http://localhost:8765"
echo "  Press Ctrl-C to stop."
echo ""

exec "$VENV/bin/python" main.py
