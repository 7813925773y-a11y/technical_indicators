#!/usr/bin/env bash
# Boot the mcp-crew-ai MCP server pointed at the tv_indicator_crew YAMLs.
#
# Usage:
#   ./tradingview_based_indicators/tv_indicator_crew/run.sh
#
# This starts the FastMCP server over STDIO. It is meant to be launched
# by an MCP client (Claude Code, Cursor, etc.) — not invoked directly
# by a human in a terminal. The .mcp.json in the repo root wires this
# server into Claude Code automatically.
#
# Prerequisites:
#   cd ~/Desktop/trading_agent/mcp-crew-ai
#   python3.11 -m venv .venv && .venv/bin/pip install -e .

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
VENV="$REPO/mcp-crew-ai/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "venv missing at $VENV — run: cd $REPO/mcp-crew-ai && python3.11 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

export MCP_CREW_AGENTS_FILE="$HERE/agents.yml"
export MCP_CREW_TASKS_FILE="$HERE/tasks.yml"
# Sequential process — CrewAI fires async tasks concurrently while sync
# downstream tasks block until their context tasks complete.
export MCP_CREW_PROCESS="sequential"
export MCP_CREW_TOPIC="${MCP_CREW_TOPIC:-SPY}"
export MCP_CREW_VERBOSE="${MCP_CREW_VERBOSE:-0}"

exec "$VENV/bin/python" -m mcp_crew_ai.server_cmd
