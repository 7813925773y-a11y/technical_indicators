# TV Indicator Analyzer

A local web UI that reads a live TradingView chart, runs five custom Pine Script indicators via OHLCV computation, and synthesizes a trade recommendation using a 5-analyst CrewAI crew.

---

## How it works

```
Browser (http://localhost:8765)
  │  Enter ticker + timeframe → click Run
  │
  ▼
FastAPI server  (main.py)
  │
  ├─ Phase 1 — Data gathering
  │    ├─ Connects to TradingView Desktop via tradingview-mcp (CDP on port 9222)
  │    ├─ Sets chart symbol and timeframe
  │    ├─ Fetches OHLCV bars (200–300 bars per indicator)
  │    └─ Runs 5 Python indicator modules against the bars → brief + chart data
  │         mcpe.py · harmonic.py · ichimoku.py · fibstruct.py · demark_compute.py
  │
  └─ Phase 2 — CrewAI synthesis
       ├─ Passes all 5 briefs to tv_indicator_crew (agents.yml + tasks.yml)
       ├─ 5 specialist analysts run in parallel (async_execution: true)
       └─ Chief strategist synthesizes → final trade recommendation
```

Results stream to the browser in real time via **Server-Sent Events**. Each indicator tab populates as its data arrives; the Synthesis tab populates last.

---

## Indicators

| Tab | Module | What it computes |
|-----|--------|-----------------|
| MCPE | `mcpe.py` | Wyckoff 4-phase cycle (Accumulation / Markup / Distribution / Markdown) via LR slope + ATR ratio. Shows phase-colored candles, cycle high/mid/low levels, and a projection target. |
| HAV | `harmonic.py` | Scott Carney's 6 harmonic patterns (Gartley, Bat, Alt Bat, Butterfly, Crab, Deep Crab). Detects XABCD zigzag pivots, validates ratio bands, scores 0–10, draws PRZ zone. |
| Ichimoku | `ichimoku.py` | Full Ichimoku (Tenkan/Kijun/Senkou A & B/Chikou) + LuxAlgo swing detection + N-wave price targets (V/E/N/NT/2E/3E). Cloud rendered as bull/bear area fills. |
| FibStruct | `fibstruct.py` | SMC pipeline: ATR-filtered swings → BOS/CHoCH → structure-anchored Fibonacci retracement → confluence scoring → entry signals. |
| DeMark | `demark_compute.py` | TD Sequential buy/sell count 1–13. Count 9 = perfected setup; count 13 = exhaustion. Candles colored by heatmap intensity. |

All five modules are pure Python translations of the Pine Script originals — no TradingView label parsing, no screenshots for data extraction.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| TradingView Desktop (Mac) | Must be running before starting the server |
| CDP debug port enabled | Run `bash ../tradingview-mcp/scripts/launch_tv_debug_mac.sh` once |
| Python venv | Shared with `mcp-crew-ai/` — run `uv sync` there if not set up |
| OpenAI API key | Set `OPENAI_API_KEY` in your environment for CrewAI synthesis |

The five Pine Script indicators do **not** need to be on the chart for data extraction — OHLCV bars are the only input. They are used by the `/tv-indicator-analyzer` Claude Code skill for visual reference only.

---

## Running

```bash
# 1. Start TradingView Desktop with CDP enabled
bash ../tradingview-mcp/scripts/launch_tv_debug_mac.sh

# 2. Start the web server
bash tv-indicator-ui/run.sh

# 3. Open in browser
open http://localhost:8765
```

Enter a ticker (e.g. `GLD`) and timeframe (`4H`, `Day`, `Week`, `Month`), then click **Run Analysis**.

---

## File layout

```
tv-indicator-ui/
├── main.py              FastAPI server — SSE stream endpoint
├── brief_builder.py     Calls each indicator module; assembles structured briefs
├── tv_mcp_client.py     Thin async wrapper around tradingview-mcp (CDP)
├── crew_runner.py       Launches tv_indicator_crew with model fallback chain
├── mcpe.py              MCPE indicator — Python translation of Pine Script v2.0
├── harmonic.py          HAV indicator — Pine Script v1.1 translation
├── ichimoku.py          Ichimoku Theories — LuxAlgo Pine Script translation
├── fibstruct.py         Fibonacci Structure Engine translation
├── demark_compute.py    TD Sequential translation
├── templates/
│   └── index.html       Single-page UI — Lightweight Charts v4.2 + SSE client
└── run.sh               Launch script (activates mcp-crew-ai venv)
```

The CrewAI crew lives at `../tv_indicator_crew/` (agents.yml + tasks.yml).

---

## Chart UI details

- **OHLC tooltip** — hover over any candle to see O/H/L/C values
- **Zoom** — charts open showing the last 60 bars; scroll/pinch to zoom
- **Height** — charts auto-size to ~58% of your browser window height
- **Width** — charts fill the full page width edge-to-edge
- **Summary bar** — key signal values shown above each chart (phase, kumo position, etc.)

---

## CrewAI fallback chain

If the primary model (`gpt-5.4-mini`) is unavailable, `crew_runner.py` automatically retries with `gpt-4o-mini` → `gpt-4o`. If all CrewAI attempts fail, it falls back to a direct LiteLLM synthesis call and marks the result with a "fallback" badge.
