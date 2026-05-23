# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

Two things live here:

1. **Five Pine Script indicators** — `.script` files ready to paste into TradingView's Pine Editor. Each folder contains the script and a readme/changelog explaining the methodology and settings.
2. **`tradingview-mcp/`** — a vendored Node.js MCP server that lets Claude Code read and control a live TradingView Desktop chart via Chrome DevTools Protocol (CDP on port 9222). This is what powers the `mcp__tradingview__*` tools available in this Claude Code session.

## Indicator inventory

| Folder | Script name | Core methodology |
|---|---|---|
| `cycle_indicator/` | Market Cycle Projection Engine (MCPE) | Wyckoff 4-phase cycle (Accumulation / Markup / Distribution / Markdown) via LR slope + ATR ratio + price position |
| `harmonic_wave_indicator/` | Harmonic Auto-Validator [GBB] | Scott Carney's 6 harmonic patterns (Gartley, Bat, Alt Bat, Butterfly, Crab, Deep Crab) with PRZ zone scoring |
| `ichimoku_indicator/` | Ichimoku Theories | Full Ichimoku (Kinkō Hyō) + Time Theory (Kihon Suchi cycles) + Wave Theory (I/V/N/P/Y/W) + Price Theory targets |
| `smart_money_fibonacci_indicator/` | Fibonacci Structure Engine | SMC pipeline: ATR-filtered swing detection → BOS/CHoCH → structure-anchored Fib retracement → confluence scoring → engulfing + liquidity sweep entries |
| `tom_demark_sequential_indicator/` | TD Sequential heatmap | DeMark TD count 1–13 with candle coloring; highlights count 9 and 13 as exhaustion labels |

Each indicator is Pine Script v6, no repainting, signals on bar close only. Indicators only draw on confirmed bars (`barstate.isconfirmed`).

## Deploying a script to TradingView

Two workflows:

**Manual**: open TradingView Desktop → Pine Editor → paste contents of the `.script` file → Add to chart.

**Via MCP (automated)**: use the `pine_set_source` + `pine_smart_compile` + `pine_save` tool sequence. Check errors with `pine_get_errors` before saving.

```
pine_set_source  → inject code
pine_smart_compile → compile + detect errors
pine_get_errors  → read any errors
pine_save        → save to TradingView cloud
```

Use `pine_open "<indicator name>"` to reopen a previously saved script for editing.

## tradingview-mcp architecture

```
Claude Code ←─ MCP stdio ─→ tradingview-mcp/src/server.js ←─ CDP :9222 ─→ TradingView Desktop (Electron)
```

- `src/server.js` — MCP server entry point. Registers all 78 tool groups via `register*Tools(server)` calls.
- `src/tools/` — one file per domain (chart, pine, data, drawing, replay, alerts, ui, pane, tab, …). Each registers its MCP tools against the server instance.
- `src/core/` — pure logic layer that each tool file delegates to. Tools handle parameter validation and formatting; core handles CDP calls.
- `src/connection.js` — CDP connection singleton (retries, known JS API paths into `window.TradingViewApi`).
- `src/tools/_format.js` — shared response formatting helpers.

### Running the MCP server

```bash
cd tradingview-mcp
npm start          # node src/server.js (stdio transport)
```

TradingView Desktop must be running with CDP enabled first. On Mac:

```bash
bash scripts/launch_tv_debug_mac.sh
```

Then verify with `tv_health_check` before any other tool call.

### Tests

```bash
cd tradingview-mcp
npm test              # e2e + pine_analyze unit tests (requires live TV connection for e2e)
npm run test:unit     # unit tests only (pine_analyze + CLI — no live connection needed)
npm run test:cli      # CLI command tests
```

Unit tests (`tests/pine_analyze.test.js`, `tests/cli.test.js`) run without a live TradingView connection. E2E tests (`tests/e2e.test.js`) require TradingView Desktop to be running on CDP :9222.

## Pine Script editing conventions

- Indicators use `var` for persistent variables and `type` declarations (Pine v6 user-defined types).
- All alert payloads support both plain text and JSON webhook format — preserve both in any edits.
- The `study_filter` parameter on MCP pine-graphics tools (`data_get_pine_lines`, `data_get_pine_labels`, etc.) matches by indicator **display name** substring, not script filename. Use the `shorttitle` or `title` as defined in the `indicator()` call.
- Key shorttitles: MCPE, FibStruct (smart money fib), Ichimoku Theories. Check `chart_get_state` for the exact names on the active chart.

## TV Indicator Multi-Agent System

`/tv-indicator-analyzer <TICKER> <TIMEFRAME>` — invocable skill that reads all 5 indicators from a live TradingView chart and produces per-indicator verdicts + a synthesized trade recommendation.

### Components

| Component | Location | Role |
|---|---|---|
| Claude Code skill | `tv-indicator-analyzer/` | Data gathering via TV MCP + crew orchestration |
| CrewAI crew | `tv_indicator_crew/` | 5 specialist analysts + chief strategist |
| MCP registration | `../.mcp.json` (`tv-indicator-crew` server) | Wires the crew into Claude Code |
| Runtime copy | `~/.claude/skills/tv-indicator-analyzer/` | Makes skill invocable as `/tv-indicator-analyzer` |

### Workflow

```
/tv-indicator-analyzer AAPL 4h

1. TV preflight (health check, set symbol/TF, chart_get_state)
2. Auto-add any missing indicators via chart_manage_indicator
3. Spawn 5 parallel Agents to read pine data + screenshots per indicator
4. Assemble 5 structured briefs
5. Kick off tv-indicator-crew CrewAI (5 async analysts → chief strategist)
6. Present: per-indicator verdicts + screenshots + synthesized recommendation
```

### Reference docs (inside tv-indicator-analyzer/)

- `references/workflow.md` — exact tool sequences for each phase
- `references/output-template.md` — final report structure
- `references/indicator-playbooks/<name>.md` — data extraction + interpretation per indicator

## MCP tool usage rules (from tradingview-mcp/CLAUDE.md)

- Always call `chart_get_state` once at session start to get entity IDs — don't re-call on every action.
- Always pass `summary: true` to `data_get_ohlcv` unless you need individual bars.
- Always pass `study_filter` on pine-graphics tools when targeting a specific indicator.
- Avoid `pine_get_source` on complex scripts — returns 200 KB+. Only read if you need to edit.
- Use `capture_screenshot` for visual context rather than pulling large datasets.
- `chart_manage_indicator` requires full indicator names: "Relative Strength Index" not "RSI".
- Pine indicator must be **visible** on the chart for `data_get_pine_*` tools to return data.
