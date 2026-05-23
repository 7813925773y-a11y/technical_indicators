---
name: tv-indicator-analyzer
description: >
  For a requested ticker and time horizon (4h/day/week/month), reads all 5
  custom TradingView indicators (MCPE, HAV, Ichimoku, FibStruct, TD Sequential)
  from a live chart via TradingView MCP, runs a 5-analyst CrewAI crew for deep
  interpretation, and produces per-indicator verdicts plus a synthesized trade
  recommendation. Invoke as /tv-indicator-analyzer <TICKER> <TIMEFRAME>.
user-invocable: true
allowed-tools:
  - mcp__tradingview__tv_health_check
  - mcp__tradingview__chart_set_symbol
  - mcp__tradingview__chart_set_timeframe
  - mcp__tradingview__chart_get_state
  - mcp__tradingview__chart_manage_indicator
  - mcp__tradingview__data_get_pine_labels
  - mcp__tradingview__data_get_pine_lines
  - mcp__tradingview__data_get_pine_tables
  - mcp__tradingview__data_get_pine_boxes
  - mcp__tradingview__data_get_study_values
  - mcp__tradingview__data_get_ohlcv
  - mcp__tradingview__quote_get
  - mcp__tradingview__capture_screenshot
  - mcp__tradingview__indicator_toggle_visibility
  - mcp__tradingview__pane_list
  - mcp__tradingview__pine_list_scripts
  - mcp__tv-indicator-crew__kickoff
  - Agent
---

# TV Indicator Analyzer

For a given ticker and timeframe, gather live chart data from all 5 custom TradingView indicators, run a specialist CrewAI crew, and return per-indicator verdicts plus a synthesized trade recommendation.

## Entry points

- Args present (`/tv-indicator-analyzer AAPL 4h`) → proceed directly to `references/workflow.md`
- No args → ask for ticker and timeframe (`4h` / `day` / `week` / `month`), then `references/workflow.md`
- "How does X indicator work?" → `references/indicator-playbooks/<indicator>.md`
- Output format reference → `references/output-template.md`

## Timeframe mapping

| User input | TradingView value |
|---|---|
| `4h` | `"240"` |
| `day` | `"D"` |
| `week` | `"W"` |
| `month` | `"M"` |

## Indicator roster

| Indicator | Full title (for `chart_manage_indicator`) | Shorttitle (for `study_filter`) |
|---|---|---|
| MCPE | `Market Cycle Projection Engine` | `MCPE` |
| Harmonic | `Harmonic Auto-Validator [GBB]` | `HAV` |
| Ichimoku | `Ichimoku Theories [LuxAlgo]` | `LuxAlgo - Ichimoku Theories` |
| FibStruct | `Fibonacci Structure Engine [WillyAlgoTrader]` | `FibStruct` |
| DeMark | `Tom DeMark Sequential Heat Map` | `TD heatmap` |

## Hard rules

- Always call `tv_health_check` first. If it fails, stop and tell the user to launch TradingView Desktop: `bash tradingview-mcp/scripts/launch_tv_debug_mac.sh`
- Always pass `study_filter` on all `data_get_pine_*` calls — without it you get data from every study on the chart.
- An indicator must be **visible** on the chart for `data_get_pine_*` to return data. If `chart_manage_indicator` fails to add a missing indicator, warn the user and skip that indicator's analysis rather than fabricating data.
- Never skip `capture_screenshot` per indicator — screenshots are part of the output.
- Always use `summary: true` with `data_get_ohlcv`.
- Call `chart_get_state` once per session; reuse the entity IDs it returns.
- Never invent indicator readings. If a tool returns empty data, report "no data available" for that indicator.
- Indicator must be on the **main price pane** (pane 0) for pine graphics tools to reach it. Check `pane_list` if data comes back empty.
